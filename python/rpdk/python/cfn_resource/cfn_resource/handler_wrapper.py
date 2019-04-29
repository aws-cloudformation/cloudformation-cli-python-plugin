import logging
from cfn_resource.exceptions import CfnResourceInitException
from cfn_resource import CfnResource

logger = logging.getLogger(__name__)


def _get_handler(action):
    try:
        import __handler__
    except ModuleNotFoundError:
        raise CfnResourceInitException("__handler__.py does not exist")
    try:
        return getattr(__handler__, "{}_handler".format(action.lower()))
    except AttributeError:
        raise CfnResourceInitException("__handler__.py does not contain a {}_handler function".format(action))


def _handler_wrapper(event, context):
    cfnr = CfnResource()
    try:
        handler = _get_handler(event["action"])
        handler(_event_parse(event, context))
    except Exception as e:
        logger.error(e, exc_info=True)
        cfnr.send_status(status=CfnResource.FAILED, message=str(e))


def _event_parse(event, context):
    # TODO: restructure event
    return event
