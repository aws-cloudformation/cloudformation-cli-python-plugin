# pylint: disable=protected-access

import unittest
from datetime import datetime, timedelta
from unittest import mock

from cfn_resource import Status
from cfn_resource.metrics import Metrics


class TestMetrics(unittest.TestCase):
    def test_exception(self):
        boto3_mock = mock.Mock()
        start_time = datetime.now()
        metrics = Metrics("Aa::Bb::Cc", b3=boto3_mock)
        metrics.exception(start_time, Status.FAILED, ValueError("test"))
        expected = [
            {
                "MetricName": "HandlerException",
                "Dimensions": [
                    {"Name": "Action", "Value": "FAILED"},
                    {"Name": "ExceptionType", "Value": "ValueError"},
                    {"Name": "ResourceType", "Value": "Aa::Bb::Cc"},
                ],
                "Timestamp": start_time,
                "Value": 1.0,
                "Unit": "Count",
            }
        ]
        self.assertEqual(expected, metrics.data)

    def test_invocation(self):
        boto3_mock = mock.Mock()
        start_time = datetime.now()
        metrics = Metrics("Aa::Bb::Cc", b3=boto3_mock)
        metrics.invocation(start_time, Status.SUCCESS)
        expected = [
            {
                "MetricName": "HandlerInvocationCount",
                "Dimensions": [
                    {"Name": "Action", "Value": "SUCCESS"},
                    {"Name": "ResourceType", "Value": "Aa::Bb::Cc"},
                ],
                "Timestamp": start_time,
                "Value": 1.0,
                "Unit": "Count",
            }
        ]
        self.assertEqual(expected, metrics.data)

    def test_duration(self):
        boto3_mock = mock.Mock()
        start_time = datetime.now()
        metrics = Metrics("Aa::Bb::Cc", b3=boto3_mock)
        duration = (start_time + timedelta(0, 10)) - start_time
        metrics.duration(start_time, Status.SUCCESS, duration)
        expected = [
            {
                "MetricName": "HandlerInvocationDuration",
                "Dimensions": [
                    {"Name": "Action", "Value": "SUCCESS"},
                    {"Name": "ResourceType", "Value": "Aa::Bb::Cc"},
                ],
                "Timestamp": start_time,
                "Value": 10000,
                "Unit": "Milliseconds",
            }
        ]
        print(metrics.data)
        self.assertEqual(expected, metrics.data)

    def test_publish(self):
        boto3_mock = mock.Mock()
        start_time = datetime.now()
        duration = (start_time + timedelta(0, 10)) - start_time
        sessions = [{"region_name": "us-east-1"}, {"region_name": "us-east-2"}]
        metrics = Metrics("Aa::Bb::Cc", session_configs=sessions, b3=boto3_mock)
        client_indexes = range(len(metrics._cw_clients))
        self.assertEqual(client_indexes, range(0, 2))
        for i in client_indexes:
            metrics._cw_clients[i] = mock.Mock()
            metrics._cw_clients[i].put_metric_data = mock.Mock()
        metrics.publish()
        for i in client_indexes:
            metrics._cw_clients[i].put_metric_data.assert_not_called()
        metrics.duration(start_time, Status.SUCCESS, duration)
        metrics.publish()
        for i in client_indexes:
            metrics._cw_clients[i].put_metric_data.assert_called_once()
        self.assertEqual([], metrics.data)
