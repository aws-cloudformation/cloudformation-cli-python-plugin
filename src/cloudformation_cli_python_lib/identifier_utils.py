import hashlib
import re

# from typing import List

STACK_ARN_PATTERN = "^[a-z0-9-:]*stack/[-a-z0-9A-Z]*/[-a-z0-9A-Z]*"

MIN_PHYSICAL_RESOURCE_ID_LENGTH = 15
MIN_PREFERRED_LENGTH = 17
HASH_LENGTH = 12


def _get_hash(client_request_token: str) -> str:
    return hashlib.sha1(str.encode(client_request_token)).hexdigest()  # nosec


def generate_resource_identifier(
    stack_id_or_name: str,
    logical_resource_id: str,
    client_request_token: str,
    max_length: int,
) -> str:
    if max_length < MIN_PHYSICAL_RESOURCE_ID_LENGTH:
        raise Exception(
            f"Cannot generate resource IDs shorter than\
               {MIN_PHYSICAL_RESOURCE_ID_LENGTH} characters."
        )

    stack_name: str = stack_id_or_name

    pattern = re.compile(STACK_ARN_PATTERN)

    if pattern.match(stack_id_or_name):
        stack_name = stack_name.split("/")[1]

    separate: bool = max_length > MIN_PREFERRED_LENGTH

    clean_stack_name: str = stack_name.replace("^-+", "", 1).replace("--", "-")
    free_chars: int = max_length - 13 - (1 if separate else 0)

    chars_for_resource_name: int = min(free_chars // 2, len(logical_resource_id))
    chars_for_stack_name: int = min(
        free_chars - chars_for_resource_name, len(clean_stack_name)
    )

    hash_value: str = _get_hash(client_request_token)

    identifier: str = (
        clean_stack_name[:chars_for_stack_name]
        + ("-" if separate else "")
        + logical_resource_id[:chars_for_resource_name]
        + "-"
        + hash_value[:HASH_LENGTH]
    )
    return identifier
