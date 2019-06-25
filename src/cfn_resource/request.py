class Action:
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    READ = "READ"
    LIST = "LIST"


class RequestContext:  # pylint: disable=too-many-instance-attributes
    def __init__(self, request: dict, context):
        self.aws_account_id = request["awsAccountId"]
        self.region = request["region"]
        self.resource_type = request["resourceType"]
        self.resource_type_version = request["resourceTypeVersion"]
        self.stack_id = request["stackId"]
        self.logical_resource_id = request["requestData"]["logicalResourceId"]
        self.resource_properties = request["requestData"]["resourceProperties"]
        self.system_tags = request["requestData"]["systemTags"]
        self.stack_tags: dict = {}
        if "stackTags" in request["requestData"].keys():
            self.stack_tags = request["requestData"]["stackTags"]
        self.get_remaining_time_in_millis = context.get_remaining_time_in_millis
        self.invocation_count = 0
        if request["requestContext"]:
            self.invocation_count = request["requestContext"]["invocation"]
        self.previous_stack_tags: dict = {}
        if "previousStackTags" in request["requestData"].keys():
            self.previous_stack_tags = request["requestData"]["previousStackTags"]


def extract_event_data(event):
    resource_properties = event["requestData"]["resourceProperties"]
    previous_resource_properties = {}
    callback_context = {}
    if "previousResourceProperties" in event["requestData"]:
        previous_resource_properties = event["requestData"][
            "previousResourceProperties"
        ]
    if event["requestContext"]:
        callback_context = event["requestContext"]["callbackContext"]
    return resource_properties, previous_resource_properties, callback_context
