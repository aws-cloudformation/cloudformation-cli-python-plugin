# pylint: disable=redefined-outer-name,protected-access
import logging
from unittest.mock import DEFAULT, Mock, create_autospec, patch

import pytest
from aws_cloudformation_rpdk_python_lib.log_delivery import ProviderLogHandler


@pytest.fixture
def mock_logger():
    return create_autospec(logging.getLogger())


@pytest.fixture
def mock_provider_handler():
    patch("aws_cloudformation_rpdk_python_lib.log_delivery.boto3.client", autospec=True)
    plh = ProviderLogHandler(
        group="test-group",
        stream="test-stream",
        creds={
            "aws_access_key_id": "",
            "aws_secret_access_key": "",
            "aws_session_token": "",
        },
    )
    for method in ["create_log_group", "create_log_stream", "put_log_events"]:
        setattr(plh.client, method, Mock(auto_spec=True))
    return plh


def test_setup_with_provider_creds(mock_logger):
    payload = {
        "requestData": {
            "providerCredentials": {
                "accessKeyId": "AKI",
                "secretAccessKey": "SAK",
                "sessionToken": "ST",
            },
            "providerLogGroupName": "test_group",
        }
    }
    with patch(
        "aws_cloudformation_rpdk_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ) as patched_logger:
        with patch(
            "aws_cloudformation_rpdk_python_lib.log_delivery.boto3.client",
            autospec=True,
        ) as mock_client:
            ProviderLogHandler.setup(payload)
    mock_client.assert_called_once_with(
        "logs",
        aws_access_key_id="AKI",
        aws_secret_access_key="SAK",
        aws_session_token="ST",
    )
    patched_logger.return_value.addHandler.assert_called_once()


def test_setup_without_provider_creds(mock_logger):
    with patch(
        "aws_cloudformation_rpdk_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ) as patched_logger:
        with patch(
            "aws_cloudformation_rpdk_python_lib.log_delivery.ProviderLogHandler"
            ".__init__",
            autospec=True,
        ) as mock___init__:
            ProviderLogHandler.setup({})
            ProviderLogHandler.setup({"requestData": {}})
            ProviderLogHandler.setup({"requestData": {"providerLogGroupName": "test"}})
            ProviderLogHandler.setup(
                {
                    "requestData": {
                        "providerCredentials": {
                            "accessKeyId": "AKI",
                            "secretAccessKey": "SAK",
                            "sessionToken": "ST",
                        }
                    }
                }
            )
    mock___init__.assert_not_called()
    patched_logger.return_value.addHandler.assert_not_called()


@pytest.mark.parametrize("create_method", ["_create_log_group", "_create_log_stream"])
def test__create_success(mock_provider_handler, create_method):
    getattr(mock_provider_handler, create_method)()
    getattr(mock_provider_handler.client, create_method[1:]).assert_called_once()


@pytest.mark.parametrize("create_method", ["_create_log_group", "_create_log_stream"])
def test__create_already_exists(mock_provider_handler, create_method):
    mock_logs_method = getattr(mock_provider_handler.client, create_method[1:])
    exc = mock_provider_handler.client.exceptions.ResourceAlreadyExistsException
    mock_logs_method.side_effect = exc({}, operation_name="Test")
    # should not raise an exception if the log group already exists
    getattr(mock_provider_handler, create_method)()
    mock_logs_method.assert_called_once()


@pytest.mark.parametrize("sequence_token", [None, "some-seq"])
def test__put_log_event_success(mock_provider_handler, sequence_token):
    mock_provider_handler.sequence_token = sequence_token
    mock_put = mock_provider_handler.client.put_log_events
    mock_put.return_value = {"nextSequenceToken": "some-other-seq"}
    mock_provider_handler._put_log_event(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    mock_put.assert_called_once()


def test__put_log_event_invalid_token(mock_provider_handler):
    exc = mock_provider_handler.client.exceptions
    mock_put = mock_provider_handler.client.put_log_events
    mock_put.return_value = {"nextSequenceToken": "some-other-seq"}
    mock_put.side_effect = [
        exc.InvalidSequenceTokenException({}, operation_name="Test"),
        exc.DataAlreadyAcceptedException({}, operation_name="Test"),
        DEFAULT,
    ]
    mock_provider_handler._put_log_event(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_put.call_count == 3


def test_emit_existing_cwl_group_stream(mock_provider_handler):
    mock_provider_handler._put_log_event = Mock()
    mock_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    mock_provider_handler._put_log_event.assert_called_once()


def test_emit_no_group_stream(mock_provider_handler):
    exc = mock_provider_handler.client.exceptions.ResourceNotFoundException
    group_exc = exc(
        {"Error": {"Message": "log group does not exist"}},
        operation_name="PutLogRecords",
    )
    mock_provider_handler._put_log_event = Mock()
    mock_provider_handler._put_log_event.side_effect = [group_exc, DEFAULT]
    mock_provider_handler._create_log_group = Mock()
    mock_provider_handler._create_log_stream = Mock()
    mock_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_provider_handler._put_log_event.call_count == 2
    mock_provider_handler._create_log_group.assert_called_once()
    mock_provider_handler._create_log_stream.assert_called_once()

    # create_group should not be called again if the group already exists
    stream_exc = exc(
        {"Error": {"Message": "log stream does not exist"}},
        operation_name="PutLogRecords",
    )
    mock_provider_handler._put_log_event.side_effect = [stream_exc, DEFAULT]
    mock_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_provider_handler._put_log_event.call_count == 4
    mock_provider_handler._create_log_group.assert_called_once()
    assert mock_provider_handler._create_log_stream.call_count == 2
