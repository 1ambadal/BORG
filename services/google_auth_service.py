import os
import json
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


def _sync_from_db(filename):
    """If filename doesn't exist on disk, look it up in database and write it."""
    from services.db_service import get_setting
    local_path = os.path.join(_ROOT_DIR, filename)
    if not os.path.exists(local_path):
        content = get_setting(f"google_{filename}")
        if content:
            try:
                for path in _save_paths(filename):
                    with open(path, "w") as f:
                        f.write(content if isinstance(content, str) else json.dumps(content))
                logger.info(f"Synchronized {filename} from database to disk.")
            except Exception as e:
                logger.error(f"Failed to sync {filename} from database: {e}")


def _find_path(filename):
    """Return the first existing path for filename (local or project root)."""
    path = None
    if os.path.exists(filename):
        path = filename
    else:
        alt = os.path.join(_ROOT_DIR, filename)
        if os.path.exists(alt):
            path = alt

    if not path:
        _sync_from_db(filename)
        if os.path.exists(filename):
            path = filename
        else:
            alt = os.path.join(_ROOT_DIR, filename)
            if os.path.exists(alt):
                path = alt

    return path


def _save_paths(filename):
    """Return both local and project-root paths to write to."""
    return [filename, os.path.join(_ROOT_DIR, filename)]


def get_google_credentials():
    """Load and auto-refresh credentials from token.json."""
    token_path = _find_path("token.json")
    if not token_path:
        logger.error("No token.json found. Please authorize via the dashboard.")
        return None

    try:
        creds = Credentials.from_authorized_user_file(token_path)
    except Exception as e:
        logger.error("Failed to load token.json: %s", e)
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_json = creds.to_json()
            for path in _save_paths("token.json"):
                with open(path, "w") as f:
                    f.write(token_json)
            logger.info("Refreshed credentials and saved to token.json")
            
            # Save refreshed credentials to database
            from services.db_service import set_setting
            set_setting("google_token.json", token_json)
        except Exception as e:
            logger.error("Failed to refresh Google credentials: %s", e)
            return None

    if not creds or not creds.valid:
        logger.error("No valid Google credentials found.")
        return None

    return creds


def get_auth_status():
    """Return a dict describing credentials + auth state."""
    creds_path = _find_path("credentials.json")
    token_path = _find_path("token.json")

    credentials_configured = creds_path is not None
    credentials_valid = False
    credentials_error = None

    if credentials_configured:
        try:
            with open(creds_path, "r") as f:
                cdata = json.load(f)
            if "web" in cdata:
                credentials_valid = True
            else:
                credentials_error = "Invalid credentials format. Please upload a 'Web application' type credentials.json from Google Cloud Console."
        except Exception as e:
            credentials_error = f"Error reading credentials.json: {e}"

    authenticated = False
    if credentials_valid and token_path:
        try:
            creds = Credentials.from_authorized_user_file(token_path)
            if creds and (creds.valid or (creds.expired and creds.refresh_token)):
                authenticated = True
        except Exception as e:
            logger.error(f"Error reading token.json: {e}")

    return {
        "credentials_configured": credentials_configured,
        "credentials_valid": credentials_valid,
        "credentials_error": credentials_error,
        "authenticated": authenticated,
    }


def save_credentials(content: bytes):
    """Validate and save uploaded credentials.json. Returns (success, error)."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return False, "Uploaded file is not valid JSON."

    if "web" not in data:
        return False, "Invalid credentials. Please upload a 'Web application' type credentials.json (not Desktop app)."

    for path in _save_paths("credentials.json"):
        with open(path, "wb") as f:
            f.write(content)

    # Save to database
    from services.db_service import set_setting
    set_setting("google_credentials.json", content.decode("utf-8"))

    return True, None


def _build_redirect_uri(request):
    """Build the OAuth redirect URI from the request context."""
    base_url = str(request.base_url).rstrip("/")
    # Behind a reverse proxy (ngrok, nginx), use forwarded headers
    fwd_host = request.headers.get("x-forwarded-host")
    fwd_proto = request.headers.get("x-forwarded-proto")
    if fwd_host:
        proto = fwd_proto or "https"
        base_url = f"{proto}://{fwd_host}"
    elif fwd_proto and fwd_proto == "https" and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
    if "localhost" in base_url:
        base_url = base_url.replace("localhost", "127.0.0.1")
    return base_url, f"{base_url}/api/google/callback"


# Store PKCE code verifier between /auth and /callback (single-user app)
_pending_verifier = {}


def get_auth_url(request):
    """Start OAuth flow and return the authorization URL."""
    creds_path = _find_path("credentials.json")
    if not creds_path:
        return None, "credentials.json is missing."

    base_url, redirect_uri = _build_redirect_uri(request)

    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    flow = Flow.from_client_secrets_file(creds_path, scopes=SCOPES, redirect_uri=redirect_uri)
    url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")

    # Persist the code verifier so exchange_code can use it
    _pending_verifier["code_verifier"] = flow.code_verifier
    _pending_verifier["redirect_uri"] = redirect_uri

    return url, None


def exchange_code(request, code: str):
    """Exchange the authorization code for credentials. Returns (success, error)."""
    creds_path = _find_path("credentials.json")
    if not creds_path:
        return False, "credentials.json not found."

    # Use the same redirect_uri that was used during auth
    redirect_uri = _pending_verifier.get("redirect_uri")
    if not redirect_uri:
        _, redirect_uri = _build_redirect_uri(request)

    base_url = redirect_uri.rsplit("/api/", 1)[0]

    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    flow = Flow.from_client_secrets_file(creds_path, scopes=SCOPES, redirect_uri=redirect_uri)
    flow.code_verifier = _pending_verifier.pop("code_verifier", None)
    _pending_verifier.pop("redirect_uri", None)
    flow.fetch_token(code=code)

    token_json = flow.credentials.to_json()
    for path in _save_paths("token.json"):
        with open(path, "w") as f:
            f.write(token_json)

    # Save to database
    from services.db_service import set_setting
    set_setting("google_token.json", token_json)

    return True, None


def disconnect():
    """Delete token.json files. Returns True if anything was deleted."""
    # Delete from database
    from services.db_service import set_setting
    set_setting("google_token.json", None)

    deleted = False
    for path in _save_paths("token.json"):
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted = True
            except Exception as e:
                logger.error(f"Failed to delete {path}: {e}")
    return deleted
