# pylint: disable=redefined-outer-name,protected-access
import ast
import importlib.util
from subprocess import CalledProcessError
from unittest.mock import ANY, patch, sentinel
from uuid import uuid4
from zipfile import ZipFile

import pytest

from docker.errors import APIError, ContainerError, ImageLoadError
from requests.exceptions import ConnectionError as RequestsConnectionError
from rpdk.core.exceptions import DownstreamError
from rpdk.core.project import Project
from rpdk.python.codegen import (
    SUPPORT_LIB_NAME,
    SUPPORT_LIB_PKG,
    Python36LanguagePlugin as PythonLanguagePlugin,
    validate_no,
)

TYPE_NAME = "foo::bar::baz"


@pytest.fixture
def plugin():
    return PythonLanguagePlugin()


@pytest.fixture
def project(tmp_path):
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
        project.init(TYPE_NAME, PythonLanguagePlugin.NAME)
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


def test_initialize(project):
    assert project.settings == {"use_docker": False, "protocolVersion": "2.0.0"}

    files = get_files_in_project(project)
    assert set(files) == {
        ".gitignore",
        ".rpdk-config",
        "README.md",
        "foo-bar-baz.json",
        "requirements.txt",
        "example_inputs/inputs_1_invalid.json",
        "example_inputs/inputs_1_update.json",
        "example_inputs/inputs_1_create.json",
        "example_inputs",
        "src",
        "src/foo_bar_baz",
        "src/foo_bar_baz/__init__.py",
        "src/foo_bar_baz/handlers.py",
        "template.yml",
    }

    assert "__pycache__" in files[".gitignore"].read_text()
    assert SUPPORT_LIB_NAME in files["requirements.txt"].read_text()

    readme = files["README.md"].read_text()
    assert project.type_name in readme
    assert SUPPORT_LIB_PKG in readme
    assert "handlers.py" in readme
    assert "models.py" in readme

    assert project.entrypoint in files["template.yml"].read_text()

    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(files["src/foo_bar_baz/__init__.py"].read_text())
    ast.parse(files["src/foo_bar_baz/handlers.py"].read_text())


def test_generate(project):
    project.load_schema()
    before = get_files_in_project(project)
    project.generate()
    after = get_files_in_project(project)
    files = after.keys() - before.keys() - {"resource-role.yaml"}

    assert files == {"src/foo_bar_baz/models.py"}

    models_path = after["src/foo_bar_baz/models.py"]
    # this is a rough check the generated Python code is valid as far as syntax
    ast.parse(models_path.read_text())

    # this however loads the module
    spec = importlib.util.spec_from_file_location("foo_bar_baz.models", models_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module.ResourceModel, "_serialize")
    assert hasattr(module.ResourceModel, "_deserialize")


def test_package_pip(project):
    project.load_schema()
    project.generate()

    # not real requirements, would make version bumps a pain to test
    (project.root / "requirements.txt").write_text("")
    (project.root / f"{SUPPORT_LIB_NAME}-2.1.1.tar.gz").touch()
    # want to exclude *.pyc files from zip, but code isn't run, so never get made
    (project.root / "src" / "foo_bar_baz" / "coverage.pyc").touch()

    zip_path = project.root / "foo-bar-baz.zip"

    with zip_path.open("wb") as f, ZipFile(f, mode="w") as zip_file:
        project._plugin.package(project, zip_file)

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

    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


def test__pip_build_called_process_error(tmp_path):
    patch_cmd = patch.object(
        PythonLanguagePlugin, "_make_pip_command", return_value=["false"]
    )

    with patch_cmd as mock_cmd:
        with pytest.raises(DownstreamError) as excinfo:
            PythonLanguagePlugin._pip_build(tmp_path)

    mock_cmd.assert_called_once_with(tmp_path)

    assert isinstance(excinfo.value.__cause__, CalledProcessError)


def test__build_pip(plugin):
    plugin._use_docker = False

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_docker = patch.object(plugin, "_docker_build", autospec=True)
    with patch_docker as mock_docker, patch_pip as mock_pip:
        plugin._build(sentinel.base_path)

    mock_docker.assert_not_called()
    mock_pip.assert_called_once_with(sentinel.base_path)


def test__build_docker(plugin):
    plugin._use_docker = True

    patch_pip = patch.object(plugin, "_pip_build", autospec=True)
    patch_docker = patch.object(plugin, "_docker_build", autospec=True)
    with patch_docker as mock_docker, patch_pip as mock_pip:
        plugin._build(sentinel.base_path)

    mock_pip.assert_not_called()
    mock_docker.assert_called_once_with(sentinel.base_path)


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
        auto_remove=True,
        volumes={str(tmp_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        user=ANY,
    )


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
        auto_remove=True,
        volumes={str(tmp_path): {"bind": "/project", "mode": "rw"}},
        stream=True,
        user=ANY,
    )
