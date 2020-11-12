# pylint: disable=redefined-outer-name,protected-access
import logging
from unittest.mock import DEFAULT, Mock, create_autospec, patch
from uuid import uuid4

import pytest
from boto3.session import Session
from cloudformation_cli_python_lib.boto3_proxy import SessionProxy
from cloudformation_cli_python_lib.log_delivery import (
    ProviderFilter,
    ProviderLogHandler,
)
from cloudformation_cli_python_lib.utils import HandlerRequest, RequestData


@pytest.fixture
def mock_logger():
    return create_autospec(logging.getLogger())


@pytest.fixture
def mock_session():
    return Mock(spec_set=["client"])


def make_payload() -> HandlerRequest:
    return HandlerRequest(
        action="CREATE",
        awsAccountId="123412341234",
        bearerToken=str(uuid4()),
        region="us-east-1",
        responseEndpoint="",
        resourceType="Foo::Bar::Baz",
        resourceTypeVersion="4",
        requestData=RequestData(
            providerLogGroupName="test_group",
            logicalResourceId="MyResourceId",
            resourceProperties={},
            systemTags={},
            previousSystemTags={},
        ),
        stackId="an-arn",
    )


@pytest.fixture
def setup_patches(mock_logger):
    patch_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    )
    patch__get_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.ProviderLogHandler."
        "_get_existing_logger"
    )
    return make_payload(), patch_logger, patch__get_logger


@pytest.fixture
def mock_provider_handler():
    plh = ProviderLogHandler(
        group="test-group",
        stream="test-stream",
        session=SessionProxy(
            Session(
                aws_access_key_id="", aws_secret_access_key="", aws_session_token=""
            )
        ),
    )
    # not mocking the whole client because that replaces generated exception classes to
    # be replaced with mocks
    for method in ["create_log_group", "create_log_stream", "put_log_events"]:
        setattr(plh.client, method, Mock(auto_spec=True))
    return plh


@pytest.mark.parametrize(
    "logger", [("aa_bb_cc", False), ("cloudformation_cli_python_lib", True)]
)
def test_provider_filter(logger):
    log_name, expected = logger
    log_filter = ProviderFilter("aa_bb_cc")
    record = logging.LogRecord(
        name=log_name,
        level=123,
        pathname="abc",
        lineno=123,
        msg="test",
        args=[],
        exc_info=False,
    )
    assert log_filter.filter(record) == expected


def test_setup_with_provider_creds_and_stack_id_and_logical_resource_id(
    setup_patches, mock_session
):
    payload, p_logger, p__get_logger = setup_patches
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = None
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert payload.stackId in plh.stream
    assert payload.requestData.logicalResourceId in plh.stream


def test_setup_with_provider_creds_without_stack_id(setup_patches, mock_session):
    payload, p_logger, p__get_logger = setup_patches
    payload.stackId = None
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = None
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert payload.awsAccountId in plh.stream
    assert payload.region in plh.stream


def test_setup_with_provider_creds_without_logical_resource_id(
    setup_patches, mock_session
):
    payload, p_logger, p__get_logger = setup_patches
    payload.requestData.logicalResourceId = None
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = None
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert payload.awsAccountId in plh.stream
    assert payload.region in plh.stream


def test_setup_existing_logger(setup_patches, mock_session):
    existing = ProviderLogHandler("g", "s", mock_session)
    mock_session.reset_mock()
    payload, p_logger, p__get_logger = setup_patches
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = existing
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_not_called()


def test_setup_without_log_group_should_not_set_up(mock_logger, mock_session):
    patch_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    )
    patch___init__ = patch(
        "cloudformation_cli_python_lib.log_delivery.ProviderLogHandler.__init__",
        autospec=True,
    )
    with patch_logger as mock_log, patch___init__ as mock___init__:
        payload = make_payload()
        payload.requestData.providerLogGroupName = ""
        ProviderLogHandler.setup(payload, mock_session)
    mock___init__.assert_not_called()
    mock_session.assert_not_called()
    mock_log.return_value.addHandler.assert_not_called()


def test_setup_without_session_should_not_set_up(mock_logger):
    patch_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    )
    patch___init__ = patch(
        "cloudformation_cli_python_lib.log_delivery.ProviderLogHandler.__init__",
        autospec=True,
    )
    with patch_logger as mock_log, patch___init__ as mock___init__:
        ProviderLogHandler.setup(make_payload(), None)
    mock___init__.assert_not_called()
    mock_log.return_value.addHandler.assert_not_called()


def test_log_group_create_success(mock_provider_handler):
    mock_provider_handler._create_log_group()
    mock_provider_handler.client.create_log_group.assert_called_once()


def test_log_stream_create_success(mock_provider_handler):
    mock_provider_handler._create_log_stream()
    mock_provider_handler.client.create_log_stream.assert_called_once()


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


def test__get_existing_logger_no_logger_present(mock_logger):
    mock_logger.handlers = [logging.Handler()]
    with patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ):
        actual = ProviderLogHandler._get_existing_logger()
    assert actual is None


def test__get_existing_logger_logger_present(mock_logger, mock_session):
    expected = ProviderLogHandler("g", "s", mock_session)
    mock_logger.handlers = [logging.Handler(), expected]
    with patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ):
        actual = ProviderLogHandler._get_existing_logger()
    assert actual == expected
