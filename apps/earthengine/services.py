import ee
from ee import oauth as ee_oauth
from google.oauth2.credentials import Credentials

from earthengine.models import EarthEngineAccount


class NotConnected(Exception):
    pass


def credentials_for_user(user):
    try:
        account = user.earthengine_account
    except EarthEngineAccount.DoesNotExist:
        raise NotConnected(f'{user} has no Earth Engine account connected')

    # The OAuth client that issued the token is ephemeral ('notebook' flow), so the
    # refresh must go through that one and not ee's static client.
    return account, Credentials(
        None,
        refresh_token=account.refresh_token,
        token_uri=ee_oauth.TOKEN_URI,
        client_id=account.client_id or ee_oauth.CLIENT_ID,
        client_secret=account.client_secret or ee_oauth.CLIENT_SECRET,
        scopes=ee_oauth.SCOPES,
    )


def ee_initialize_for_user(user):
    """Initializes EE for this request using the user's own credentials.

    ee.Initialize() sets process-global state, not per-request state: the
    server must run sync/process-based workers (e.g. gunicorn `sync` class),
    not threaded, or concurrent users' requests can race onto each other's
    credentials.
    """
    account, credentials = credentials_for_user(user)
    ee.Initialize(credentials, project=account.ee_project)
