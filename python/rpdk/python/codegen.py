import docker
import logging
import os
import shutil
import zipfile
from docker.errors import APIError, ContainerError, ImageLoadError
from pathlib import PurePosixPath
from requests.exceptions import ConnectionError as RequestsConnectionError
from rpdk.core.data_loaders import resource_stream
from rpdk.core.exceptions import DownstreamError, SysExitRecommendedError
from rpdk.core.init import input_with_validation
from rpdk.core.jsonutils.resolver import (
    UNDEFINED,
    ContainerType,
    ResolvedType,
    resolve_models,
)
from rpdk.core.plugin_base import LanguagePlugin
from rpdk.core.project import ARTIFACT_TYPE_HOOK
from subprocess import PIPE, CalledProcessError, run as subprocess_run  # nosec
from tempfile import TemporaryFile
from typing import Dict

from . import __version__
from .resolver import contains_model, translate_type

LOG = logging.getLogger(__name__)

EXECUTABLE = "cfn"
SUPPORT_LIB_NAME = "cloudformation-cli-python-lib"
SUPPORT_LIB_PKG = SUPPORT_LIB_NAME.replace("-", "_")


class StandardDistNotFoundError(SysExitRecommendedError):
    pass


def validate_no(value):
    return value.lower() not in ("n", "no")


