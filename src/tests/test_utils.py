import json
import logging
import os
import random
import string
import unittest
from datetime import datetime
from unittest import mock

from cfn_resource.utils import setup_json_logger, JsonFormatter, get_log_level_from_env, valid_log_level, _serialize, \
    is_sam_local


class TestUtils(unittest.TestCase):

    def test_logging_boto_explicit(self):
        logger = logging.getLogger('2')
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        setup_json_logger(level='DEBUG', boto_level='CRITICAL')
        for logger in ['boto', 'boto3', 'botocore', 'urllib3']:
            b_logger = logging.getLogger(logger)
            self.assertEqual(b_logger.level, 50)

    def test_logging_json(self):
        logger = logging.getLogger('3')
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        setup_json_logger(level='DEBUG', RequestType='ContainerInit')
        for handler in logging.root.handlers:
            self.assertEqual(JsonFormatter, type(handler.formatter))

    def test_logging_boto_implicit(self):
        logger = logging.getLogger('4')
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        setup_json_logger(level='DEBUG', RequestType='ContainerInit')
        for logger in ['boto', 'boto3', 'botocore', 'urllib3']:
            b_logger = logging.getLogger(logger)
            self.assertEqual(40, b_logger.level)

    def test_logging_json_keys(self):
        with self.assertLogs() as ctx:
            logger = logging.getLogger()
            handler = logging.StreamHandler()
            logger.addHandler(handler)
            setup_json_logger(level='DEBUG', RequestType='ContainerInit')
            logger.info("test")
            logs = json.loads(ctx.output[0])
        self.assertEqual(["timestamp", "level", "location", "RequestType", "message"], list(logs.keys()))

    def test_logging_json_parse_message(self):
        with self.assertLogs() as ctx:
            logger = logging.getLogger()
            handler = logging.StreamHandler()
            logger.addHandler(handler)
            setup_json_logger(level='DEBUG', RequestType='ContainerInit')
            logger.info("{}")
            logs = json.loads(ctx.output[0])
        self.assertEqual({}, logs["message"])

    def test_logging_json_exception(self):
        with self.assertLogs() as ctx:
            logger = logging.getLogger()
            handler = logging.StreamHandler()
            logger.addHandler(handler)
            setup_json_logger(level='DEBUG', RequestType='ContainerInit')
            try:
                1 + 't'
            except TypeError:
                logger.info("[]", exc_info=True)
            logs = json.loads(ctx.output[0])
        self.assertIn("exception", logs.keys())

    @mock.patch('cfn_resource.utils.valid_log_level')
    def test_get_log_level_from_env(self, mock_valid_log_level):
        env_name = ''.join(random.choices(string.ascii_uppercase, k=16))
        try:
            os.environ[env_name] = 'critical'
            lvl = get_log_level_from_env(env_name)
            self.assertEqual(logging.getLevelName(logging.CRITICAL), lvl)
            mock_valid_log_level.assert_called_once()
        finally:
            del os.environ[env_name]

    @mock.patch('cfn_resource.utils.valid_log_level', return_value=False)
    def test_get_log_level_from_env_invalid_should_default(self, mock_valid_log_level):
        env_name = ''.join(random.choices(string.ascii_uppercase, k=16))
        lvl = get_log_level_from_env(env_name)
        self.assertEqual(logging.getLevelName(logging.WARNING), lvl)
        mock_valid_log_level.assert_called_once()

    def test_valid_log_level(self):
        self.assertEqual(True, valid_log_level('DEBUG'))
        self.assertEqual(False, valid_log_level('NONE'))

    def test_serialize(self):
        now = datetime.now()
        now_t = now.date()
        now_d = now.time()

        def test_func_serialize():
            pass

        class TestClassSerialize:
            pass

        method_wrapper_str = str(_serialize(TestClassSerialize().__init__))
        method_wrapper_str_prefix = "<method-wrapper '__init__' of TestClassSerialize object at "
        self.assertEqual("string", _serialize("string"))
        self.assertEqual(1, _serialize(1))
        self.assertEqual(1.1, _serialize(1.1))
        self.assertEqual(True, _serialize(True))
        self.assertEqual(None, _serialize(None))
        self.assertEqual(now.isoformat(), _serialize(now))
        self.assertEqual(now_d.isoformat(), _serialize(now_d))
        self.assertEqual(now_t.isoformat(), _serialize(now_t))
        self.assertEqual({}, _serialize(test_func_serialize))
        self.assertEqual({}, _serialize(TestClassSerialize()))
        self.assertEqual(True, method_wrapper_str.startswith(method_wrapper_str_prefix))

    def test_is_sam_local(self):
        env_name = ''.join(random.choices(string.ascii_uppercase, k=16))
        try:
            self.assertEqual(False, is_sam_local(env_name))
            os.environ[env_name] = 'true'
            self.assertEqual(True, is_sam_local(env_name))
            os.environ[env_name] = 'false'
            self.assertEqual(False, is_sam_local(env_name))
        finally:
            del os.environ[env_name]
