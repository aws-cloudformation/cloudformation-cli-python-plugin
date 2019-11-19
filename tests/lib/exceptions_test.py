import importlib
import inspect

import pytest
from cloudformation_cli_python_lib.interface import HandlerErrorCode, OperationStatus


def get_public_exceptions(module_name="cloudformation_cli_python_lib.exceptions"):
    module = importlib.import_module(module_name)

    def local_public_class(member):
        return (
            inspect.isclass(member)
            and member.__module__ == module_name
            and not member.__name__.startswith("_")
        )

    return inspect.getmembers(module, local_public_class)


EXCEPTIONS = get_public_exceptions()


def test_all_error_codes_have_exceptions():
    classes = {name for name, ex in EXCEPTIONS}
    members = set(HandlerErrorCode.__members__)
    assert classes == members


@pytest.mark.parametrize("name, ex", EXCEPTIONS)
def test_exception_to_progress_event(name, ex):
    try:
        e = ex()
    except TypeError:
        e = ex("Foo::Bar::Baz", "ident")
    progress_event = e.to_progress_event()
    assert progress_event.status == OperationStatus.FAILED
    assert progress_event.errorCode == HandlerErrorCode[name]
