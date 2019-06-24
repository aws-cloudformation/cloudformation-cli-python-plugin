# {{ type_name }}

Congratulations on starting development! Next steps:

1. Write the JSON schema describing your resource, `{{ schema_path.name }}`
2. Implement your resource handlers in `{{ project_path }}/handlers.py`

> Don't modify files in `resource_model/` by hand, any modifications will be overwritten when `generate` or
`package` commandsare run.

Implement CloudFormation resource here. Each function must return a ProgressEvent.

ProgressEvent(
    operation_status=Status.IN_PROGRESS, # Required: must be one of Status.IN_PROGRESS, Status.FAILED, Status.SUCCESS
    # resource_model={}, # Optional: resource model dict, values can be retrieved in CFN with Fn::GetAtt
    # message='', # Optional: message to supply to CloudFormation Stack events
    # error_code='', # Optional: error code (only used in failure) Should be one of cfn_resource.exceptions.Codes
    # callback_context={}, # will be sent to callback invocations as callback_context
    # callback_delay_minutes=0 # setting to a value > 0 will re-call handler after specified time
)

Failures can be passed back to CloudFormation by either raising an exception, preferably one of cfn_resource.exceptions
operation_status to Status.FAILED and error_code to one of cfn_resource.exceptions
