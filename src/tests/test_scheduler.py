# pylint: disable=protected-access

import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from cfn_resource.scheduler import CloudWatchScheduler

PARENT = Path(__file__).parent
EVENTS = {
    "SYNC-GOOD": [
        PARENT / "data" / "create.request.json",
    ],
    "ASYNC-GOOD": [
        PARENT / "data" / "create.with-request-context.request.json",
    ]
}


def _get_event(evt_path):
    with open(evt_path, 'r') as file_h:
        event = json.load(file_h)
    return event


class TestCloudWatchScheduler(unittest.TestCase):

    def test_reschedule(self):
        mock_boto = mock.Mock()
        cws = CloudWatchScheduler(b3=mock_boto)
        cws._cwe_client.put_rule = mock.Mock()
        cws._cwe_client.put_targets = mock.Mock()
        event = _get_event(EVENTS['SYNC-GOOD'][0])
        cws.reschedule('arn::not::really', event, {}, 1)
        self.assertEqual(True, event['requestContext']['cloudWatchEventsRuleName'].startswith('reinvoke-handler-'))
        self.assertEqual(True, event['requestContext']['cloudWatchEventsTargetId'].startswith('reinvoke-target-'))
        self.assertEqual(1, event['requestContext']['invocation'])
        cws._cwe_client.put_rule.assert_called_once()
        cws._cwe_client.put_targets.assert_called_once()
        event = _get_event(EVENTS['ASYNC-GOOD'][0])
        cws.reschedule('arn::not::really', event, {}, 1)
        self.assertEqual(3, event['requestContext']['invocation'])

    @staticmethod
    def test_cleanup():
        mock_boto = mock.Mock()
        cws = CloudWatchScheduler(b3=mock_boto)
        cws._cwe_client.delete_rule = mock.Mock()
        cws._cwe_client.remove_targets = mock.Mock()
        event = _get_event(EVENTS['SYNC-GOOD'][0])
        cws.cleanup(event)
        cws._cwe_client.delete_rule.assert_not_called()
        cws._cwe_client.remove_targets.assert_not_called()
        event = _get_event(EVENTS['ASYNC-GOOD'][0])
        cws.cleanup(event)
        cws._cwe_client.delete_rule.assert_called_once()
        cws._cwe_client.remove_targets.assert_called_once()

    def test_nim_to_cron(self):
        now = datetime.now()
        cron = CloudWatchScheduler._min_to_cron(1)
        self.assertEqual(True, cron.startswith('cron('))
        self.assertEqual(True, cron.endswith(')'))
        print(cron)
        out_dt = datetime.strptime(cron, "cron('%M %H %d %m ? %Y')")
        diff = out_dt - now
        self.assertGreater(120.0, diff.total_seconds())
