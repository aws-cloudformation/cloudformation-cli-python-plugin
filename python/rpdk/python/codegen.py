import logging
import os
import shutil

import docker
from rpdk.core.plugin_base import LanguagePlugin

LOG = logging.getLogger(__name__)

EXECUTABLE = "cfn-cli"
OLD_VIRTUAL_ENV = ""
OLD_PATH = []


class Python36LanguagePlugin(LanguagePlugin):
    MODULE_NAME = __name__
    NAME = "python37"
    RUNTIME = "python3.7"
    ENTRY_POINT = "cfn_resource.handler_wrapper._handler_wrapper"
    CODE_URI = "./target/{}.zip"

    def __init__(self):
        self.env = self._setup_jinja_env(
            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
        )
        self.package_name = None
        self.schema_filename = None
        self.namespace = None
        self.cfn_resource_version = "cfn_resource==0.0.1"

    def _package_from_project(self, project):
        self.namespace = tuple(s.lower() for s in project.type_info)
        self.package_name = "_".join(self.namespace)

    def _schema_from_project(self, project):
        self.namespace = tuple(s.lower() for s in project.type_info)
        self.schema_filename = "{}.json".format("-".join(self.namespace))

    def init(self, project):
        LOG.debug("Init started")

        self._package_from_project(project)

        project.runtime = self.RUNTIME
        project.entrypoint = self.ENTRY_POINT

        folders = [project.root / self.package_name, project.root / "tests"]

        # venv_dir = project.root / ".venv"
        # venv.create(venv_dir, system_site_packages=False, with_pip=True)

        for f in folders:
            LOG.debug("Making folder: %s", f)
            f.mkdir(parents=True, exist_ok=True)

        templates = [
            [
                project.root / "template.yml",
                self.env.get_template("template.yml"),
                {
                    "resource_type": project.type_name,
                    "handler_params": {
                        "Handler": project.entrypoint,
                        "Runtime": project.runtime,
                        "CodeUri": self.CODE_URI.format(self.package_name),
                        "Timeout": 900,
                    },
                },
            ],
            [
                project.root / self.package_name / "handlers.py",
                self.env.get_template("handlers.py"),
                {},
            ],
            [
                project.root / self.package_name / "__init__.py",
                self.env.get_template("__init__.py"),
                {},
            ],
            [
                project.root / "README.md",
                self.env.get_template("README.md"),
                {
                    "type_name": project.type_name,
                    "schema_path": project.schema_path,
                    "project_path": self.package_name,
                    "executable": EXECUTABLE,
                },
            ],
            [
                project.root / "requirements.txt",
                self.env.get_template("requirements.txt"),
                # until cfn_resource has it's own pypi package, this will need to be
                # updated to point to the absolute path for the src folder in your
                # working copy
                {"cfn_resource_version": self.cfn_resource_version},
            ],
        ]

        for path, template, kwargs in templates:
            LOG.debug("Writing file: %s", path)
            contents = template.render(**kwargs)
            project.safewrite(path, contents)

        LOG.debug("Init complete")

    def generate(self, project):
        LOG.debug("Generate started")

        self._package_from_project(project)
        self._schema_from_project(project)

        shutil.rmtree(project.root / "resource_model", ignore_errors=True)
        os.mkdir(project.root / "resource_model")

        resource_model_path = project.root / "resource_model" / "__init__.py"

        templates = [
            [
                resource_model_path,
                self.env.get_template("resource_model.py"),
                {"properties": project.schema["properties"]},
            ]
        ]

        for path, template, kwargs in templates:
            LOG.debug("Writing file: %s", path)
            contents = template.render(**kwargs)
            project.safewrite(path, contents)

        LOG.debug("Generate complete")

    def package(self, project, zip_file):
        LOG.debug("Package started")

        self._package_from_project(project)

        def write_with_relative_path(path, base=project.root):
            relative = path.relative_to(base)
            zip_file.write(path.resolve(), str(relative))

        resource_model_path = project.root / "resource_model"
        handlers_path = project.root / self.package_name
        deps_path = project.root / "build"

        self._docker_build(project)
        write_with_relative_path(resource_model_path)
        write_with_relative_path(handlers_path)
        write_with_relative_path(deps_path, deps_path)
        LOG.debug("Package complete")

    @classmethod
    def _docker_build(cls, project):
        LOG.debug("Dependencies build started")
        docker_client = docker.from_env()
        volumes = {str(project.root): {"bind": "/project", "mode": "rw"}}
        with open(project.root / "requirements.txt", "r") as f:
            for line in f.readlines():
                if line.startswith("/"):
                    line = line.rstrip("\n")
                    volumes[line] = {"bind": line, "mode": "ro"}
        logs = docker_client.containers.run(
            image="lambci/lambda:build-{}".format(cls.RUNTIME),
            command="pip install --upgrade -r /project/requirements.txt -t "
            "/project/build/",
            auto_remove=True,
            volumes=volumes,
        )
        LOG.debug("pip install logs: \n%s", logs.decode("utf-8"))


class Python37LanguagePlugin(Python36LanguagePlugin):
    NAME = "python37"
    RUNTIME = "python3.7"
