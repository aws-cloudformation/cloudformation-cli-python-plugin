# pylint: disable=redefined-outer-name,protected-access
import pytest
from cloudformation_cli_python_lib.log_delivery import (
    HookProviderLogHandler,
    ProviderFilter,
    ProviderLogHandler,
)
from cloudformation_cli_python_lib.utils import (
    HandlerRequest,
    HookInvocationRequest,
    HookRequestData,
    RequestData,
)

import botocore.errorfactory
import botocore.session
import logging
from unittest.mock import DEFAULT, Mock, create_autospec, patch
from uuid import uuid4

logs_model = botocore.session.get_session().get_service_model("logs")
factory = botocore.errorfactory.ClientExceptionsFactory()
logs_exceptions = factory.create_client_exceptions(logs_model)


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


def make_hook_payload() -> HookInvocationRequest:
    return HookInvocationRequest(
        actionInvocationPoint="CREATE_PRE_PROVISION",
        awsAccountId="123412341234",
        clientRequestToken=str(uuid4()),
        hookTypeName="AWS::Test::Hook",
        hookTypeVersion="3",
        requestData=HookRequestData(
            providerLogGroupName="test_group",
            targetName="AWS::Test::Resource",
            targetType="RESOURCE",
            targetLogicalId="MyTargetId",
            targetModel={"resourceProperties": {}},
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
    patch__get_hook_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.HookProviderLogHandler."
        "_get_existing_logger"
    )
    return (
        make_payload(),
        make_hook_payload(),
        patch_logger,
        patch__get_logger,
        patch__get_hook_logger,
    )


@pytest.fixture
def mock_handler_set_formatter():
    patch__set_handler_formatter = patch.object(ProviderLogHandler, "setFormatter")
    patch__set_hook_handler_formatter = patch.object(
        HookProviderLogHandler, "setFormatter"
    )
    return patch__set_handler_formatter, patch__set_hook_handler_formatter


@pytest.fixture
def mock_provider_handler(mock_session):
    plh = ProviderLogHandler(
        group="test-group",
        stream="test-stream",
        session=mock_session,
    )
    # not mocking the whole client because that replaces generated exception classes to
    # be replaced with mocks
    for method in ["create_log_group", "create_log_stream", "put_log_events"]:
        setattr(plh.client, method, Mock(auto_spec=True))

    # set exceptions instead of using Mock
    plh.client.exceptions = logs_exceptions
    return plh


@pytest.fixture
def mock_hook_provider_handler(mock_session):
    plh = HookProviderLogHandler(
        group="test-hook-group",
        stream="test-hook-stream",
        session=mock_session,
    )
    # not mocking the whole client because that replaces generated exception classes to
    # be replaced with mocks
    for method in ["create_log_group", "create_log_stream", "put_log_events"]:
        setattr(plh.client, method, Mock(auto_spec=True))

    # set exceptions instead of using Mock
    plh.client.exceptions = logs_exceptions
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
    payload, _hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = None
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert payload.stackId in plh.stream
    assert payload.requestData.logicalResourceId in plh.stream


def test_setup_with_provider_creds_without_stack_id(setup_patches, mock_session):
    payload, _hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
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
    payload, _hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
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
    payload, _hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
    with p_logger as mock_log, p__get_logger as mock_get:
        mock_get.return_value = existing
        ProviderLogHandler.setup(payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_not_called()


def test_setup_with_formatter(setup_patches, mock_session, mock_handler_set_formatter):
    payload, _hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
    (
        p__set_handler_formatter,
        _p__set_hook_handler_formatter,
    ) = mock_handler_set_formatter
    formatter = logging.Formatter()
    with p_logger as mock_log, p__get_logger as mock_get, p__set_handler_formatter as mock_set_formatter:  # pylint: disable=C0301  # noqa: B950
        mock_get.return_value = None
        ProviderLogHandler.setup(payload, mock_session, formatter)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    mock_set_formatter.assert_called_once_with(formatter)


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
    mock_put = mock_provider_handler.client.put_log_events
    mock_put.return_value = {"nextSequenceToken": "some-other-seq"}
    mock_put.side_effect = [
        logs_exceptions.InvalidSequenceTokenException({}, operation_name="Test"),
        logs_exceptions.DataAlreadyAcceptedException({}, operation_name="Test"),
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
    group_exc = logs_exceptions.ResourceNotFoundException(
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
    stream_exc = logs_exceptions.ResourceNotFoundException(
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


def test_setup_with_hook_provider_creds_and_stack_id_and_target_logical_id(
    setup_patches, mock_session
):
    _payload, hook_payload, p_logger, _p__get_logger, p__get_hook_logger = setup_patches
    with p_logger as mock_log, p__get_hook_logger as mock_get:
        mock_get.return_value = None
        HookProviderLogHandler.setup(hook_payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert hook_payload.stackId in plh.stream
    assert hook_payload.requestData.targetLogicalId in plh.stream


def test_setup_with_hook_provider_creds_without_stack_id(setup_patches, mock_session):
    _payload, hook_payload, p_logger, _p__get_logger, p__get_hook_logger = setup_patches
    hook_payload.stackId = None
    with p_logger as mock_log, p__get_hook_logger as mock_get:
        mock_get.return_value = None
        HookProviderLogHandler.setup(hook_payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert hook_payload.awsAccountId in plh.stream


def test_setup_with_hook_provider_creds_without_target_logical_id(
    setup_patches, mock_session
):
    _payload, hook_payload, p_logger, _p__get_logger, p__get_hook_logger = setup_patches
    hook_payload.requestData.targetLogicalId = None
    with p_logger as mock_log, p__get_hook_logger as mock_get:
        mock_get.return_value = None
        HookProviderLogHandler.setup(hook_payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    plh = mock_log.return_value.addHandler.call_args[0][0]
    assert hook_payload.awsAccountId in plh.stream


def test_setup_existing_hook_logger(setup_patches, mock_session):
    existing = HookProviderLogHandler("g", "s", mock_session)
    mock_session.reset_mock()
    _payload, hook_payload, p_logger, _p__get_logger, p__get_hook_logger = setup_patches
    with p_logger as mock_log, p__get_hook_logger as mock_get:
        mock_get.return_value = existing
        HookProviderLogHandler.setup(hook_payload, mock_session)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_not_called()


def test_setup_with_hook_formatter(
    setup_patches, mock_session, mock_handler_set_formatter
):
    _payload, hook_payload, p_logger, p__get_logger, _p__get_hook_logger = setup_patches
    (
        _p__set_handler_formatter,
        p__set_hook_handler_formatter,
    ) = mock_handler_set_formatter
    formatter = logging.Formatter()
    with p_logger as mock_log, p__get_logger as mock_get, p__set_hook_handler_formatter as mock_set_formatter:  # pylint: disable=C0301  # noqa: B950
        mock_get.return_value = None
        HookProviderLogHandler.setup(hook_payload, mock_session, formatter)
    mock_session.client.assert_called_once_with("logs")
    mock_log.return_value.addHandler.assert_called_once()
    mock_set_formatter.assert_called_once_with(formatter)


def test_setup_without_hook_log_group_should_not_set_up(mock_logger, mock_session):
    patch_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    )
    patch___init__ = patch(
        "cloudformation_cli_python_lib.log_delivery.HookProviderLogHandler.__init__",
        autospec=True,
    )
    with patch_logger as mock_log, patch___init__ as mock___init__:
        payload = make_hook_payload()
        payload.requestData.providerLogGroupName = ""
        HookProviderLogHandler.setup(payload, mock_session)
    mock___init__.assert_not_called()
    mock_session.assert_not_called()
    mock_log.return_value.addHandler.assert_not_called()


def test_setup_without_hook_session_should_not_set_up(mock_logger):
    patch_logger = patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    )
    patch___init__ = patch(
        "cloudformation_cli_python_lib.log_delivery.HookProviderLogHandler.__init__",
        autospec=True,
    )
    with patch_logger as mock_log, patch___init__ as mock___init__:
        HookProviderLogHandler.setup(make_hook_payload(), None)
    mock___init__.assert_not_called()
    mock_log.return_value.addHandler.assert_not_called()


def test_hook_log_group_create_success(mock_hook_provider_handler):
    mock_hook_provider_handler._create_log_group()
    mock_hook_provider_handler.client.create_log_group.assert_called_once()


def test_hook_log_stream_create_success(mock_hook_provider_handler):
    mock_hook_provider_handler._create_log_stream()
    mock_hook_provider_handler.client.create_log_stream.assert_called_once()


@pytest.mark.parametrize("create_method", ["_create_log_group", "_create_log_stream"])
def test__hook_create_already_exists(mock_hook_provider_handler, create_method):
    mock_logs_method = getattr(mock_hook_provider_handler.client, create_method[1:])
    mock_logs_method.side_effect = logs_exceptions.ResourceAlreadyExistsException(
        {}, operation_name="Test"
    )
    # should not raise an exception if the log group already exists
    getattr(mock_hook_provider_handler, create_method)()
    mock_logs_method.assert_called_once()


@pytest.mark.parametrize("sequence_token", [None, "some-seq"])
def test__hook_put_log_event_success(mock_hook_provider_handler, sequence_token):
    mock_hook_provider_handler.sequence_token = sequence_token
    mock_put = mock_hook_provider_handler.client.put_log_events
    mock_put.return_value = {"nextSequenceToken": "some-other-seq"}
    mock_hook_provider_handler._put_log_event(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    mock_put.assert_called_once()


def test__hook_put_log_event_invalid_token(mock_hook_provider_handler):
    mock_put = mock_hook_provider_handler.client.put_log_events
    mock_put.return_value = {"nextSequenceToken": "some-other-seq"}
    mock_put.side_effect = [
        logs_exceptions.InvalidSequenceTokenException({}, operation_name="Test"),
        logs_exceptions.DataAlreadyAcceptedException({}, operation_name="Test"),
        DEFAULT,
    ]
    mock_hook_provider_handler._put_log_event(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_put.call_count == 3


def test_hook_emit_existing_cwl_group_stream(mock_hook_provider_handler):
    mock_hook_provider_handler._put_log_event = Mock()
    mock_hook_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    mock_hook_provider_handler._put_log_event.assert_called_once()


def test_hook_emit_no_group_stream(mock_hook_provider_handler):
    group_exc = logs_exceptions.ResourceNotFoundException(
        {"Error": {"Message": "log group does not exist"}},
        operation_name="PutLogRecords",
    )
    mock_hook_provider_handler._put_log_event = Mock()
    mock_hook_provider_handler._put_log_event.side_effect = [group_exc, DEFAULT]
    mock_hook_provider_handler._create_log_group = Mock()
    mock_hook_provider_handler._create_log_stream = Mock()
    mock_hook_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_hook_provider_handler._put_log_event.call_count == 2
    mock_hook_provider_handler._create_log_group.assert_called_once()
    mock_hook_provider_handler._create_log_stream.assert_called_once()

    # create_group should not be called again if the group already exists
    stream_exc = logs_exceptions.ResourceNotFoundException(
        {"Error": {"Message": "log stream does not exist"}},
        operation_name="PutLogRecords",
    )
    mock_hook_provider_handler._put_log_event.side_effect = [stream_exc, DEFAULT]
    mock_hook_provider_handler.emit(
        logging.LogRecord("a", 123, "/", 234, "log-msg", [], False)
    )
    assert mock_hook_provider_handler._put_log_event.call_count == 4
    mock_hook_provider_handler._create_log_group.assert_called_once()
    assert mock_hook_provider_handler._create_log_stream.call_count == 2


def test__get_existing_hook_logger_no_logger_present(mock_logger):
    mock_logger.handlers = [logging.Handler()]
    with patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ):
        actual = HookProviderLogHandler._get_existing_logger()
    assert actual is None


def test__get_existing_hook_logger_logger_present(mock_logger, mock_session):
    expected = HookProviderLogHandler("g", "s", mock_session)
    mock_logger.handlers = [logging.Handler(), expected]
    with patch(
        "cloudformation_cli_python_lib.log_delivery.logging.getLogger",
        return_value=mock_logger,
    ):
        actual = HookProviderLogHandler._get_existing_logger()
    assert actual == expected
