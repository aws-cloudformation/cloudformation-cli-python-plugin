from setuptools import setup

setup(
    name="cfn_resource",
    version="0.0.1",
    description="cfn_resource enables python based CloudFormation resource types",
    author="Jay McConnell",
    author_email="jmmccon@amazon.com",
    license="Apache2",
    packages=["cfn_resource"],
    install_requires=["boto3>=1.9.108,<1.10"],
    tests_require=[],
    test_suite="tests",
    classifiers=[
        'Programming Language :: Python :: 3.7',
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