class _PythonLanguagePlugin(LanguagePlugin):
    MODULE_NAME = __name__
    NAME = ""
    RUNTIME = ""
    HOOK_ENTRY_POINT = "{}.handlers.hook"
    RESOURCE_ENTRY_POINT = "{}.handlers.resource"
    TEST_ENTRY_POINT = "{}.handlers.test_entrypoint"
    CODE_URI = "build/"
    DOCKER_TAG = ""

    def __init__(self):
        self.env = self._setup_jinja_env(
            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
        )
        self.env.filters["translate_type"] = translate_type
        self.env.filters["contains_model"] = contains_model
        self.env.globals["ContainerType"] = ContainerType
        self.namespace = None
        self.package_name = None
        self.package_root = None
        self._use_docker = None
        self._no_docker = None
        self._protocol_version = "2.0.0"

    def _init_from_project(self, project):
        self.namespace = tuple(s.lower() for s in project.type_info)
        self.package_name = "_".join(self.namespace)
        # Check config file for (legacy) 'useDocker' and use_docker settings
        self._use_docker = project.settings.get("useDocker") or project.settings.get(
            "use_docker"
        )
        self.package_root = project.root / "src"

    def _init_settings(self, project):
        LOG.debug("Writing settings")

        project.runtime = self.RUNTIME
        if project.artifact_type == ARTIFACT_TYPE_HOOK:
            project.entrypoint = self.HOOK_ENTRY_POINT.format(self.package_name)
            project.test_entrypoint = project.entrypoint.replace(
                ".hook", ".test_entrypoint"
            )
        else:
            project.entrypoint = self.RESOURCE_ENTRY_POINT.format(self.package_name)
            project.test_entrypoint = project.entrypoint.replace(
                ".resource", ".test_entrypoint"
            )

        # If use_docker specified in .rpdk-config file or cli switch
        # Ensure only 1 is true, with preference to use_docker
        if project.settings.get("use_docker") is True:
            self._use_docker = True
            self._no_docker = False
        # If no_docker specified in .rpdk-config file or cli switch
        elif project.settings.get("no_docker") is True:
            self._use_docker = False
            self._no_docker = True
        else:
            # If neither no_docker nor use_docker specified in .rpdk-config
            # file or cli switch, prompt to use containers or not
            self._use_docker = input_with_validation(
                "Use docker for platform-independent packaging (Y/n)?\n",
                validate_no,
                "This is highly recommended unless you are experienced \n"
                "with cross-platform Python packaging.",
            )
            self._no_docker = not self._use_docker

        # project.settings will get saved into .rpdk-config by cloudformation-cli
        project.settings["use_docker"] = self._use_docker
        project.settings["no_docker"] = self._no_docker
        project.settings["protocolVersion"] = self._protocol_version

    def init(self, project):
        LOG.debug("Init started")

        self._init_from_project(project)
        self._init_settings(project)

        def _render_template(path, **kwargs):
            LOG.debug("Writing '%s'", path)
            template = self.env.get_template(path.name)
            contents = template.render(**kwargs)
            project.safewrite(path, contents)

        def _copy_resource(path, resource_name=None):
            LOG.debug("Writing '%s'", path)
            if not resource_name:
                resource_name = path.name
            contents = resource_stream(__name__, f"data/{resource_name}").read()
            project.safewrite(path, contents)

        # handler Python package
        handler_package_path = self.package_root / self.package_name
        LOG.debug("Making folder '%s'", handler_package_path)
        handler_package_path.mkdir(parents=True, exist_ok=True)
        _copy_resource(handler_package_path / "__init__.py")
        self.init_handlers(project, handler_package_path)
        # models.py produced by generate

        # project support files
        _copy_resource(project.root / ".gitignore", "Python.gitignore")
        _render_template(
            project.root / "requirements.txt", support_lib_name=SUPPORT_LIB_NAME
        )
        _render_template(
            project.root / "README.md",
            type_name=project.type_name,
            schema_path=project.schema_path,
            project_path=self.package_name,
            executable=EXECUTABLE,
            support_lib_pkg=SUPPORT_LIB_PKG,
        )

        # CloudFormation/SAM template for handler lambda
        handler_params = {
            "Handler": project.entrypoint,
            "Runtime": project.runtime,
            "CodeUri": self.CODE_URI,
        }
        _render_template(
            project.root / "template.yml",
            resource_type=project.type_name,
            functions={
                "TypeFunction": handler_params,
                "TestEntrypoint": {
                    **handler_params,
                    "Handler": project.test_entrypoint,
                },
            },
        )

        LOG.debug("Init complete")

    def init_handlers(self, project, handler_package_path):
        path = handler_package_path / "handlers.py"
        if project.artifact_type == ARTIFACT_TYPE_HOOK:
            template = self.env.get_template("hook_handlers.py")
        else:
            template = self.env.get_template("handlers.py")
        contents = template.render(
            support_lib_pkg=SUPPORT_LIB_PKG, type_name=project.type_name
        )
        project.safewrite(path, contents)

    def generate(self, project):
        LOG.debug("Generate started")

        self._init_from_project(project)
        if project.artifact_type == ARTIFACT_TYPE_HOOK:
            models = resolve_models(project.schema, "HookInputModel")
        else:
            models = resolve_models(project.schema)

        if project.configuration_schema:
            configuration_schema_path = (
                project.root / project.configuration_schema_filename
            )
            project.write_configuration_schema(configuration_schema_path)
            configuration_models = resolve_models(
                project.configuration_schema, "TypeConfigurationModel"
            )
        else:
            configuration_models = {"TypeConfigurationModel": {}}
        models.update(configuration_models)

        path = self.package_root / self.package_name / "models.py"
        LOG.debug("Writing file: %s", path)
        if project.artifact_type == ARTIFACT_TYPE_HOOK:
            template = self.env.get_template("hook_models.py")
        else:
            template = self.env.get_template("models.py")

        contents = template.render(support_lib_pkg=SUPPORT_LIB_PKG, models=models)
        project.overwrite(path, contents)

        if project.artifact_type == ARTIFACT_TYPE_HOOK:
            self._generate_target_models(project)

        LOG.debug("Generate complete")

    def _generate_target_models(self, project):
        target_model_dir = self.package_root / self.package_name / "target_models"

        LOG.debug("Removing generated models: %s", target_model_dir)
        shutil.rmtree(target_model_dir, ignore_errors=True)

        target_model_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("target_model.py")

        for target_type_name, target_info in project.target_info.items():
            target_schema = target_info["Schema"]
            target_namespace = [
                s.lower() for s in target_type_name.split("::")
            ]  # AWS::SQS::Queue -> awssqsqueue
            target_name = "".join(
                [s.capitalize() for s in target_namespace]
            )  # awssqsqueue -> AwsSqsQueue
            target_model_file = f'{"_".join(target_namespace)}.py'
            # awssqsqueue -> aws_sqs_queue.py

            models = resolve_models(target_schema, target_name)

            # TODO: Remove once tagging is fully supported
            if models.get(target_name, {}).get("Tags"):  # pragma: no cover
                models[target_name]["Tags"] = ResolvedType(
                    ContainerType.PRIMITIVE, UNDEFINED
                )

            path = target_model_dir / target_model_file
            LOG.debug("Writing file: %s", path)

            contents = template.render(
                support_lib_pkg=SUPPORT_LIB_PKG, models=models, target_name=target_name
            )
            project.overwrite(path, contents)

    # pylint: disable=unused-argument
    # the argument "project" is not used here but is used in codegen.py of other plugins
    # this method is called in cloudformation-cli/src/rpdk/core/project.py
    def get_plugin_information(self, project) -> Dict:
        return self._get_plugin_information()

    def _pre_package(self, build_path):
        f = TemporaryFile("w+b")  # pylint: disable=R1732

        with zipfile.ZipFile(f, mode="w") as zip_file:
            self._recursive_relative_write(build_path, build_path, zip_file)
        f.seek(0)

        return f

    @staticmethod
    def _recursive_relative_write(src_path, base_path, zip_file):
        for path in src_path.rglob("*"):
            if path.is_file() and path.suffix != ".pyc":
                relative = path.relative_to(base_path)
                zip_file.write(path.resolve(), str(relative))

    def package(self, project, zip_file):
        LOG.debug("Package started")

        self._init_from_project(project)

        handler_package_path = self.package_root / self.package_name
        build_path = project.root / "build"

        self._remove_build_artifacts(build_path)
        self._build(project.root)
        shutil.copytree(str(handler_package_path), str(build_path / self.package_name))

        inner_zip = self._pre_package(build_path)
        zip_file.writestr("ResourceProvider.zip", inner_zip.read())
        self._recursive_relative_write(handler_package_path, project.root, zip_file)

        LOG.debug("Package complete")

    @staticmethod
    def _remove_build_artifacts(deps_path):
        LOG.debug("Removing '%s' folder.", deps_path)
        shutil.rmtree(deps_path, ignore_errors=True)

    def _build(self, base_path):
        LOG.debug("Dependencies build started from '%s'", base_path)
        if self._use_docker:
            self._docker_build(base_path)
        else:
            self._pip_build(base_path)
        LOG.debug("Dependencies build finished")

    @staticmethod
    def _make_pip_command(base_path):
        return [
            "pip",
            "install",
            "--no-cache-dir",
            "--no-color",
            "--disable-pip-version-check",
            "--upgrade",
            "--requirement",
            str(base_path / "requirements.txt"),
            "--target",
            str(base_path / "build"),
        ]

    @staticmethod
    def _get_plugin_information() -> Dict:
        return {"plugin-tool-version": __version__, "plugin-name": "python"}

    @classmethod
    def _docker_build(cls, external_path):
        internal_path = PurePosixPath("/project")
        command = (
            '/bin/bash -c "' + " ".join(cls._make_pip_command(internal_path)) + '"'
        )
        LOG.debug("command is '%s'", command)

        volumes = {str(external_path): {"bind": str(internal_path), "mode": "rw"}}
        image = f"public.ecr.aws/sam/build-python{cls.DOCKER_TAG}"
        LOG.warning(
            "Starting Docker build. This may take several minutes if the "
            "image '%s' needs to be pulled first.",
            image,
        )

        # Docker will mount the path specified in the volumes variable in the container
        # and pip will place all the dependent packages inside the volumes/build path.
        # codegen will need access to this directory during package()
        try:
            # Use root:root for euid:group when on Windows
            # https://docs.docker.com/desktop/windows/permission-requirements/#containers-running-as-root-within-the-linux-vm
            if os.name == "nt":
                localuser = "root:root"
            # Try to get current effective user ID and Group ID.
            # Only valid on UNIX-like systems
            else:
                localuser = f"{os.geteuid()}:{os.getgid()}"
        # Catch exception if geteuid failed on non-Windows system
        # and default to root:root
        except AttributeError:
            localuser = "root:root"
            LOG.warning(
                "User ID / Group ID not found.  Using root:root for docker build"
            )

        docker_client = docker.from_env()
        try:
            logs = docker_client.containers.run(
                image=image,
                command=command,
                remove=True,
                volumes=volumes,
                stream=True,
                entrypoint="",
                user=localuser,
                platform="linux/amd64",
            )
        except RequestsConnectionError as e:
            # it seems quite hard to reliably extract the cause from
            # ConnectionError. we replace it with a friendlier error message
            # and preserve the cause for debug traceback
            cause = RequestsConnectionError(
                "Could not connect to docker - is it running?"
            )
            cause.__cause__ = e
            raise DownstreamError("Error running docker build") from cause
        except (ContainerError, ImageLoadError, APIError) as e:
            raise DownstreamError("Error running docker build") from e
        LOG.debug("Build running. Output:")
        for line in logs:
            LOG.debug(line.rstrip(b"\n").decode("utf-8"))

    @classmethod
    def _pip_build(cls, base_path):
        command = cls._make_pip_command(base_path)
        LOG.debug("command is '%s'", command)

        LOG.warning("Starting pip build.")
        try:
            # On windows run pip command through the default shell (CMD)
            if os.name == "nt":
                completed_proc = subprocess_run(  # nosec
                    command,
                    stdout=PIPE,
                    stderr=PIPE,
                    cwd=base_path,
                    check=True,
                    shell=True,
                )
            else:
                completed_proc = subprocess_run(  # nosec
                    command,
                    stdout=PIPE,
                    stderr=PIPE,
                    cwd=base_path,
                    check=True,
                )
            LOG.warning("pip build finished.")
        except (FileNotFoundError, CalledProcessError) as e:
            raise DownstreamError("pip build failed") from e

        LOG.debug("--- pip stdout:\n%s", completed_proc.stdout)
        LOG.debug("--- pip stderr:\n%s", completed_proc.stderr)


class Python38LanguagePlugin(_PythonLanguagePlugin):
    NAME = "python38"
    RUNTIME = "python3.8"
    DOCKER_TAG = 3.8


class Python39LanguagePlugin(_PythonLanguagePlugin):
    NAME = "python39"
    RUNTIME = "python3.9"
    DOCKER_TAG = 3.9


class Python310LanguagePlugin(_PythonLanguagePlugin):
    NAME = "python310"
    RUNTIME = "python3.10"
    DOCKER_TAG = 3.10


class Python311LanguagePlugin(_PythonLanguagePlugin):
    NAME = "python311"
    RUNTIME = "python3.11"
    DOCKER_TAG = 3.11


class Python312LanguagePlugin(_PythonLanguagePlugin):
    NAME = "python312"
    RUNTIME = "python3.12"
    DOCKER_TAG = 3.12
