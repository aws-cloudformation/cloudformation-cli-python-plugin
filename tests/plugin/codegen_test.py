# pylint: disable=redefined-outer-name,protected-access
import pytest

import ast
import importlib.util
import os
from docker.errors import APIError, ContainerError, ImageLoadError
from pathlib import Path
from requests.exceptions import ConnectionError as RequestsConnectionError
from rpdk.core.exceptions import DownstreamError
from rpdk.core.project import Project
from rpdk.python.__init__ import __version__
from rpdk.python.codegen import (
    SUPPORT_LIB_NAME,
    SUPPORT_LIB_PKG,
    _PythonLanguagePlugin as PythonLanguagePlugin,
    validate_no,
)
from shutil import copyfile
from subprocess import CalledProcessError
from unittest.mock import ANY, patch, sentinel
from uuid import uuid4
from zipfile import ZipFile

TYPE_NAME = "foo::bar::baz"

TEST_TARGET_INFO = {
    "My::Example::Resource": {
        "TargetName": "My::Example::Resource",
        "TargetType": "RESOURCE",
        "Schema": {
            "typeName": "My::Example::Resource",
            "additionalProperties": False,
            "properties": {
                "Id": {"type": "string"},
                "Tags": {
                    "type": "array",
                    "uniqueItems": False,
                    "items": {"$ref": "#/definitions/Tag"},
                },
            },
            "required": [],
            "definitions": {
                "Tag": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "Value": {"type": "string"},
                        "Key": {"type": "string"},
                    },
                    "required": ["Value", "Key"],
                }
            },
        },
        "ProvisioningType": "FULLY_MUTTABLE",
        "IsCfnRegistrySupportedType": True,
        "SchemaFileAvailable": True,
    },
    "My::Other::Resource": {
        "TargetName": "My::Other::Resource",
        "TargetType": "RESOURCE",
        "Schema": {
            "typeName": "My::Other::Resource",
            "additionalProperties": False,
            "properties": {
                "Id": {"type": "string"},
                "Tags": {
                    "type": "array",
                    "uniqueItems": False,
                    "items": {"$ref": "#/definitions/Tag"},
                },
            },
            "required": [],
            "definitions": {
                "Tag": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "Value": {"type": "string"},
                        "Key": {"type": "string"},
                    },
                    "required": ["Value", "Key"],
                }
            },
        },
        "ProvisioningType": "NOT_PROVISIONABLE",
        "IsCfnRegistrySupportedType": False,
        "SchemaFileAvailable": True,
    },
}


@pytest.fixture
def plugin():
    return PythonLanguagePlugin()


@pytest.fixture
def resource_project(tmp_path):
    project = Project(root=tmp_path)

    patch_plugins = patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {PythonLanguagePlugin.NAME: lambda: PythonLanguagePlugin},
        clear=True,
    )
    patch_wizard = patch(
        "rpdk.python.codegen.input_with_validation", autospec=True, side_effect=[False]
    )
    with patch_plugins, patch_wizard:
        project.init(
            TYPE_NAME,
            PythonLanguagePlugin.NAME,
            settings={"use_docker": False, "no_docker": True},
        )
    return project


@pytest.fixture
def resource_project_use_docker(tmp_path):
    project = Project(root=tmp_path)

    patch_plugins = patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {PythonLanguagePlugin.NAME: lambda: PythonLanguagePlugin},
        clear=True,
    )
    patch_wizard = patch(
        "rpdk.python.codegen.input_with_validation", autospec=True, side_effect=[False]
    )
    with patch_plugins, patch_wizard:
        project.init(
            TYPE_NAME,
            PythonLanguagePlugin.NAME,
            settings={"use_docker": True, "no_docker": False},
        )
    return project


@pytest.fixture
def hook_project(tmp_path):
    project = Project(root=tmp_path)

    patch_plugins = patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {PythonLanguagePlugin.NAME: lambda: PythonLanguagePlugin},
        clear=True,
    )
    patch_wizard = patch(
        "rpdk.python.codegen.input_with_validation", autospec=True, side_effect=[False]
    )
    with patch_plugins, patch_wizard:
        project.init_hook(
            TYPE_NAME,
            PythonLanguagePlugin.NAME,
            settings={"use_docker": False, "no_docker": True},
        )
    return project


@pytest.fixture
def hook_project_use_docker(tmp_path):
    project = Project(root=tmp_path)

    patch_plugins = patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {PythonLanguagePlugin.NAME: lambda: PythonLanguagePlugin},
        clear=True,
    )
    patch_wizard = patch(
        "rpdk.python.codegen.input_with_validation", autospec=True, side_effect=[False]
    )
    with patch_plugins, patch_wizard:
        project.init_hook(
            TYPE_NAME,
            PythonLanguagePlugin.NAME,
            settings={"use_docker": True, "no_docker": False},
        )
    return project


