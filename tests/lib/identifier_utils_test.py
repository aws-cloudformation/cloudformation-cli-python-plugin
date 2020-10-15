import pytest
from cloudformation_cli_python_lib.identifier_utils import generate_resource_identifier


def test_generated_name_with_stack_name_and_long_logical_id():
    result: str = generate_resource_identifier(
        stack_id_or_name="my-custom-stack-name",
        logical_resource_id="my-long-long-long-long-long-logical-id-name",
        client_request_token="123456789",
        max_length=36,
    )
    assert len(result) == 36
    assert result.startswith("my-custom-s-my-long-lon-")


def test_generated_name_with_stack_id_and_long_logical_id():
    result: str = generate_resource_identifier(
        stack_id_or_name="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack-name/084c0bd1-082b-11eb-afdc-0a2fadfa68a5",  # noqa: B950 # pylint: disable=line-too-long
        logical_resource_id="my-long-long-long-long-long-logical-id-name",
        client_request_token="123456789",
        max_length=36,
    )
    assert len(result) == 36
    assert result.startswith("my-stack-na-my-long-lon-")


def test_generated_name_with_short_stack_name_and_short_logical_id():
    result: str = generate_resource_identifier(
        stack_id_or_name="abc",
        logical_resource_id="abc",
        client_request_token="123456789",
        max_length=255,
    )
    assert len(result) == 20  # "abc" + "-" + "abc" + "-" + 12 char hash
    assert result.startswith("abc-abc-")


def test_generated_name_with_max_len_shorter_than_preferred():
    result: str = generate_resource_identifier(
        stack_id_or_name="abc",
        logical_resource_id="abc",
        client_request_token="123456789",
        max_length=16,
    )
    assert len(result) == 16
    assert result.startswith("aba-f7c3bc1d808e")


def test_generated_name_with_invalid_len():
    with pytest.raises(Exception) as excinfo:
        generate_resource_identifier(
            stack_id_or_name="my-stack-name",
            logical_resource_id="my-logical-id",
            client_request_token="123456789",
            max_length=13,
        )
    assert "Cannot generate resource IDs shorter than" in str(excinfo.value)
