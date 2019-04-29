import logging
import shutil
from pip._internal import main as pip
import os
import rpdk.python as pyrpdk
from rpdk.core.plugin_base import LanguagePlugin

LOG = logging.getLogger(__name__)

EXECUTABLE = "uluru-cli"


class PythonLanguagePlugin(LanguagePlugin):
    MODULE_NAME = __name__
    NAME = "python"
    RUNTIME = "python3.7"
    ENTRY_POINT = "cfn_resource._handler_wrapper"
    CODE_URI = "./target/{}.zip"

    def __init__(self):
        self.env = self._setup_jinja_env(
            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
        )
        self.package_name = None

    def _package_from_project(self, project):
        self.namespace = tuple(s.lower() for s in project.type_info)
        self.package_name = "_".join(self.namespace)

    def init(self, project):
        LOG.debug("Init started")

        self._package_from_project(project)

        folders = [project.root / self.package_name, project.root / "tests"]

        for f in folders:
            LOG.debug("Making folder: %s", f)
            f.mkdir(parents=True, exist_ok=True)

        templates = [
            [
                project.root / "Handler.yaml",
                self.env.get_template("Handler.yaml"),
                {
                    'resource_type': project.type_name,
                    'handler_params': {
                        "Handler": self.ENTRY_POINT,
                        "Runtime": self.RUNTIME,
                        "CodeUri": self.CODE_URI.format(self.package_name),
                    }
                }
            ],
            [
                project.root / self.package_name / "__handler__.py",
                self.env.get_template("__handler__.py"),
                {'package_name': self.package_name}
            ],
            [
                project.root / "README.md",
                self.env.get_template("README.md"),
                {
                    'type_name': project.type_name,
                    'schema_path': project.schema_path,
                    'executable': EXECUTABLE
                }
            ]
        ]

        for path, template, kwargs in templates:
            LOG.debug("Writing file: %s", path)
            contents = template.render(**kwargs)
            project.safewrite(path, contents)

        LOG.debug("Init complete")

    def generate(self, project):
        LOG.debug("Generate started")

        self._package_from_project(project)

        project_path = project.root / self.package_name
        cfn_resource_path = project_path / "cfn_resource"

        LOG.debug("Removing python rpdk package: %s", cfn_resource_path)
        shutil.rmtree(cfn_resource_path, ignore_errors=True)
        # cleanup .egg-info dir
        for p in os.listdir(project_path):
            if p.startswith('cfn_resource-') and p.endswith('.egg-info'):
                shutil.rmtree(project_path / p)

        LOG.debug("Installing python rpdk package into: %s", project_path)
        dest_path = os.path.join(pyrpdk.__path__[0], "cfn_resource")
        pip(['--log', './rpdk.log', '-qqq', 'install', '-t', str(project_path), dest_path])

        LOG.debug("Generate complete")

    def package(self, project):
        pass
