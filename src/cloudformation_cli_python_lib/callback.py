import json
import logging
from typing import Optional
from uuid import uuid4

from .boto3_proxy import SessionProxy
from .interface import BaseModel, HandlerErrorCode, OperationStatus
from .utils import KitchenSinkEncoder

LOG = logging.getLogger(__name__)


def report_progress(  # pylint: disable=too-many-arguments
    session: SessionProxy,
    bearer_token: str,
    error_code: Optional[HandlerErrorCode],
    operation_status: OperationStatus,
    current_operation_status: Optional[OperationStatus],
    resource_model: Optional[BaseModel],
    status_message: str,
) -> None:
    client = session.client("cloudformation")
    request = {
        "BearerToken": bearer_token,
        "OperationStatus": operation_status.name,
        "StatusMessage": status_message,
        "ClientRequestToken": str(uuid4()),
    }
    if resource_model:
        request["ResourceModel"] = json.dumps(
            resource_model._serialize(),  # pylint: disable=protected-access
            cls=KitchenSinkEncoder,
        )
    if error_code:
        request["ErrorCode"] = error_code.name
    if current_operation_status:
        request["CurrentOperationStatus"] = current_operation_status.name
    response = client.record_handler_progress(**request)
    LOG.info(
        "Record Handler Progress with Request Id %s and Request: {%s}",
        response["ResponseMetadata"]["RequestId"],
        request,
    )
