import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

# boto3 doesn't have stub files
from boto3 import Session  # type: ignore

from botocore.exceptions import ClientError  # type: ignore

from .utils import HandlerRequest, KitchenSinkEncoder

LOG = logging.getLogger(__name__)


class CloudWatchScheduler:
    def __init__(self, boto3_session: Session):
        self.client = boto3_session.client("events")

    def reschedule_after_minutes(
        self, function_arn: str, minutes_from_now: int, handler_request: HandlerRequest
    ) -> None:
        cron = self._min_to_cron(max(minutes_from_now, 1))
        uuid = uuid4().hex
        rule_name = f"reinvoke-handler-{uuid}"
        target_id = f"reinvoke-target-{uuid}"
        handler_request.requestContext["cloudWatchEventsRuleName"] = rule_name
        handler_request.requestContext["cloudWatchEventsTargetId"] = target_id
        json_request = json.dumps(handler_request.serialize(), cls=KitchenSinkEncoder)
        LOG.info("Scheduling re-invoke at %s (%s)", cron, uuid)
        self.client.put_rule(Name=rule_name, ScheduleExpression=cron, State="ENABLED")
        self.client.put_targets(
            Rule=rule_name,
            Targets=[{"Id": target_id, "Arn": function_arn, "Input": json_request}],
        )

    def cleanup_cloudwatch_events(self, rule_name: str, target_id: str) -> None:
        try:
            if target_id and rule_name:
                self.client.remove_targets(Rule=rule_name, Ids=[target_id])
        except ClientError as e:
            LOG.error(
                "Error cleaning CloudWatchEvents Target (targetId=%s): %s",
                target_id,
                str(e),
            )
        try:
            if rule_name:
                self.client.delete_rule(Name=rule_name, Force=True)
        except ClientError as e:
            LOG.error(
                "Error cleaning CloudWatchEvents (ruleName=%s): %s", rule_name, str(e)
            )

    @staticmethod
    def _min_to_cron(minutes: int) -> str:
        schedule_time = datetime.now() + timedelta(minutes=minutes)
        # add another minute, as per java implementation
        schedule_time = schedule_time + timedelta(minutes=1)
        return schedule_time.strftime("cron('%M %H %d %m ? %Y')")
