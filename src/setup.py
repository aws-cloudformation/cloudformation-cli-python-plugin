"""Support library to enable Python-based CloudFormation resource types"""
from setuptools import setup

setup(
    name="aws-cloudformation-rpdk-python-lib",
    version="0.0.1",
    description=__doc__,
    author="Amazon Web Services",
    packages=["aws_cloudformation_rpdk_python_lib"],
    # package_data -> use MANIFEST.in instead
    include_package_data=True,
    zip_safe=True,
    install_requires=["boto3>=1.9.108,<1.10", 'dataclasses;python_version<"3.7"'],
    license="Apache License 2.0",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Code Generators",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="Amazon Web Services AWS CloudFormation",
)