def get_files_in_project(project):
    return {
        str(child.relative_to(project.root)): child for child in project.root.rglob("*")
    }


@pytest.mark.parametrize(
    "value,result",
    [
        ("y", True),
        ("Y", True),
        ("yes", True),
        ("Yes", True),
        ("YES", True),
        ("asdf", True),
        ("no", False),
        ("No", False),
        ("No", False),
        ("n", False),
        ("N", False),
    ],
)
def test_validate_no(value, result):
    assert validate_no(value) is result


def test__remove_build_artifacts_file_found(tmp_path):
    deps_path = tmp_path / "build"
    deps_path.mkdir()
    PythonLanguagePlugin._remove_build_artifacts(deps_path)


def test__remove_build_artifacts_file_not_found(tmp_path):
    deps_path = tmp_path / "build"
    with patch("rpdk.python.codegen.LOG", autospec=True) as mock_log:
        PythonLanguagePlugin._remove_build_artifacts(deps_path)

    mock_log.debug.assert_called_once()


def test_initialize_resource(resource_project):
    assert resource_project.settings == {
        "use_docker": False,
        "no_docker": True,
        "protocolVersion": "2.0.0",
    }

    files = get_files_in_project(resource_project)
    assert set(files) == {
        ".gitignore",
        ".rpdk-config",
        "README.md",
        "foo-bar-baz.json",
        "requirements.txt",
        f"{os.path.join('example_inputs', 'inputs_1_create.json')}",
        f"{os.path.join('example_inputs', 'inputs_1_invalid.json')}",
        f"{os.path.join('example_inputs', 'inputs_1_update.json')}",
        "example_inputs",
        "src",
        f"{os.path.join('src', 'foo_bar_baz')}",
        f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}",
        f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}",
        "template.yml",
    }

    assert "__pycache__" in files[".gitignore"].read_text()
    assert SUPPORT_LIB_NAME in files["requirements.txt"].read_text()

    readme = files["README.md"].read_text()
    assert resource_project.type_name in readme
    assert SUPPORT_LIB_PKG in readme
    assert "handlers.py" in readme
    assert "models.py" in readme

    assert resource_project.entrypoint in files["template.yml"].read_text()

    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}"].read_text())
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}"].read_text())


def test_initialize_resource_use_docker(resource_project_use_docker):
    assert resource_project_use_docker.settings == {
        "use_docker": True,
        "no_docker": False,
        "protocolVersion": "2.0.0",
    }

    files = get_files_in_project(resource_project_use_docker)
    assert set(files) == {
        ".gitignore",
        ".rpdk-config",
        "README.md",
        "foo-bar-baz.json",
        "requirements.txt",
        f"{os.path.join('example_inputs', 'inputs_1_create.json')}",
        f"{os.path.join('example_inputs', 'inputs_1_invalid.json')}",
        f"{os.path.join('example_inputs', 'inputs_1_update.json')}",
        "example_inputs",
        "src",
        f"{os.path.join('src', 'foo_bar_baz')}",
        f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}",
        f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}",
        "template.yml",
    }

    assert "__pycache__" in files[".gitignore"].read_text()
    assert SUPPORT_LIB_NAME in files["requirements.txt"].read_text()

    readme = files["README.md"].read_text()
    assert resource_project_use_docker.type_name in readme
    assert SUPPORT_LIB_PKG in readme
    assert "handlers.py" in readme
    assert "models.py" in readme

    assert resource_project_use_docker.entrypoint in files["template.yml"].read_text()

    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}"].read_text())
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}"].read_text())


def test_initialize_hook(hook_project):
    assert hook_project.settings == {
        "use_docker": False,
        "no_docker": True,
        "protocolVersion": "2.0.0",
    }

    files = get_files_in_project(hook_project)
    assert set(files) == {
        ".gitignore",
        ".rpdk-config",
        "README.md",
        "foo-bar-baz.json",
        "requirements.txt",
        "src",
        f"{os.path.join('src', 'foo_bar_baz')}",
        f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}",
        f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}",
        "template.yml",
    }

    assert "__pycache__" in files[".gitignore"].read_text()
    assert SUPPORT_LIB_NAME in files["requirements.txt"].read_text()

    readme = files["README.md"].read_text()
    assert hook_project.type_name in readme
    assert SUPPORT_LIB_PKG in readme
    assert "handlers.py" in readme
    assert "models.py" in readme

    assert hook_project.entrypoint in files["template.yml"].read_text()

    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}"].read_text())
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}"].read_text())


