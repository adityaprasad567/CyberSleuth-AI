"""
File storage abstraction for evidence uploads and generated reports.

Two backends, chosen automatically at import time:
  - SUPABASE_URL + SUPABASE_KEY set -> Supabase Storage (a bucket). Use this
    for any real deployment - Render/Railway's local disk is wiped on every
    restart/redeploy, so files saved locally would disappear.
  - Neither set -> local disk under storage/blobs/ (original-ish behavior).

`save_blob` returns an opaque "locator" string - store that (not a raw path)
in the database's file_path column. `read_blob(locator)` works regardless
of which backend originally created it, as long as the same env vars are
still set at read time.
"""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
BUCKET = os.environ.get("SUPABASE_BUCKET", "cybercrime-files")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

LOCAL_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "blobs")
os.makedirs(LOCAL_DIR, exist_ok=True)

_client = None
if USE_SUPABASE:
    from supabase import create_client
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_blob(key: str, data: bytes) -> str:
    """
    key: a path-like identifier, e.g. "evidence/<id>_<filename>" or
    "reports/<filename>". Returns a locator to persist in the DB.
    """
    if USE_SUPABASE:
        # upsert=true so re-uploading the same key (shouldn't normally happen,
        # keys include a uuid) overwrites rather than erroring
        _client.storage.from_(BUCKET).upload(
            key, data, {"content-type": "application/octet-stream", "upsert": "true"}
        )
        return f"supabase://{BUCKET}/{key}"

    path = os.path.join(LOCAL_DIR, key.replace("/", "__"))
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_blob(locator: str) -> bytes:
    if locator.startswith("supabase://"):
        _, rest = locator.split("://", 1)
        bucket, key = rest.split("/", 1)
        return _client.storage.from_(bucket).download(key)
    with open(locator, "rb") as f:
        return f.read()


def blob_exists(locator: str) -> bool:
    try:
        read_blob(locator)
        return True
    except Exception:
        return False


def delete_blob(locator: str):
    try:
        if locator.startswith("supabase://"):
            _, rest = locator.split("://", 1)
            bucket, key = rest.split("/", 1)
            _client.storage.from_(bucket).remove([key])
        elif os.path.exists(locator):
            os.remove(locator)
    except Exception:
        pass  # best-effort cleanup - don't fail the request over it
