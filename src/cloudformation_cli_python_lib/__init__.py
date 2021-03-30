import logging

from .boto3_proxy import SessionProxy  # noqa: F401
from .interface import (  # noqa: F401
    Action,
    BaseResourceHandlerRequest,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)
from .resource import Resource  # noqa: F401

__version__ = "2.1.5"

logging.getLogger(__name__).addHandler(logging.NullHandler())
