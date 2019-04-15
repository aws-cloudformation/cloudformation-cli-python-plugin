# pylint: disable=useless-super-delegation,too-many-locals
# pylint doesn't recognize abstract methods
import logging
import shutil

from rpdk.core.jsonutils.flattener import JsonSchemaFlattener
from rpdk.core.plugin_base import LanguagePlugin

LOG = logging.getLogger(__name__)

OPERATIONS = ("Create", "Read", "Update", "Delete", "List")
EXECUTABLE = "uluru-cli"


class PythonLanguagePlugin(LanguagePlugin):
    MODULE_NAME = __name__
    NAME = "python"
    RUNTIME = "python3.7"
    ENTRY_POINT = "{}.handler_wrapper"
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

        # maven folder structure
        src = project.root / self.package_name
        LOG.debug("Making source folder structure: %s", src)
        src.mkdir(parents=True, exist_ok=True)
        tst = project.root / "tests"
        LOG.debug("Making test folder structure: %s", tst)
        tst.mkdir(parents=True, exist_ok=True)

        artifact_id = "{}-handler".format(project.hypenated_name)

        # CloudFormation/SAM template for handler lambda
        path = project.root / "Handler.yaml"
        LOG.debug("Writing SAM template: %s", path)
        template = self.env.get_template("Handler.yaml")
        contents = template.render(
            resource_type=project.type_name,
            handler_params={
                "Handler": self.ENTRY_POINT.format(self.package_name),
                "Runtime": self.RUNTIME,
                "CodeUri": self.CODE_URI.format(artifact_id),
            },
        )
        project.safewrite(path, contents)

        template = self.env.get_template("stub_handler.py")
        for operation in OPERATIONS:
            path = src / "{}.py".format(operation.lower())
            LOG.debug("%s handler: %s", operation, path)
            contents = template.render(
                package_name=self.package_name,
                operation=operation,
            )
            project.safewrite(path, contents)

        path = project.root / "README.md"
        LOG.debug("Writing README: %s", path)
        template = self.env.get_template("README.md")
        contents = template.render(
            type_name=project.type_name,
            schema_path=project.schema_path,
            executable=EXECUTABLE,
        )
        project.safewrite(path, contents)

        LOG.debug("Init complete")

    @staticmethod
    def _get_generated_root(project):
        return project.root / "target" / "generated-sources" / "rpdk"

    def generate(self, project):
        LOG.debug("Generate started")

        self._package_from_project(project)

        generated_root = self._get_generated_root(project)
        LOG.debug("Removing generated sources: %s", generated_root)
        shutil.rmtree(generated_root, ignore_errors=True)

        src = generated_root.joinpath(*self.namespace)
        LOG.debug("Making generated folder structure: %s", src)
        src.mkdir(parents=True, exist_ok=True)

        LOG.debug("Generate complete")

    def package(self, project):
        pass
