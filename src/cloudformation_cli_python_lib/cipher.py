# boto3, botocore, aws_encryption_sdk don't have stub files
import boto3  # type: ignore

import aws_encryption_sdk  # type: ignore
import base64
import json
import uuid
from aws_encryption_sdk.exceptions import AWSEncryptionSDKClientError  # type: ignore
from aws_encryption_sdk.identifiers import CommitmentPolicy  # type: ignore
from botocore.client import BaseClient  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.credentials import (  # type: ignore
    DeferredRefreshableCredentials,
    create_assume_role_refresher,
)
from botocore.session import Session, get_session  # type: ignore
from typing import Optional

from .exceptions import _EncryptionError
from .utils import Credentials


class Cipher:
    def decrypt_credentials(
        self, encrypted_credentials: str
    ) -> Optional[Credentials]:  # pragma: no cover
        raise NotImplementedError()


class KmsCipher(Cipher):
    """
    This class is decrypted the encrypted credentials sent by CFN in the request:
        * Credentials are encrypted service side
        * The encrypted credentials along with an IAM role
        * Credentials are decrypetd using the AWS Encryption
          SDK while assuming the encryption role
    """

    def __init__(
        self, encryption_key_arn: Optional[str], encryption_key_role: Optional[str]
    ) -> None:
        self._crypto_client = aws_encryption_sdk.EncryptionSDKClient(
            commitment_policy=CommitmentPolicy.FORBID_ENCRYPT_ALLOW_DECRYPT
        )
        self._key_provider = None
        if encryption_key_arn and encryption_key_role:
            self._key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
                key_ids=[encryption_key_arn],
                botocore_session=self._get_assume_role_session(
                    encryption_key_role, self._create_client()
                ),
            )

    def decrypt_credentials(
        self, encrypted_credentials: Optional[str]
    ) -> Optional[Credentials]:
        if not encrypted_credentials:
            return None

        # If no kms key and role arn provided
        # Attempt to deserialize unencrypted credentials
        # This happens during contract tests
        if not self._key_provider:
            try:
                credentials_data = json.loads(encrypted_credentials)
                return Credentials(**credentials_data)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None

        try:
            decrypted_credentials, _decryptor_header = self._crypto_client.decrypt(
                source=base64.b64decode(encrypted_credentials),
                key_provider=self._key_provider,
            )
            credentials_data = json.loads(decrypted_credentials.decode("UTF-8"))
            if credentials_data is None:
                raise _EncryptionError(
                    "Failed to decrypt credentials. Decrypted credentials are 'null'."
                )

            return Credentials(**credentials_data)
        except (
            AWSEncryptionSDKClientError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as e:
            raise _EncryptionError("Failed to decrypt credentials.") from e

    @staticmethod
    def _get_assume_role_session(
        encryption_key_role: str, client: BaseClient
    ) -> Session:
        params = {"RoleArn": encryption_key_role, "RoleSessionName": str(uuid.uuid4())}

        session = get_session()
        # pylint: disable=protected-access
        session._credentials = DeferredRefreshableCredentials(
            refresh_using=create_assume_role_refresher(client, params),
            method="sts-assume-role",
        )
        return session

    @staticmethod
    def _create_client() -> BaseClient:
        return boto3.client(
            "sts",
            config=Config(
                connect_timeout=10, read_timeout=60, retries={"max_attempts": 3}
            ),
        )
