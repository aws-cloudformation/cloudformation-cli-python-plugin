from cfn_resource import (
    Boto3SessionProxy as BotoProxy,
    ProgressEvent as Progress,
    RequestContext as Context,
    Status,
    exceptions,
)
from resource_model import ResourceModel as Model


def create_handler(model: Model, callback: dict, context: Context, boto3: BotoProxy):
    progress = Progress(status=Status.IN_PROGRESS, resourceModel=model)
    # TODO: put code here

    # Example:
    try:
        # Setting Status to success will signal to cfn that the operation is complete
        progress.status = Status.SUCCESS
    except TypeError as e:
        # exceptions module lets CloudFormation know the type of failure that occurred
        raise exceptions.InternalFailure(f"was not expecting type {e}")
        # this can also be done by setting progress.status, errorCode and message:
        # progress.status = Status.FAILED
        # progress.errorCode = exceptions.Codes.INTERNAL_FAILURE
        # progress.message = f"was not expecting type {e}"
    return progress


def update_handler(model: Model, callback: dict, context: Context, boto3: BotoProxy):
    progress = Progress(status=Status.IN_PROGRESS, resourceModel=model)
    # TODO: put code here
    return progress


def delete_handler(model: Model, callback: dict, context: Context, boto3: BotoProxy):
    progress = Progress(status=Status.IN_PROGRESS, resourceModel=model)
    # TODO: put code here
    return progress


def read_handler(model: Model, callback: dict, context: Context, boto3: BotoProxy):
    progress = Progress(status=Status.IN_PROGRESS, resourceModel=model)
    # TODO: put code here
    return progress


def list_handler(model: Model, callback: dict, context: Context, boto3: BotoProxy):
    progress = Progress(status=Status.IN_PROGRESS, resourceModel=model)
    # TODO: put code here
    return progress