def test_initialize_hook_use_docker(hook_project_use_docker):
    assert hook_project_use_docker.settings == {
        "use_docker": True,
        "no_docker": False,
        "protocolVersion": "2.0.0",
    }

    files = get_files_in_project(hook_project_use_docker)
    assert set(files) == {
        ".gitignore",
        ".rpdk-config",
        "README.md",
        "foo-bar-baz.json",
        "requirements.txt",
        "src",
        f"{os.path.join('src', 'foo_bar_baz')}",
        f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}",
        f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}",
        "template.yml",
    }

    assert "__pycache__" in files[".gitignore"].read_text()
    assert SUPPORT_LIB_NAME in files["requirements.txt"].read_text()

    readme = files["README.md"].read_text()
    assert hook_project_use_docker.type_name in readme
    assert SUPPORT_LIB_PKG in readme
    assert "handlers.py" in readme
    assert "models.py" in readme

    assert hook_project_use_docker.entrypoint in files["template.yml"].read_text()

    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', '__init__.py')}"].read_text())
    ast.parse(files[f"{os.path.join('src', 'foo_bar_baz', 'handlers.py')}"].read_text())


def test_generate_resource(resource_project):
    resource_project.load_schema()
    before = get_files_in_project(resource_project)
    resource_project.generate()
    after = get_files_in_project(resource_project)
    files = after.keys() - before.keys() - {"resource-role.yaml"}
    print("Project files: ", get_files_in_project(resource_project))
    assert files == {f"{os.path.join('src', 'foo_bar_baz', 'models.py')}"}

    models_path = after[f"{os.path.join('src', 'foo_bar_baz', 'models.py')}"]
    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(models_path.read_text())

    # this however loads the module
    spec = importlib.util.spec_from_file_location("foo_bar_baz.models", models_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module.ResourceModel, "_serialize")
    assert hasattr(module.ResourceModel, "_deserialize")
    assert hasattr(module.TypeConfigurationModel, "_serialize")
    assert hasattr(module.TypeConfigurationModel, "_deserialize")

    type_configuration_schema_file = (
        resource_project.root / "foo-bar-baz-configuration.json"
    )
    assert not type_configuration_schema_file.is_file()


def test_generate_hook(hook_project):
    with patch.object(hook_project, "_load_target_info", return_value=TEST_TARGET_INFO):
        hook_project.load_hook_schema()
        hook_project.load_configuration_schema()
        before = get_files_in_project(hook_project)
        hook_project.generate()
    after = get_files_in_project(hook_project)
    files = after.keys() - before.keys() - {"hook-role.yaml"}
    print("Project files: ", get_files_in_project(hook_project))
    assert files == {
        f"{os.path.join('src', 'foo_bar_baz', 'models.py')}",
        f"{os.path.join('src', 'foo_bar_baz', 'target_models')}",
        f"{os.path.join('src', 'foo_bar_baz', 'target_models', 'my_example_resource.py')}",  # noqa: B950 pylint: disable=line-too-long
        f"{os.path.join('src', 'foo_bar_baz', 'target_models', 'my_other_resource.py')}",  # noqa: B950 pylint: disable=line-too-long
        "foo-bar-baz-configuration.json",
    }

    models_path = after[f"{os.path.join('src', 'foo_bar_baz', 'models.py')}"]
    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(models_path.read_text())

    # this however loads the module
    spec = importlib.util.spec_from_file_location("foo_bar_baz.models", models_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module.TypeConfigurationModel, "_serialize")
    assert hasattr(module.TypeConfigurationModel, "_deserialize")

    type_configuration_schema_file = (
        hook_project.root / "foo-bar-baz-configuration.json"
    )
    assert type_configuration_schema_file.is_file()


def test_generate_resource_with_type_configuration(tmp_path):
    type_name = "schema::with::typeconfiguration"
    project = Project(root=tmp_path)

    patch_plugins = patch.dict(
        "rpdk.core.plugin_registry.PLUGIN_REGISTRY",
        {PythonLanguagePlugin.NAME: lambda: PythonLanguagePlugin},
        clear=True,
    )
    patch_wizard = patch(
        "rpdk.python.codegen.input_with_validation", autospec=True, side_effect=[False]
    )
    with patch_plugins, patch_wizard:
        project.init(type_name, PythonLanguagePlugin.NAME)

    copyfile(
        str(
            Path.cwd()
            / f"{os.path.join('tests', 'data', 'schema-with-typeconfiguration.json')}"
        ),
        str(project.root / "schema-with-typeconfiguration.json"),
    )
    project.type_info = ("schema", "with", "typeconfiguration")
    project.load_schema()
    project.load_configuration_schema()
    project.generate()

    # assert TypeConfigurationModel is added to generated directory
    models_path = project.root / "src" / "schema_with_typeconfiguration" / "models.py"

    # this however loads the module
    spec = importlib.util.spec_from_file_location("foo_bar_baz.models", models_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module.ResourceModel, "_serialize")
    assert hasattr(module.ResourceModel, "_deserialize")
    assert hasattr(module.TypeConfigurationModel, "_serialize")
    assert hasattr(module.TypeConfigurationModel, "_deserialize")

    type_configuration_schema_file = (
        project.root / "schema-with-typeconfiguration-configuration.json"
    )
    assert type_configuration_schema_file.is_file()


