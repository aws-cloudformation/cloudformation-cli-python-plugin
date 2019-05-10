import json
import logging
import os
from datetime import date, time, datetime

LOG = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):

    def __init__(self, **kwargs):
        super(JsonFormatter, self).__init__()
        self.format_dict = {
            'timestamp': '%(asctime)s',
            'level': '%(levelname)s',
            'location': '%(name)s.%(funcName)s:%(lineno)d',
        }
        self.format_dict.update(kwargs)
        self.default_json_formatter = kwargs.pop(
            'json_default', _serialize)

    def format(self, record):
        record_dict = record.__dict__.copy()
        record_dict['asctime'] = self.formatTime(record)

        log_dict = {
            k: v % record_dict
            for k, v in self.format_dict.items()
            if v
        }

        if isinstance(record_dict['msg'], dict):
            log_dict['message'] = record_dict['msg']
        else:
            log_dict['message'] = record.getMessage()
            try:
                log_dict['message'] = json.loads(log_dict['message'])
            except (TypeError, ValueError):
                pass

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            log_dict['exception'] = record.exc_text

        json_record = json.dumps(log_dict, default=_serialize)

        if hasattr(json_record, 'decode'):
            json_record = json_record.decode('utf-8')

        return json_record


def setup_json_logger(level=logging.DEBUG, boto_level=logging.ERROR, formatter_cls=JsonFormatter, **kwargs):
    if formatter_cls:
        for handler in logging.root.handlers:
            handler.setFormatter(formatter_cls(**kwargs))

    logging.root.setLevel(level)

    logging.getLogger('boto').setLevel(boto_level)
    logging.getLogger('boto3').setLevel(boto_level)
    logging.getLogger('botocore').setLevel(boto_level)
    logging.getLogger('urllib3').setLevel(boto_level)


def get_log_level_from_env(env_var_name, default=logging.WARNING):
    log_level = str(os.environ.get(env_var_name)).upper()
    if not valid_log_level(log_level):
        log_level = logging.getLevelName(default)
    return log_level


def valid_log_level(level):
    if level in logging._nameToLevel.keys():  # pylint: disable=protected-access
        return True
    LOG.warning('Invalid log level %s, using default', level)
    return False


def _serialize(obj):
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.isoformat()
    if '__dict__' in dir(obj):
        return obj.__dict__
    return str(obj)


def is_sam_local(env_var='AWS_SAM_LOCAL'):
    if os.environ.get(env_var) == 'true':
        return True
    return False
