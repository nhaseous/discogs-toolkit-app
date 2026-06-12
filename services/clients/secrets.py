"""Loads sensitive config from Google Secret Manager into the environment.

On App Engine the runtime service account reads each secret via its metadata-
server credentials (Application Default Credentials) and copies the value into
``os.environ`` so the rest of the app keeps reading it with ``os.environ.get``
— no other module needs to know secrets now come from Secret Manager.

Off App Engine (local dev, the macOS desktop app) there is no metadata server,
so this is a no-op: secrets continue to come from ``.env`` / real environment
variables / Keychain exactly as before. Set ``USE_SECRET_MANAGER=1`` to opt a
local run into Secret Manager (requires ``GOOGLE_APPLICATION_CREDENTIALS`` or
``gcloud auth application-default login``).

Values already present in the environment are never overwritten, so a populated
``app.yaml`` env var still wins — which makes the rollout safe to deploy before
the secrets exist and before they're trimmed out of ``app.yaml``.
"""

import logging
import os

# Secret IDs in Secret Manager match these env var names one-to-one.
_SECRET_NAMES = (
    'FLASK_SECRET_KEY',
    'DISCOGS_CONSUMER_KEY',
    'DISCOGS_CONSUMER_SECRET',
    'GOOGLE_SA_KEY_B64',
)


def _enabled():
    # GAE sets GAE_ENV=standard on the runtime; opt local runs in explicitly.
    return os.environ.get('GAE_ENV', '').startswith('standard') \
        or os.environ.get('USE_SECRET_MANAGER') == '1'


def _project():
    return (os.environ.get('GCP_PROJECT')
            or os.environ.get('GOOGLE_CLOUD_PROJECT')
            or 'discogs-toolkit')


def load_secrets():
    """Hydrate ``os.environ`` with Secret Manager values when enabled.

    Best-effort: any failure (missing library, no permission, absent secret) is
    logged and skipped so the app can still fall back to whatever env vars exist.
    """
    if not _enabled():
        return

    try:
        from google.cloud import secretmanager
    except ImportError:
        logging.warning("google-cloud-secret-manager not installed; "
                        "skipping Secret Manager load")
        return

    try:
        client = secretmanager.SecretManagerServiceClient()
    except Exception as e:  # credential / transport init failure
        logging.warning("Could not initialize Secret Manager client: %s", e)
        return

    project = _project()
    for name in _SECRET_NAMES:
        # Never override a value already set explicitly in the environment.
        if os.environ.get(name):
            continue
        path = f"projects/{project}/secrets/{name}/versions/latest"
        try:
            resp = client.access_secret_version(name=path)
            os.environ[name] = resp.payload.data.decode('utf-8')
        except Exception as e:
            logging.warning("Could not load secret '%s': %s", name, e)
