import json
import logging
from typing import Optional
from uuid import uuid4

# boto3 doesn't have stub files
from boto3 import Session  # type: ignore

from .interface import BaseResourceModel, HandlerErrorCode, OperationStatus
from .utils import KitchenSinkEncoder

LOG = logging.getLogger(__name__)


def report_progress(  # pylint: disable=too-many-arguments
    session: Session,
    token: str,
    code: Optional[HandlerErrorCode],
    status: OperationStatus,
    current_status: Optional[OperationStatus],
    model: Optional[BaseResourceModel],
    message: str,
) -> None:
    client = session.client("cloudformation")
    request = {
        "BearerToken": token,
        "OperationStatus": status.name,
        "StatusMessage": message,
        "ClientRequestToken": str(uuid4()),
    }
    if model:
        request["ResourceModel"] = json.dumps(
            model._serialize(),  # pylint: disable=protected-access
            cls=KitchenSinkEncoder,
        )
    if code:
        request["ErrorCode"] = code
    if current_status:
        request["CurrentOperationStatus"] = current_status.name
    response = client.record_handler_progress(**request)
    LOG.info(
        "Record Handler Progress with Request Id %s and Request: {%s}",
        response["ResponseMetadata"]["RequestId"],
        request,
    )
