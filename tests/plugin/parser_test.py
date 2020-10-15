import argparse

from rpdk.python.parser import setup_subparser_python36, setup_subparser_python37


def test_setup_subparser_python36():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python36(subparsers, [])

    args = sub_parser.parse_args(["-d"])

    assert args.language == "python36"
    assert args.use_docker is True


def test_setup_subparser_python37():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name")

    sub_parser = setup_subparser_python37(subparsers, [])

    args = sub_parser.parse_args([])

    assert args.language == "python37"
    assert args.use_docker is False
