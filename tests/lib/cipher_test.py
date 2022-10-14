# pylint: disable=wrong-import-order,line-too-long
from unittest.mock import Mock, patch

import pytest
from cloudformation_cli_python_lib.cipher import KmsCipher
from cloudformation_cli_python_lib.exceptions import _EncryptionError
from cloudformation_cli_python_lib.utils import Credentials

from aws_encryption_sdk.exceptions import AWSEncryptionSDKClientError


def mock_session():
    return Mock(spec_set=["client"])


def test_create_kms_cipher():
    with patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.StrictAwsKmsMasterKeyProvider",
        autospec=True,
    ), patch("boto3.client", autospec=True):
        cipher = KmsCipher("encryptionKeyArn", "encryptionKeyRole")
    assert cipher


def test_decrypt_credentials_success():
    expected_credentials = {
        "accessKeyId": "IASAYK835GAIFHAHEI23",
        "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5poh2O0",
        "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DH"
        "fW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg",
    }

    with patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.StrictAwsKmsMasterKeyProvider",
        autospec=True,
    ), patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.EncryptionSDKClient.decrypt"
    ) as mock_decrypt, patch(
        "boto3.client", autospec=True
    ):
        mock_decrypt.return_value = (
            b'{"accessKeyId": "IASAYK835GAIFHAHEI23", "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5poh2O0", "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DHfW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg"}',  # noqa: B950
            Mock(),
        )
        cipher = KmsCipher("encryptionKeyArn", "encryptionKeyRole")

        credentials = cipher.decrypt_credentials(
            "ewogICAgICAgICAgICAiYWNjZXNzS2V5SWQiOiAiSUFTQVlLODM1R0FJRkhBSEVJMjMiLAogICAg"
        )
    assert Credentials(**expected_credentials) == credentials


def test_decrypt_credentials_fail():
    with patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.StrictAwsKmsMasterKeyProvider",
        autospec=True,
    ), patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.EncryptionSDKClient.decrypt"
    ) as mock_decrypt, pytest.raises(
        _EncryptionError
    ) as excinfo, patch(
        "boto3.client", autospec=True
    ):
        mock_decrypt.side_effect = AWSEncryptionSDKClientError()
        cipher = KmsCipher("encryptionKeyArn", "encryptionKeyRole")
        cipher.decrypt_credentials(
            "ewogICAgICAgICAgICAiYWNjZXNzS2V5SWQiOiAiSUFTQVlLODM1R0FJRkhBSEVJMjMiLAogICAg"
        )
    assert str(excinfo.value) == "Failed to decrypt credentials."


def test_decrypt_credentials_returns_null_fail():
    with patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.StrictAwsKmsMasterKeyProvider",
        autospec=True,
    ), patch(
        "cloudformation_cli_python_lib.cipher.aws_encryption_sdk.EncryptionSDKClient.decrypt"
    ) as mock_decrypt, pytest.raises(
        _EncryptionError
    ) as excinfo, patch(
        "boto3.client", autospec=True
    ):
        mock_decrypt.return_value = (
            b"null",
            Mock(),
        )
        cipher = KmsCipher("encryptionKeyArn", "encryptionKeyRole")
        cipher.decrypt_credentials(
            "ewogICAgICAgICAgICAiYWNjZXNzS2V5SWQiOiAiSUFTQVlLODM1R0FJRkhBSEVJMjMiLAogICAg"
        )
    assert (
        str(excinfo.value)
        == "Failed to decrypt credentials. Decrypted credentials are 'null'."
    )


@pytest.mark.parametrize(
    "encryption_key_arn,encryption_key_role",
    [
        (None, "encryptionKeyRole"),
        ("encryptionKeyArn", None),
        (None, None),
    ],
)
def test_decrypt_unencrypted_credentials_success(
    encryption_key_arn, encryption_key_role
):
    expected_credentials = {
        "accessKeyId": "IASAYK835GAIFHAHEI23",
        "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5poh2O0",
        "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DH"
        "fW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg",
    }

    cipher = KmsCipher(encryption_key_arn, encryption_key_role)

    credentials = cipher.decrypt_credentials(
        '{"accessKeyId": "IASAYK835GAIFHAHEI23", "secretAccessKey": "66iOGPN5LnpZorcLr8Kh25u8AbjHVllv5poh2O0", "sessionToken": "lameHS2vQOknSHWhdFYTxm2eJc1JMn9YBNI4nV4mXue945KPL6DHfW8EsUQT5zwssYEC1NvYP9yD6Y5s5lKR3chflOHPFsIe6eqg"}'  # noqa: B950
    )
    assert Credentials(**expected_credentials) == credentials


@pytest.mark.parametrize(
    "encryption_key_arn,encryption_key_role",
    [
        (None, "encryptionKeyRole"),
        ("encryptionKeyArn", None),
        (None, None),
    ],
)
def test_decrypt_unencrypted_credentials_fail(encryption_key_arn, encryption_key_role):
    cipher = KmsCipher(encryption_key_arn, encryption_key_role)

    credentials = cipher.decrypt_credentials("{ Not JSON")  # noqa: B950
    assert not credentials
