# boto3 doesn't have stub files
from typing import Optional

from boto3.session import Session  # type: ignore

from .utils import Credentials


class SessionProxy:
    def __init__(self, session: Session):
        self.client = session.client
        self.resource = session.resource


def _get_boto_session(
    credentials: Optional[Credentials], region: Optional[str] = None
) -> Optional[SessionProxy]:
    if not credentials:
        return None
    session = Session(
        aws_access_key_id=credentials.accessKeyId,
        aws_secret_access_key=credentials.secretAccessKey,
        aws_session_token=credentials.sessionToken,
        region_name=region,
    )
    return SessionProxy(session)
