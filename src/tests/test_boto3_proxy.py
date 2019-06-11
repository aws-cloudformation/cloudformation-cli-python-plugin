import unittest
from unittest import mock

from cfn_resource.boto3_proxy import Boto3Client, get_boto3_proxy_session, get_boto_session_config, boto3_factory, \
    Boto3SessionProxy

SESSION_CONFIG = {'aws_access_key_id': 'a', 'aws_secret_access_key': 'b', 'aws_session_token': 'c', 'region_name': 'd'}


class TestBoto3Client(unittest.TestCase):

    @mock.patch('cfn_resource.boto3_proxy.Boto3Client.boto3')
    def test_init(self, mock_boto):
        Boto3Client(region_name="some-region-1")
        self.assertEqual({'region_name': 'some-region-1'}, mock_boto.method_calls[0][2])

    @mock.patch('cfn_resource.boto3_proxy.Boto3Client.boto3')
    def test_client(self, mock_boto):
        session = Boto3Client(region_name="some-region-1")
        session.client("some-service", region_name="some-otherplace-1")
        call = mock_boto.mock_calls[1]
        self.assertEqual(tuple(["some-service"]), call[1])
        self.assertEqual({'region_name': "some-otherplace-1"}, call[2])


class TestBoto3funcs(unittest.TestCase):

    def test_get_boto3_proxy_session(self):
        mock_boto = mock.Mock()
        session_proxy = get_boto3_proxy_session({"region_name": "us-east-2"}, mock_boto)
        self.assertEqual(False, mock_boto.called)
        self.assertEqual(mock_boto, session_proxy.boto3pkg)

    def test_get_boto_session_config(self):
        evt = {
            'region': "d",
            'requestData': {'credentials': {'accessKeyId': 'a', 'secretAccessKey': 'b', 'sessionToken': 'c'}}
        }
        act = get_boto_session_config(evt)
        self.assertEqual(SESSION_CONFIG, act)

    def test_boto3_factory(self):
        mock_boto = mock.Mock()

        def mock_provider():
            return SESSION_CONFIG

        boto_proxy = boto3_factory(mock_provider, mock_boto)
        self.assertEqual(0, len(mock_boto.mock_calls))

        client = boto_proxy('client', 's3', 'us-east-2')
        self.assertEqual(1, len(mock_boto.mock_calls))

        # proxy checks for public methods to discover supported aws api's, in this case it's the Mock instance's methods
        resp = client.called  # pylint: disable=no-member
        self.assertEqual(1, len(mock_boto.mock_calls))
        self.assertEqual({'service_name': 's3', 'region_name': 'us-east-2', 'boto3_method': 'called'}, resp.keywords)


class TestBoto3SessionProxy(unittest.TestCase):

    def test_proxy_(self):
        def mock_provider():
            return SESSION_CONFIG

        class MockSession:
            class client:  # pylint: disable=invalid-name
                def __init__(self, *args, **kwargs):
                    pass

                def create_bucket(self, BucketName):  # pylint: disable=unused-argument,no-self-use
                    return {}

            class resource:  # pylint: disable=invalid-name
                def __init__(self, *args, **kwargs):
                    pass

                def list_objects(self): # pylint: disable=no-self-use
                    return {}

            class session:  # pylint: disable=invalid-name
                @staticmethod
                def Session(*args, **kwargs):  # pylint: disable=unused-argument
                    return MockSession()

        sess_proxy = Boto3SessionProxy("us-east-2", boto3_factory(mock_provider, MockSession), MockSession)
        client = sess_proxy.client('s3')
        resource = sess_proxy.resource('s3')
        self.assertEqual({}, client.create_bucket(BucketName='testbucket'))
        self.assertEqual({}, resource.list_objects())
