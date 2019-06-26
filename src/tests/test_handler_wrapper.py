# pylint: disable=protected-access

import json
import os
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from cfn_resource import ProgressEvent, Status, exceptions
from cfn_resource.base_resource_model import BaseResourceModel as ResourceModel
from cfn_resource.handler_wrapper import HandlerWrapper, _handler_wrapper

PARENT = Path(__file__).parent
EVENTS = {
    "SYNC-GOOD": [
        PARENT / "data" / "create.request.json",
        PARENT / "data" / "delete.request.json",
        PARENT / "data" / "list.request.json",
        PARENT / "data" / "read.request.json",
        PARENT / "data" / "update.request.json",
    ],
    "ASYNC-GOOD": [
        PARENT / "data" / "create.with-request-context.request.json",
        PARENT / "data" / "delete.with-request-context.request.json",
        PARENT / "data" / "update.with-request-context.request.json",
    ],
    "BAD": [
        # meed schema validation for this one to fail
        # PARENT / "data" / "create.request.with-extraneous-model-fields.json",
        [PARENT / "data" / "no-response-endpoint.request.json", "InvalidRequest"],
        [PARENT / "data" / "malformed.request.json", "InternalFailure"],
        [
            PARENT / "data" / "create.request-without-platform-credentials.json",
            "InternalFailure",
        ],
    ],
}

sys.path.append(str(PARENT))


def _get_event(evt_path):
    with open(evt_path, "r") as file_h:
        event = json.load(file_h)
    return event


def get_mock_context(deadline=None, val=9000):
    arn = "arn:aws:lambda:us-west-2:123412341234:function:my-function"
    context = mock.Mock(invoked_function_arn=arn)
    if deadline:
        context.get_remaining_time_in_millis.side_effect = lambda: int(
            (deadline - datetime.now()).total_seconds() * 1000
        )
    else:
        context.get_remaining_time_in_millis.return_value = val
    return context


def mock_handler(*_args, **_kwargs):
    return ProgressEvent(status=Status.SUCCESS, resourceModel=ResourceModel())


def mock_handler_reschedule(*_args, **_kwargs):
    return ProgressEvent(
        status=Status.IN_PROGRESS,
        resourceModel=ResourceModel(),
        callbackContext={"some_key": "some-value"},
        callbackDelaySeconds=120,
    )


def mock_handler_local_callback(*_args, **_kwargs):
    return ProgressEvent(
        status=Status.IN_PROGRESS,
        resourceModel=ResourceModel(),
        callbackContext={"some_key": "some-value"},
        callbackDelaySeconds=1,
    )


