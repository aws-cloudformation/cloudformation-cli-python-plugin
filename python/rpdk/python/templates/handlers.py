from resource_model import ResourceModel
from cfn_resource import Boto3SessionProxy
from cfn_resource import RequestContext, ProgressEvent, Status
from cfn_resource import exceptions


def create_handler(resource_model: ResourceModel, callback_context: dict, handler_context: RequestContext,
                   boto3: Boto3SessionProxy):
    progress_event = ProgressEvent(status=Status.IN_PROGRESS, resourceModel=resource_model)
    # TODO: put code here
    return progress_event


def update_handler(resource_model: ResourceModel, previous_resource_model: ResourceModel, callback_context: dict,
                   handler_context: RequestContext, boto3: Boto3SessionProxy):
    progress_event = ProgressEvent(status=Status.IN_PROGRESS, resourceModel=resource_model)
    # TODO: put code here
    return progress_event


def delete_handler(resource_model: ResourceModel, callback_context: dict, handler_context: RequestContext,
                   boto3: Boto3SessionProxy):
    progress_event = ProgressEvent(status=Status.IN_PROGRESS, resourceModel=resource_model)
    # TODO: put code here
    return progress_event


def read_handler(resource_model: ResourceModel, handler_context: RequestContext, boto3: Boto3SessionProxy):
    progress_event = ProgressEvent(status=Status.IN_PROGRESS, resourceModel=resource_model)
    # TODO: put code here
    return progress_event


def list_handler(resource_model: ResourceModel, handler_context: RequestContext, boto3: Boto3SessionProxy):
    progress_event = ProgressEvent(status=Status.IN_PROGRESS, resourceModel=resource_model)
    # TODO: put code here
    return progress_event
