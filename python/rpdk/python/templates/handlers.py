import logging
from typing import Any, MutableMapping

from {{support_lib_pkg}} import (
    Action,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
    Resource,
    ResourceHandlerRequest,
    SessionProxy,
    exceptions,
)

from .models import ResourceModel, TResourceModel

# Use this logger to forward log messages to CloudWatch Logs.
LOG = logging.getLogger(__name__)

resource = Resource(ResourceModel)
test_entrypoint = resource.test_entrypoint


@resource.handler(Action.CREATE)
def create_handler(
    session: SessionProxy,
    request: ResourceHandlerRequest[TResourceModel],
    callback_context: MutableMapping[str, Any],
) -> ProgressEvent[TResourceModel]:
    model = request.desiredResourceState
    progress: ProgressEvent[TResourceModel] = ProgressEvent(
        status=OperationStatus.IN_PROGRESS,
        resourceModel=model,
    )
    # TODO: put code here

    # Example:
    try:
        client = session.client("s3")
        # Setting Status to success will signal to cfn that the operation is complete
        progress.status = OperationStatus.SUCCESS
    except TypeError as e:
        # exceptions module lets CloudFormation know the type of failure that occurred
        raise exceptions.InternalFailure(f"was not expecting type {e}")
        # this can also be done by returning a failed progress event
        # return ProgressEvent.failed(HandlerErrorCode.InternalFailure, f"was not expecting type {e}")
    return progress


@resource.handler(Action.UPDATE)
def update_handler(
    session: SessionProxy,
    request: ResourceHandlerRequest[TResourceModel],
    callback_context: MutableMapping[str, Any],
) -> ProgressEvent[TResourceModel]:
    model = request.desiredResourceState
    progress: ProgressEvent[TResourceModel] = ProgressEvent(
        status=OperationStatus.IN_PROGRESS,
        resourceModel=model,
    )
    # TODO: put code here
    return progress


@resource.handler(Action.DELETE)
def delete_handler(
    session: SessionProxy,
    request: ResourceHandlerRequest[TResourceModel],
    callback_context: MutableMapping[str, Any],
) -> ProgressEvent[TResourceModel]:
    model = request.desiredResourceState
    progress: ProgressEvent[TResourceModel] = ProgressEvent(
        status=OperationStatus.IN_PROGRESS,
        resourceModel=model,
    )
    # TODO: put code here
    return progress


@resource.handler(Action.READ)
def read_handler(
    session: SessionProxy,
    request: ResourceHandlerRequest[TResourceModel],
    callback_context: MutableMapping[str, Any],
) -> ProgressEvent[TResourceModel]:
    model = request.desiredResourceState
    # TODO: put code here
    return ProgressEvent(
        status=OperationStatus.SUCCESS,
        resourceModel=model,
    )


@resource.handler(Action.LIST)
def list_handler(
    session: SessionProxy,
    request: ResourceHandlerRequest[TResourceModel],
    callback_context: MutableMapping[str, Any],
) -> ProgressEvent[TResourceModel]:
    # TODO: put code here
    return ProgressEvent(
        status=OperationStatus.SUCCESS,
        resourceModels=[],
    )
