import os
from requests_oauthlib import OAuth2Session

OSM_URL = os.environ.get("OSM_URL", "https://openstreetmap.204-168-242-139.nip.io")

CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("falta CLIENT_ID / CLIENT_SECRET (export antes de correr)")

oauth = OAuth2Session(
    CLIENT_ID,
    redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    scope=["read_prefs", "read_gpx", "write_gpx"],
)

auth_url, _ = oauth.authorization_url(f"{OSM_URL}/oauth2/authorize")
print(f"open this link in your browser:\n{auth_url}\n")

code = input("paste the authorization code here: ")

token = oauth.fetch_token(
    f"{OSM_URL}/oauth2/token",
    code=code,
    client_secret=CLIENT_SECRET,
)
print(f"\naccess token:\n{token['access_token']}")
