import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from botocore.exceptions import ClientError  # type: ignore

from .boto3_proxy import SessionProxy
from .utils import HandlerRequest, KitchenSinkEncoder

LOG = logging.getLogger(__name__)


def reschedule_after_minutes(
    session: SessionProxy,
    function_arn: str,
    minutes_from_now: int,
    handler_request: HandlerRequest,
) -> None:
    client = session.client("events")
    cron = _min_to_cron(max(minutes_from_now, 1))
    uuid = str(uuid4())
    rule_name = f"reinvoke-handler-{uuid}"
    target_id = f"reinvoke-target-{uuid}"
    handler_request.requestContext["cloudWatchEventsRuleName"] = rule_name
    handler_request.requestContext["cloudWatchEventsTargetId"] = target_id
    json_request = json.dumps(handler_request.serialize(), cls=KitchenSinkEncoder)
    LOG.info("Scheduling re-invoke at %s (%s)", cron, uuid)
    client.put_rule(Name=rule_name, ScheduleExpression=cron, State="ENABLED")
    client.put_targets(
        Rule=rule_name,
        Targets=[{"Id": target_id, "Arn": function_arn, "Input": json_request}],
    )


def cleanup_cloudwatch_events(
    session: SessionProxy, rule_name: str, target_id: str
) -> None:
    client = session.client("events")
    try:
        if target_id and rule_name:
            client.remove_targets(Rule=rule_name, Ids=[target_id])
    except ClientError as e:
        LOG.error(
            "Error cleaning CloudWatchEvents Target (targetId=%s): %s", target_id, e
        )
    try:
        if rule_name:
            client.delete_rule(Name=rule_name, Force=True)
    except ClientError as e:
        LOG.error(
            "Error cleaning CloudWatchEvents (ruleName=%s): %s", rule_name, str(e)
        )


def _min_to_cron(minutes: int) -> str:
    schedule_time = datetime.now() + timedelta(minutes=minutes)
    # add another minute, as per java implementation
    schedule_time = schedule_time + timedelta(minutes=1)
    return schedule_time.strftime("cron(%M %H %d %m ? %Y)")
