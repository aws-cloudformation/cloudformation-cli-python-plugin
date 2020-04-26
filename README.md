# DEVELOPER PREVIEW

We're excited to share our progress with adding new languages to the CloudFormation CLI! This plugin is an early preview, and not ready for production use.

## AWS CloudFormation Resource Provider Python Plugin

The CloudFormation Resource Provider Development Kit (RPDK) allows you to author your own resource providers that can be used by CloudFormation.

This plugin library helps to provide runtime bindings for the execution of your providers by CloudFormation.

[![Build Status](https://travis-ci.com/aws-cloudformation/cloudformation-cli-python-plugin.svg?branch=master)](https://travis-ci.com/aws-cloudformation/cloudformation-cli-python-plugin)

Installation
------------

Because this is a developer preview, you can't install it from pypi (the version there will not work)
You can still install the plugin using [pip](https://pypi.org/project/pip/) from GitHub.

```bash
pip install git+https://github.com/aws-cloudformation/aws-cloudformation-rpdk-python-plugin.git#egg=cloudformation-cli-python-plugin
```

Howto
-----

The support library, `cloudformation-cli-python-lib` must be packaged and present in the project's directory. Packaging can be done by running the `package_lib.sh` script. Example run:

```
$ cfn init
Initializing new project
What's the name of your resource type?
(Organization::Service::Resource)
>> Foo::Bar::Baz
Select a language for code generation:
[1] java
[2] csharp
[3] python36
[4] python37
(enter an integer):
>> 4
Use docker for platform-independent packaging (Y/n)?
This is highly recommended unless you are experienced
with cross-platform Python packaging.
>> y
Initialized a new project in <>
$ cp ../cloudformation-cli-python-lib-0.0.1.tar.gz .
$ cfn submit --dry-run
$ cat <<EOT > test.json
{
  "credentials": {
    "accessKeyId": "",
    "secretAccessKey": "",
    "sessionToken": ""
  },
  "action": "CREATE",
  "request": {
    "clientRequestToken": "ecba020e-b2e6-4742-a7d0-8a06ae7c4b2b",
    "desiredResourceState": {
      "Title": "This_Is_The_Title_For_My_Example",
      "TestCode": "NOT_STARTED",
      "Description": "bar"
    },
    "previousResourceState": null,
    "logicalResourceIdentifier": null
  },
  "callbackContext": null
}
EOT
$ sam local invoke TestEntrypoint --event test.json
```

Development
-----------

For changes to the plugin, a Python virtual environment is recommended. The development requirements can be sourced from the core repository:

```
python3 -m venv env
source env/bin/activate
pip install -e . -e src/ \
  -r https://raw.githubusercontent.com/aws-cloudformation/aws-cloudformation-rpdk/master/requirements.txt
pre-commit install
```

Linting and running unit tests is done via [pre-commit](https://pre-commit.com/), and so is performed automatically on commit. The continuous integration also runs these checks. Manual options are available so you don't have to commit):

```
# run all hooks on all files, mirrors what the CI runs
pre-commit run --all-files
# run unit tests only. can also be used for other hooks, e.g. black, flake8, pylint-local
pre-commit run pytest-local
```

License
-------

This library is licensed under the Apache 2.0 License.
