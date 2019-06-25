class Codes:
    # an unexpected error occurred within the handler
    INTERNAL_FAILURE = "InternalFailure"
    # the request was unable to be completed due to networking issues, such as failure
    # to receive a response from the server. Handlers SHOULD retry on network
    # failures using exponential backoff in order to be resilient to transient
    # issues.
    NETWORK_FAILURE = "NetworkFailure"
    # a generic exception from the downstream service
    SERVICE_EXCEPTION = "ServiceException"
    # the handler timed out waiting for the downstream service to perform an operation
    SERVICE_TIMEOUT = "ServiceTimeout"
    # a non-transient resource limit was reached on the service side
    SERVICE_LIMIT_EXCEEDED = "ServiceLimitExceeded"
    # the resource is temporarily in an inoperable state
    NOT_READY = "NotReady"
    # the request was throttled by the downstream service. Handlers SHOULD retry on
    # service throttling using exponential backoff in order to be resilient to
    # transient throttling.
    THROTTLING = "Throttling"
    # the specified resource does not exist, or is in a terminal, inoperable, and
    # irrecoverable state
    NOT_FOUND = "NotFound"
    # the customer tried perform an update to a property that is not updatable (only
    # applicable to UpdateHandler)
    NOT_UPDATABLE = "NotUpdatable"
    # the handler completed without making any modifying API calls (only applicable to
    # Update handler)
    NO_OPERATION_TO_PERFORM = "NoOperationToPerform"
    # the customer's provided credentials were invalid
    INVALID_CREDENTIALS = "InvalidCredentials"
    # the customer has insufficient permissions to perform this action
    ACCESS_DENIED = "AccessDenied"
    # a generic exception caused by invalid input from the customer
    INVALID_REQUEST = 'InvalidRequest'
    # a resource create request failed for an existing entity (only applicable to
    # CreateHandler) Handlers MUST return this error when duplicate creation requests
    # are received.
    ALREADY_EXISTS = "AlreadyExists"

    @classmethod
    def is_handled(cls, e: Exception):
        if type(e).__name__ in [
            v
            for k, v in Codes.__dict__.items()
            if isinstance(v, str) and not v.startswith("_")
        ]:
            return True
        return False


class CfnResourceBaseException(Exception):
    pass


class InternalFailure(CfnResourceBaseException):
    pass


class NetworkFailure(CfnResourceBaseException):
    pass


class ServiceException(CfnResourceBaseException):
    pass


class ServiceTimeout(CfnResourceBaseException):
    pass


class ServiceLimitExceeded(CfnResourceBaseException):
    pass


class NotReady(CfnResourceBaseException):
    pass


class Throttling(CfnResourceBaseException):
    pass


class NotFound(CfnResourceBaseException):
    pass


class NotUpdatable(CfnResourceBaseException):
    pass


class NoOperationToPerform(CfnResourceBaseException):
    pass


class InvalidCredentials(CfnResourceBaseException):
    pass


class AccessDenied(CfnResourceBaseException):
    pass


class InvalidRequest(CfnResourceBaseException):
    pass


class AlreadyExists(CfnResourceBaseException):
    pass
