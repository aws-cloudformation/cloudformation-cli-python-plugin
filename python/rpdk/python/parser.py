def setup_subparser(python_version):
    def setup_version_subparser(subparsers, parents):

        parser = subparsers.add_parser(
            python_version,
            description="""This sub command generates IDE and build files for Python {}
                """.format(
                "3.6" if python_version == "python36" else "3.7"
            ),
            parents=parents,
        )
        parser.set_defaults(language=python_version)

        parser.add_argument(
            "-d",
            "--use-docker",
            action="store_true",
            help="""Use docker for python platform-independent packaging.
                This is highly recommended unless you are experienced
                with cross-platform Python packaging.""",
        )

        return parser

    return setup_version_subparser


def setup_subparser_python36(subparsers, parents):
    return setup_subparser("python36")(subparsers, parents)


def setup_subparser_python37(subparsers, parents):
    return setup_subparser("python37")(subparsers, parents)
