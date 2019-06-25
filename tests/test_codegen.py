# fixture and parameter have the same name
# pylint: disable=redefined-outer-name,protected-access

from unittest.mock import patch

import pytest
import yaml

from rpdk.core.project import Project
from rpdk.python.codegen import Python36LanguagePlugin

RESOURCE = "DZQWCC"


@pytest.fixture
def project(tmpdir):
    project = Project(root=tmpdir)
    with patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {"test": lambda: Python36LanguagePlugin},
        clear=True,
    ):
        project.init("AWS::Foo::{}".format(RESOURCE), "test")
    return project


def test_python_language_plugin_module_is_set():
    plugin = Python36LanguagePlugin()
    assert plugin.MODULE_NAME


def test_initialize(project):
    assert (project.root / "README.md").is_file()

    path = project.root / "template.yml"
    with path.open("r", encoding="utf-8") as f:
        template = yaml.safe_load(f)

    handler_properties = template["Resources"]["TypeFunction"]["Properties"]

    code_uri = "./target/{}.zip".format(project.hypenated_name.replace("-", "_"))
    assert handler_properties["CodeUri"] == code_uri
    handler = "cfn_resource.handler_wrapper._handler_wrapper"
    assert handler_properties["Handler"] == handler
    assert handler_properties["Runtime"] == project._plugin.RUNTIME


def test_generate(project):
    project.load_schema()

    project.generate()

    test_file = project.root / "resource_model" / "test"
    test_file.touch()

    project.generate()

    # asserts we remove existing files in the tree
    assert not test_file.is_file()


def make_target(project, count):
    target = project.root / "target"
    target.mkdir(exist_ok=True)
    jar_paths = []
    for i in range(count):
        jar_path = target / "{}-{}.0-SNAPSHOT.jar".format(project.hypenated_name, i)
        jar_path.touch()
        jar_paths.append(jar_path)
    return jar_paths