class TestHandlerWrapper(unittest.TestCase):
    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper.__init__",
        autospec=True,
        return_value=None,
    )
    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper.run_handler",
        autospec=True,
        return_value=ProgressEvent(
            status=Status.SUCCESS, resourceModel=ResourceModel()
        ),
    )
    def test_handler_wrapper_func(self, mock_hw_run_handler, mock_hw_init):
        for event in EVENTS["SYNC-GOOD"]:
            mock_hw_init.reset_mock()
            mock_hw_run_handler.reset_mock()

            event = _get_event(event)
            resp = _handler_wrapper(event, get_mock_context())
            resp = json.loads(resp)
            self.assertEqual("SUCCESS", resp["status"])
            mock_hw_init.assert_called_once()
            mock_hw_run_handler.assert_called_once()

        for event in EVENTS["BAD"]:
            mock_hw_init.reset_mock()
            mock_hw_run_handler.reset_mock()

            expected_error = event[1]
            event = _get_event(event[0])
            resp = _handler_wrapper(event, get_mock_context())
            resp = json.loads(resp)
            self.assertEqual("FAILED", resp["status"])
            self.assertEqual(expected_error, resp["errorCode"])

    def test_handler_wrapper_get_handler(self):
        for event in EVENTS["SYNC-GOOD"]:
            mock_rhp = mock.Mock()
            h_wrap = HandlerWrapper(_get_event(event), get_mock_context(), mock_rhp)
            handler = h_wrap._get_handler("mock_handler")
            self.assertEqual(True, isinstance(handler, types.FunctionType))

        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )

        with self.assertRaises(exceptions.InternalFailure):
            h_wrap._get_handler("non-existant-module")

        with self.assertRaises(exceptions.InternalFailure):
            h_wrap._action = "nonexistant"
            h_wrap._get_handler("cfn_resource.mock_handler")

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish")
    def test_run_handler_good(self, mock_metric_publish, mock_get_handler):
        for event in EVENTS["SYNC-GOOD"]:
            mock_rhp = mock.Mock()
            mock_metric_publish.reset_mock()
            mock_get_handler.reset_mock()
            h_wrap = HandlerWrapper(_get_event(event), get_mock_context(), mock_rhp)
            resp = h_wrap.run_handler()
            mock_get_handler.assert_called_once()
            mock_metric_publish.assert_called_once()
            self.assertEqual(Status.SUCCESS, resp.status)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler_reschedule,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    @mock.patch(
        "cfn_resource.scheduler.CloudWatchScheduler.reschedule",
        autospec=True,
        return_value=None,
    )
    def test_good_run_handler_reschedule(
        self, mock_scheduler, mock_metric_publish, mock_get_handler
    ):
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )
        resp = h_wrap.run_handler()
        mock_get_handler.assert_called_once()
        mock_metric_publish.assert_called_once()
        mock_scheduler.assert_called_once()
        self.assertEqual(Status.IN_PROGRESS, resp.status)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    def test_good_run_handler_sam_local(self, mock_metric_publish, mock_get_handler):
        os.environ["AWS_SAM_LOCAL"] = "true"
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )
        resp = h_wrap.run_handler()
        del os.environ["AWS_SAM_LOCAL"]
        mock_get_handler.assert_called_once()
        mock_metric_publish.assert_not_called()
        self.assertEqual(Status.SUCCESS, resp.status)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    def test_run_handler_unhandled_exception(
        self, mock_metric_publish, mock_get_handler
    ):
        mock_get_handler.side_effect = ValueError("blah")
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )
        resp = h_wrap.run_handler()
        mock_get_handler.assert_called_once()
        mock_metric_publish.assert_called_once()
        self.assertEqual(Status.FAILED, resp.status)
        self.assertEqual("InternalFailure", resp.errorCode)
        self.assertEqual("ValueError: blah", resp.message)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    def test_run_handler_handled_exception(self, mock_metric_publish, mock_get_handler):
        # handler fails with exception in cfn_resource.exceptions
        mock_get_handler.side_effect = exceptions.AccessDenied("blah")
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )
        resp = h_wrap.run_handler()
        mock_get_handler.assert_called_once()
        mock_metric_publish.assert_called_once()
        self.assertEqual(Status.FAILED, resp.status)
        self.assertEqual("AccessDenied", resp.errorCode)
        self.assertEqual("AccessDenied: blah", resp.message)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    def test_run_handler_metrics_fail(self, mock_metric_publish, mock_get_handler):
        mock_metric_publish.side_effect = ValueError("blah")
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(
            _get_event(EVENTS["SYNC-GOOD"][0]), get_mock_context(), mock_rhp
        )
        resp = h_wrap.run_handler()
        mock_get_handler.assert_called_once()
        mock_metric_publish.assert_called_once()
        self.assertEqual(Status.FAILED, resp.status)
        self.assertEqual("InternalFailure", resp.errorCode)
        self.assertEqual("ValueError: blah", resp.message)

    @mock.patch(
        "cfn_resource.handler_wrapper.HandlerWrapper._get_handler",
        autospec=True,
        return_value=mock_handler_local_callback,
    )
    @mock.patch("cfn_resource.metrics.Metrics.publish", autospec=True)
    @mock.patch(
        "cfn_resource.scheduler.CloudWatchScheduler.reschedule",
        autospec=True,
        return_value=None,
    )
    def test_good_run_handler_local_callback(
        self, mock_scheduler, mock_metric_publish, mock_get_handler
    ):
        context = get_mock_context(deadline=datetime.now() + timedelta(seconds=30))
        mock_rhp = mock.Mock()
        h_wrap = HandlerWrapper(_get_event(EVENTS["SYNC-GOOD"][0]), context, mock_rhp)
        resp = h_wrap.run_handler()
        context.get_remaining_time_in_millis.assert_called()
        self.assertGreater(mock_get_handler.call_count, 1)
        mock_metric_publish.assert_called_once()
        mock_scheduler.assert_called_once()
        self.assertEqual(Status.IN_PROGRESS, resp.status)
