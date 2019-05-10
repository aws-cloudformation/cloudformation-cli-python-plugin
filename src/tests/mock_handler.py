# pylint: disable=invalid-name

from cfn_resource import ProgressEvent
from cfn_resource.base_resource_model import BaseResourceModel as ResourceModel

SIMPLE_PROGRESS_EVENT = ProgressEvent(status="SUCCESS", resourceModel=ResourceModel())


def _generic_handler(*args):
    return SIMPLE_PROGRESS_EVENT if not args else args[0]


create_handler = _generic_handler  # pylint: disable=invalid-name
update_handler = _generic_handler  # pylint: disable=invalid-name
delete_handler = _generic_handler  # pylint: disable=invalid-name
list_handler = _generic_handler  # pylint: disable=invalid-name
read_handler = _generic_handler  # pylint: disable=invalid-name
