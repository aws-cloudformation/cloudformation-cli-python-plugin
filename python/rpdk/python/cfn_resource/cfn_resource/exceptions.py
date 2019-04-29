class CfnResourceBaseException(Exception):
    pass


class CfnResourceInitException(CfnResourceBaseException):
    pass


class CfnResourceInternalError(CfnResourceBaseException):
    pass