def test_package_resource_pip(resource_project):
    resource_project.load_schema()
    resource_project.generate()

    # not real requirements, would make version bumps a pain to test
    (resource_project.root / "requirements.txt").write_text("")
    (resource_project.root / f"{SUPPORT_LIB_NAME}-2.1.1.tar.gz").touch()
    # want to exclude *.pyc files from zip, but code isn't run, so never get made
    (resource_project.root / "src" / "foo_bar_baz" / "coverage.pyc").touch()

    zip_path = resource_project.root / "foo-bar-baz.zip"

    with zip_path.open("wb") as f, ZipFile(f, mode="w") as zip_file:
        resource_project._plugin.package(resource_project, zip_file)

    with zip_path.open("rb") as f, ZipFile(f, mode="r") as zip_file:
        assert sorted(zip_file.namelist()) == [
            "ResourceProvider.zip",
            "src/foo_bar_baz/__init__.py",
            "src/foo_bar_baz/handlers.py",
            "src/foo_bar_baz/models.py",
        ]


def test__pip_build_executable_not_found(tmp_path):
    executable_name = str(uuid4())
    patch_cmd = patch.object(
        PythonLanguagePlugin, "_make_pip_command", return_value=[executable_name]
    )

    with patch_cmd as mock_cmd:
        with pytest.raises(DownstreamError) as excinfo:
            PythonLanguagePlugin._pip_build(tmp_path)

    mock_cmd.assert_called_once_with(tmp_path)

    # FileNotFoundError raised on Windows, CalledProcessError on POSIX systems
    assert isinstance(excinfo.value.__cause__, (FileNotFoundError, CalledProcessError))


def test__pip_build_called_process_error(tmp_path):
    patch_cmd = patch.object(
        PythonLanguagePlugin, "_make_pip_command", return_value=["false"]
    )

    with patch_cmd as mock_cmd:
        with pytest.raises(DownstreamError) as excinfo:
            PythonLanguagePlugin._pip_build(tmp_path)

    mock_cmd.assert_called_once_with(tmp_path)

    # FileNotFoundError raised on Windows, CalledProcessError on POSIX systems
    assert isinstance(excinfo.value.__cause__, (FileNotFoundError, CalledProcessError))


def test__build_pip(plugin):
    plugin._use_docker = False
    plugin._no_docker = True

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_docker = patch.object(plugin, "_docker_build", autospec=True)
    with patch_docker as mock_docker, patch_pip as mock_pip:
        plugin._build(sentinel.base_path)

    mock_docker.assert_not_called()
    mock_pip.assert_called_once_with(sentinel.base_path)


def test__build_pip_posix(plugin):
    patch_os_name = patch("rpdk.python.codegen.os.name", "posix")
    patch_subproc = patch("rpdk.python.codegen.subprocess_run")

    # Path must be set outside simulated os.name
    temppath = Path(str(sentinel.base_path))
    with patch_os_name, patch_subproc as mock_subproc:
        plugin._pip_build(temppath)

    mock_subproc.assert_called_once_with(
        plugin._make_pip_command(temppath),
        stdout=ANY,
        stderr=ANY,
        cwd=temppath,
        check=ANY,
    )


def test__build_pip_windows(plugin):
    patch_os_name = patch("rpdk.python.codegen.os.name", "nt")
    patch_subproc = patch("rpdk.python.codegen.subprocess_run")

    # Path must be set outside simulated os.name
    temppath = Path(str(sentinel.base_path))
    with patch_os_name, patch_subproc as mock_subproc:
        plugin._pip_build(temppath)

    mock_subproc.assert_called_once_with(
        plugin._make_pip_command(temppath),
        stdout=ANY,
        stderr=ANY,
        cwd=temppath,
        check=ANY,
        shell=True,
    )


