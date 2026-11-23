"""Home Assistant add-on entrypoint: map add-on options onto anki-sync-mcp settings and start it.

Runs as root only long enough to give the server's user ownership of /data, then drops to that
user and execs the server.
"""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

_DATA = Path(os.environ.get("ADDON_DATA", "/data"))
_OPTIONS = _DATA / "options.json"
_COLLECTION = _DATA / "collection.anki2"
_UID = _GID = 10001
_LOCAL_HOSTS = "localhost,localhost:*,127.0.0.1,127.0.0.1:*"


def _environment(options: dict) -> dict[str, str]:
    host = urlsplit(options["public_url"]).netloc
    env = {
        "MCP_AUTH_MODE": "builtin",
        "MCP_PUBLIC_URL": options["public_url"],
        "MCP_OAUTH_PASSWORD_HASH": options["password_hash"],
        "MCP_SCOPES": options["scopes"],
        "MCP_ALLOWED_HOSTS": f"{_LOCAL_HOSTS},{host}",
        "ANKI_COLLECTION_PATH": str(_COLLECTION),
        "LOG_LEVEL": options["log_level"],
    }
    username = options.get("sync_username") or ""
    password = options.get("sync_password") or ""
    if username:
        env["ANKI_SYNC_USERNAME"] = username
        env["ANKI_BOOTSTRAP_MODE"] = "download_if_empty"
    if password:
        env["ANKI_SYNC_PASSWORD"] = password
    return env


def _give_data_to_server_user() -> None:
    for root, _, files in os.walk(_DATA):
        for path in [root, *(os.path.join(root, name) for name in files)]:
            if path != str(_OPTIONS) and os.lstat(path).st_uid != _UID:
                os.lchown(path, _UID, _GID)


def main() -> None:
    options = json.loads(_OPTIONS.read_text(encoding="utf-8"))
    env = _environment(options)
    _give_data_to_server_user()
    os.setgroups([])
    os.setgid(_GID)
    os.setuid(_UID)
    os.environ.update(env)
    os.environ["HOME"] = "/app"
    os.execvp("anki-mcp", ["anki-mcp"])


if __name__ == "__main__":
    main()
