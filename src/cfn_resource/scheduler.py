import json
import logging
import uuid
from datetime import datetime, timedelta

from .boto3_proxy import Boto3Client
from .utils import _serialize, is_sam_local

LOG = logging.getLogger(__name__)


class CloudWatchScheduler:

    def __init__(self, session_config: dict = None, b3=Boto3Client):
        session_config = {} if session_config is None else session_config

        self._cwe_client = b3(**session_config).client('events')

    def reschedule(self, function_arn, event: dict, callback_context: dict, minutes: int):
        reschedule_id = str(uuid.uuid4())
        rule_name = "reinvoke-handler-{}".format(reschedule_id)
        target_id = "reinvoke-target-{}".format(reschedule_id)
        if 'requestContext' not in event.keys():
            event['requestContext'] = {}
        event['requestContext']['cloudWatchEventsRuleName'] = rule_name
        event['requestContext']['cloudWatchEventsTargetId'] = target_id
        if 'invocation' not in event['requestContext']:
            event['requestContext']['invocation'] = 0
        event['requestContext']['invocation'] += 1
        event['requestContext']['callbackContext'] = callback_context
        if is_sam_local():
            LOG.warning("Skipping rescheduling, as invocation is SAM local")
        else:
            self._put_rule(rule_name, minutes)
            self._put_targets(rule_name, target_id, function_arn, json.dumps(event, default=_serialize))

    def _put_rule(self, rule_name: str, minutes: int):
        self._cwe_client.put_rule(
            Name=rule_name,
            ScheduleExpression=self._min_to_cron(minutes),
            State='ENABLED'
        )

    def _put_targets(self, rule_name, target_id, function_arn, input_json):
        self._cwe_client.put_targets(
            Rule=rule_name,
            Targets=[{'Id': target_id, 'Arn': function_arn, 'Input': input_json}]
        )

    def _delete_rule(self, rule_name):
        LOG.debug("Deleting rule %s", rule_name)
        self._cwe_client.delete_rule(Name=rule_name, Force=True)

    def _delete_target(self, rule_name, target_id):
        LOG.debug("Deleting target %s from rule %s", target_id, rule_name)
        self._cwe_client.remove_targets(Rule=rule_name, Ids=[target_id])

    def cleanup(self, event):
        if is_sam_local():
            LOG.warning("Skipping schedule cleanup, as invocation is SAM local")
        else:
            if 'requestContext' not in event.keys():
                LOG.info("No event to clean up")
                return
            if 'cloudWatchEventsRuleName' not in event['requestContext'].keys():
                LOG.info("No event to clean up")
                return
            if 'cloudWatchEventsTargetId' in event['requestContext'].keys():
                self._delete_target(
                    event['requestContext']['cloudWatchEventsRuleName'],
                    event['requestContext']['cloudWatchEventsTargetId']
                )
            else:
                LOG.warning("cloudWatchEventsTargetId missing from requestContext")
            self._delete_rule(event['requestContext']['cloudWatchEventsRuleName'])

    @staticmethod
    def _min_to_cron(minutes):
        schedule_time = datetime.now() + timedelta(minutes=minutes)
        # add another minute, as per java implementation
        schedule_time = schedule_time + timedelta(minutes=1)
        return schedule_time.strftime("cron('%M %H %d %m ? %Y')")
