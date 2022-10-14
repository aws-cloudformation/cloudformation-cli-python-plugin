from boto3.session import Session
from cloudformation_cli_python_lib.boto3_proxy import SessionProxy, _get_boto_session
from cloudformation_cli_python_lib.utils import Credentials


def test_get_boto_session_returns_proxy():
    proxy = _get_boto_session(Credentials("", "", ""))
    assert isinstance(proxy, SessionProxy)


def test_get_boto_session_returns_none():
    proxy = _get_boto_session(None)
    assert proxy is None


def test_can_retrieve_boto_session():
    proxy = _get_boto_session(Credentials("", "", ""))
    session = proxy.session
    assert isinstance(session, Session)
