import pytest

import argparse
from rpdk.python.parser import (
    setup_subparser_python36,
    setup_subparser_python37,
    setup_subparser_python38,
    setup_subparser_python39,
)


def test_setup_subparser_python36():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python36(subparsers, [])

    args = sub_parser.parse_args([])

    assert args.language == "python36"
    assert args.use_docker is False
    assert args.no_docker is False

    short_args = sub_parser.parse_args(["-d"])
    assert short_args.language == "python36"
    assert short_args.use_docker is True
    assert short_args.no_docker is False

    long_args = sub_parser.parse_args(["--use-docker"])
    assert long_args.language == "python36"
    assert long_args.use_docker is True
    assert long_args.no_docker is False

    no_docker = sub_parser.parse_args(["--no-docker"])
    assert no_docker.language == "python36"
    assert no_docker.use_docker is False
    assert no_docker.no_docker is True

    with pytest.raises(SystemExit):
        sub_parser.parse_args(["--no-docker", "--use-docker"])


def test_setup_subparser_python37():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python37(subparsers, [])

    args = sub_parser.parse_args([])

    assert args.language == "python37"
    assert args.use_docker is False
    assert args.no_docker is False

    short_args = sub_parser.parse_args(["-d"])
    assert short_args.language == "python37"
    assert short_args.use_docker is True
    assert short_args.no_docker is False

    long_args = sub_parser.parse_args(["--use-docker"])
    assert long_args.language == "python37"
    assert long_args.use_docker is True
    assert long_args.no_docker is False

    no_docker = sub_parser.parse_args(["--no-docker"])
    assert no_docker.language == "python37"
    assert no_docker.use_docker is False
    assert no_docker.no_docker is True

    with pytest.raises(SystemExit):
        sub_parser.parse_args(["--no-docker", "--use-docker"])


def test_setup_subparser_python38():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python38(subparsers, [])

    args = sub_parser.parse_args([])

    assert args.language == "python38"
    assert args.use_docker is False
    assert args.no_docker is False

    short_args = sub_parser.parse_args(["-d"])
    assert short_args.language == "python38"
    assert short_args.use_docker is True
    assert short_args.no_docker is False

    long_args = sub_parser.parse_args(["--use-docker"])
    assert long_args.language == "python38"
    assert long_args.use_docker is True
    assert long_args.no_docker is False

    no_docker = sub_parser.parse_args(["--no-docker"])
    assert no_docker.language == "python38"
    assert no_docker.use_docker is False
    assert no_docker.no_docker is True

    with pytest.raises(SystemExit):
        sub_parser.parse_args(["--no-docker", "--use-docker"])


def test_setup_subparser_python39():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python39(subparsers, [])

    args = sub_parser.parse_args([])

    assert args.language == "python39"
    assert args.use_docker is False
    assert args.no_docker is False

    short_args = sub_parser.parse_args(["-d"])
    assert short_args.language == "python39"
    assert short_args.use_docker is True
    assert short_args.no_docker is False

    long_args = sub_parser.parse_args(["--use-docker"])
    assert long_args.language == "python39"
    assert long_args.use_docker is True
    assert long_args.no_docker is False

    no_docker = sub_parser.parse_args(["--no-docker"])
    assert no_docker.language == "python39"
    assert no_docker.use_docker is False
    assert no_docker.no_docker is True

    with pytest.raises(SystemExit):
        sub_parser.parse_args(["--no-docker", "--use-docker"])
