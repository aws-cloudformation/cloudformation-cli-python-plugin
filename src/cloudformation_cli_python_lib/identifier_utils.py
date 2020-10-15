import hashlib
import re
from typing import List

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
    requested_lengths: List[int] = [len(clean_stack_name), len(logical_resource_id)]

    available_lengths: List[int] = fair_split(free_chars, requested_lengths)
    chars_for_stack_name: int = available_lengths[0]
    chars_for_resource_name: int = available_lengths[1]

    hash_value: str = _get_hash(client_request_token)

    identifier: str = (
        clean_stack_name[:chars_for_stack_name]
        + ("-" if separate else "")
        + logical_resource_id[:chars_for_resource_name]
        + "-"
        + hash_value[:HASH_LENGTH]
    )
    return identifier


def fair_split(cap: int, buckets: List[int]) -> List[int]:
    remaining: int = cap
    buckets_length: int = len(buckets)

    allocated: List[int] = [0] * buckets_length

    while remaining > 0:
        max_allocation: int = (
            1 if remaining < buckets_length else remaining // buckets_length
        )
        buckets_satisfied: int = 0

        for index in range(0, buckets_length):
            if allocated[index] < buckets[index]:
                increment = min(max_allocation, buckets[index] - allocated[index])
                allocated[index] += increment
                remaining -= increment
            else:
                buckets_satisfied += 1

            if remaining <= 0 or buckets_satisfied == buckets_length:
                return allocated
    return allocated
