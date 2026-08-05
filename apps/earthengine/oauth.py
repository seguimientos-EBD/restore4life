"""Wraps ee.oauth to run the same code-paste flow as `ee.Authenticate()`,
storing the resulting refresh token per-user instead of in a local file.
"""
import json
import urllib.request

from ee import oauth as ee_oauth


def build_authorization_url():
    """Returns (auth_url, code_verifier). Store code_verifier server-side
    (session) and pair it with the code the user pastes back."""
    flow = ee_oauth.Flow(auth_mode='notebook')
    return flow.auth_url, flow.code_verifier


def exchange_code(auth_code, code_verifier):
    """Exchanges the pasted authorization code for a refresh token.

    Returns (refresh_token, client_id, client_secret).

    In 'notebook' auth_mode, code_verifier is actually
    'request_id:token_verifier:client_verifier': the per-session client_id/
    client_secret must be fetched from Earth Engine's server first (proving
    ownership via request_id + client_verifier), and only then can the code
    be redeemed with the token_verifier. See ee.oauth._obtain_and_write_token,
    which this mirrors minus the local-file write.

    Those fetched credentials must be stored with the token: they are per-session,
    so refreshing later against the static ee_oauth.CLIENT_ID fails with
    'unauthorized_client'. ee itself writes all three to its credentials file.
    """
    client_info = {}
    if ':' in code_verifier:
        request_id, code_verifier, client_verifier = code_verifier.split(':')
        fetch_request = urllib.request.Request(
            ee_oauth.FETCH_URL,
            data=json.dumps({'request_id': request_id, 'client_verifier': client_verifier}).encode(),
            headers={'Content-Type': 'application/json; charset=UTF-8'},
        )
        fetched_info = json.loads(urllib.request.urlopen(fetch_request).read().decode())
        if 'error' in fetched_info:
            raise Exception(f"Cannot authenticate: {fetched_info['error']}")
        client_info = {k: fetched_info[k] for k in ('client_id', 'client_secret')}

    refresh_token = ee_oauth.request_token(auth_code.strip(), code_verifier, **client_info)
    return (
        refresh_token,
        client_info.get('client_id') or ee_oauth.CLIENT_ID,
        client_info.get('client_secret') or ee_oauth.CLIENT_SECRET,
    )