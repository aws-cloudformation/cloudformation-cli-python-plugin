import botocore
from boto3.session import Session

from cloudformation_cli_python_lib.boto3_proxy import SessionProxy, _get_boto_session
from cloudformation_cli_python_lib.utils import Credentials


def test_get_boto_session_returns_proxy():
    proxy = _get_boto_session(Credentials("", "", ""))
    assert isinstance(proxy, SessionProxy)


def test_get_boto_session_returns_none():
    proxy = _get_boto_session(None)
    assert proxy is None

def test_can_create_boto_client():
    proxy = _get_boto_session(Credentials("", "", ""))
    client = proxy.client('s3', region_name="us-west-2") # just in case AWS_REGION not set in test environment
    assert isinstance(client, botocore.client.BaseClient)

def test_can_retrieve_boto_session():
    proxy = _get_boto_session(Credentials("", "", ""))
    session = proxy.session
    assert isinstance(session, Session)
