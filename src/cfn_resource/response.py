import json
import logging

from .utils import _serialize

LOG = logging.getLogger(__name__)

try:
    from resource_model import ResourceModel  # pylint: disable=import-error
except ModuleNotFoundError as e:
    if str(e) == "No module named 'resource_model'":
        LOG.warning('resource_model module not present in path, using BaseResourceModel')
        from .base_resource_model import BaseResourceModel as ResourceModel
    else:
        raise


class Status:
    IN_PROGRESS = 'IN_PROGRESS'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class ProgressEvent:

    def __init__(self, status: str, resourceModel: ResourceModel, message: str = "",  # pylint: disable=invalid-name
                 callbackContext: dict = None, error_code: str = '', callbackDelayMinutes: int = 0):  # pylint: disable=invalid-name
        callbackContext = {} if callbackContext is None else callbackContext
        resourceModel = {} if resourceModel is None else resourceModel

        self.status = status
        self.errorCode = error_code  # pylint: disable=invalid-name
        self.message = message
        self.callbackContext = callbackContext  # pylint: disable=invalid-name
        self.callbackDelayMinutes = callbackDelayMinutes  # pylint: disable=invalid-name
        self.resourceModel = resourceModel  # pylint: disable=invalid-name

    def json(self):
        return json.dumps(self, default=_serialize)
