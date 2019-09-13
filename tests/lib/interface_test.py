# pylint: disable=protected-access
import json
from string import ascii_letters

from aws_cloudformation_rpdk_python_lib.interface import (
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
)

import hypothesis.strategies as s
from hypothesis import given


@given(s.sampled_from(HandlerErrorCode), s.text(ascii_letters))
def test_progress_event_failed_is_json_serializable(error_code, message):
    event = ProgressEvent.failed(error_code, message)
    assert event.status == OperationStatus.FAILED
    assert event.errorCode == error_code
    assert event.message == message

    assert json.loads(json.dumps(event._serialize())) == {
        "status": OperationStatus.FAILED.value,
        "errorCode": error_code.value,
        "message": message,
        "callbackContext": {},
        "callbackDelaySeconds": 0,
    }