def test__build_docker(plugin):
    plugin._use_docker = True
    plugin._no_docker = False

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_docker = patch.object(plugin, "_docker_build", autospec=True)
    with patch_docker as mock_docker, patch_pip as mock_pip:
        plugin._build(sentinel.base_path)

    mock_pip.assert_not_called()
    mock_docker.assert_called_once_with(sentinel.base_path)


# Test _build_docker on Linux/Unix-like systems
def test__build_docker_posix(plugin):
    plugin._use_docker = True
    plugin._no_docker = False

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_from_env = patch("rpdk.python.codegen.docker.from_env", autospec=True)
    patch_os_name = patch("rpdk.python.codegen.os.name", "posix")

    with patch_pip as mock_pip, patch_from_env as mock_from_env:
        mock_run = mock_from_env.return_value.containers.run
        with patch_os_name:
            plugin._build(sentinel.base_path)

    mock_pip.assert_not_called()
    mock_run.assert_called_once_with(
        image=ANY,
        command=ANY,
        remove=True,
        volumes={str(sentinel.base_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        entrypoint="",
        user=ANY,
        platform="linux/amd64",
    )


# Test _build_docker on Windows
def test__build_docker_windows(plugin):
    plugin._use_docker = True
    plugin._no_docker = False

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_from_env = patch("rpdk.python.codegen.docker.from_env", autospec=True)
    patch_os_name = patch("rpdk.python.codegen.os.name", "nt")

    with patch_pip as mock_pip, patch_from_env as mock_from_env:
        mock_run = mock_from_env.return_value.containers.run
        with patch_os_name:
            plugin._build(sentinel.base_path)

    mock_pip.assert_not_called()
    mock_run.assert_called_once_with(
        image=ANY,
        command=ANY,
        remove=True,
        volumes={str(sentinel.base_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        entrypoint="",
        user="root:root",
        platform="linux/amd64",
    )


# Test _build_docker if geteuid fails
def test__build_docker_no_euid(plugin):
    plugin._use_docker = True
    plugin._no_docker = False

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_from_env = patch("rpdk.python.codegen.docker.from_env", autospec=True)
    # os.geteuid does not exist on Windows so we can not autospec os
    patch_os = patch("rpdk.python.codegen.os")
    patch_os_name = patch("rpdk.python.codegen.os.name", "posix")

    with patch_pip as mock_pip, patch_from_env as mock_from_env, patch_os as mock_patch_os:  # noqa: B950 pylint: disable=line-too-long
        mock_run = mock_from_env.return_value.containers.run
        mock_patch_os.geteuid.side_effect = AttributeError()
        with patch_os_name:
            plugin._build(sentinel.base_path)

    mock_pip.assert_not_called()
    mock_run.assert_called_once_with(
        image=ANY,
        command=ANY,
        remove=True,
        volumes={str(sentinel.base_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        entrypoint="",
        user="root:root",
        platform="linux/amd64",
    )


def test__docker_build_good_path(plugin, tmp_path):
    patch_from_env = patch("rpdk.python.codegen.docker.from_env", autospec=True)

    with patch_from_env as mock_from_env:
        mock_run = mock_from_env.return_value.containers.run
        mock_run.return_value = [b"output\n\n"]
        plugin._docker_build(tmp_path)

    mock_from_env.assert_called_once_with()
    mock_run.assert_called_once_with(
        image=ANY,
        command=ANY,
        remove=True,
        volumes={str(tmp_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        entrypoint="",
        user=ANY,
        platform="linux/amd64",
    )


def test_get_plugin_information(resource_project):
    plugin_information = resource_project._plugin.get_plugin_information(
        resource_project
    )

    assert plugin_information["plugin-tool-version"] == __version__
    assert plugin_information["plugin-name"] == "python"


@pytest.mark.parametrize(
    "exception",
    [
        lambda: ContainerError("abcde", 255, "/bin/false", "image", ""),
        ImageLoadError,
        lambda: APIError("500"),
        lambda: RequestsConnectionError(
            "Connection aborted.", ConnectionRefusedError(61, "Connection refused")
        ),
    ],
)
def test__docker_build_bad_path(plugin, tmp_path, exception):
    patch_from_env = patch("rpdk.python.codegen.docker.from_env", autospec=True)

    with patch_from_env as mock_from_env:
        mock_run = mock_from_env.return_value.containers.run
        mock_run.side_effect = exception()

        with pytest.raises(DownstreamError):
            plugin._docker_build(tmp_path)

    mock_from_env.assert_called_once_with()
    mock_run.assert_called_once_with(
        image=ANY,
        command=ANY,
        remove=True,
        volumes={str(tmp_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        entrypoint="",
        user=ANY,
        platform="linux/amd64",
    )
