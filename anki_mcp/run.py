"""Home Assistant add-on entrypoint: map add-on options onto anki-sync-mcp settings and start it.

Runs as root only long enough to move a pre-0.10 install into the multi-user layout and give the
server's user ownership of /data and /config, then drops to that user and runs the MCP server,
with the users panel on the ingress port in the same process.
"""

import json
import os
import sys
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from admin import create_admin_app
from anki_mcp.__main__ import main as serve_mcp
from anki_mcp.config import Settings
from anki_mcp.migrate import migrate_legacy_install
from anki_mcp.oauth import hash_password

_DATA = Path(os.environ.get("ADDON_DATA", "/data"))
_OPTIONS = _DATA / "options.json"
_SMTP_PASSWORD = _DATA / "smtp_password"
_CONFIG = Path(os.environ.get("ADDON_CONFIG", "/config"))
_MEDIA_URL_HOSTS = _CONFIG / "media_url_hosts.txt"
_UID = _GID = 10001
_LOCAL_HOSTS = "localhost,localhost:*,127.0.0.1,127.0.0.1:*"
_INGRESS_PORT = 8099  # Home Assistant's default ingress port, so config.yaml leaves it out
# Options from 0.9 and earlier, read once to carry the owner's account over, then cleared.
_LEGACY_OPTIONS = ("password", "password_hash", "sync_username", "sync_password")


def _environment(options: dict) -> dict[str, str]:
    host = urlsplit(options["public_url"]).netloc
    env = {
        "MCP_PUBLIC_URL": options["public_url"],
        "MCP_SCOPES": options["scopes"],
        "ANKI_ALLOW_SCHEMA_CHANGES": str(bool(options.get("allow_schema_changes", True))).lower(),
        "ANKI_ALLOW_FULL_SYNC": str(bool(options.get("allow_full_sync", True))).lower(),
        "ANKI_MAX_OPEN_COLLECTIONS": str(options.get("max_open_collections", 20)),
        "MCP_ALLOWED_HOSTS": f"{_LOCAL_HOSTS},{host}",
        "ANKI_DATA_DIR": str(_DATA),
        "LOG_LEVEL": options["log_level"],
    }
    if options.get("smtp_host"):
        env.update(
            MCP_SMTP_HOST=options["smtp_host"],
            MCP_SMTP_PORT=str(options.get("smtp_port", 587)),
            MCP_SMTP_SECURITY=options.get("smtp_security", "starttls"),
            MCP_SMTP_USERNAME=options.get("smtp_username") or "",
            MCP_SMTP_FROM=options.get("smtp_from") or "",
        )
        if options.get("smtp_password"):
            env["MCP_SMTP_PASSWORD_FILE"] = str(_SMTP_PASSWORD)
    if _MEDIA_URL_HOSTS.is_file():
        env["ANKI_MEDIA_URL_HOSTS_FILE"] = str(_MEDIA_URL_HOSTS)
    if options.get("https_proxy"):
        env["HTTPS_PROXY"] = options["https_proxy"]
    if options.get("no_proxy"):
        env["NO_PROXY"] = options["no_proxy"]
    return env


def _write_smtp_password(options: dict) -> None:
    password = options.get("smtp_password") or ""
    if not (options.get("smtp_host") and password):
        _SMTP_PASSWORD.unlink(missing_ok=True)
        return
    descriptor = os.open(_SMTP_PASSWORD, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(password)


def _legacy_account(options: dict) -> dict[str, str]:
    """The old single owner's credentials, in the environment names the migration reads."""
    password_hash = options.get("password_hash") or ""
    if not password_hash and options.get("password"):
        password_hash = hash_password(options["password"])
    values = {
        "MCP_OAUTH_PASSWORD_HASH": password_hash,
        "ANKI_SYNC_USERNAME": options.get("sync_username") or "",
        "ANKI_SYNC_PASSWORD": options.get("sync_password") or "",
    }
    return {name: value for name, value in values.items() if value}


def _save_options(options: dict) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if token:
        request = urllib.request.Request(
            "http://supervisor/addons/self/options",
            data=json.dumps({"options": options}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=10).close()
    # Supervisor rewrites this file only on the next start; drop the credentials now.
    _OPTIONS.write_text(json.dumps(options), encoding="utf-8")


def _upgrade(settings: Settings, options: dict) -> None:
    """Move a 0.9 install into users/owner/, then clear the options it no longer uses."""
    legacy = settings.data_dir / "collection.anki2"
    migrate_legacy_install(settings, _legacy_account(options) if legacy.exists() else {})
    if not any(options.get(name) for name in _LEGACY_OPTIONS):
        return
    _save_options({name: value for name, value in options.items() if name not in _LEGACY_OPTIONS})
    print(
        "Moved the owner's password and AnkiWeb login into the users file and cleared them "
        "from the configuration. Manage users from the Anki MCP panel in the sidebar.",
        flush=True,
    )


def _give_to_server_user(top: Path) -> None:
    for root, _, files in os.walk(top):
        for path in [root, *(os.path.join(root, name) for name in files)]:
            if path != str(_OPTIONS) and os.lstat(path).st_uid != _UID:
                os.lchown(path, _UID, _GID)


def _start_panel(settings: Settings) -> None:
    config = uvicorn.Config(
        create_admin_app(settings),
        host="0.0.0.0",
        port=_INGRESS_PORT,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    # uvicorn installs signal handlers only on the main thread, which the MCP server owns.
    threading.Thread(target=uvicorn.Server(config).run, name="users-panel", daemon=True).start()


def main() -> None:
    options = json.loads(_OPTIONS.read_text(encoding="utf-8"))
    os.environ.update(_environment(options))
    os.environ["HOME"] = "/app"
    try:
        settings = Settings()  # pyright: ignore[reportCallIssue] - values come from environment
    except ValueError as exc:
        sys.exit(f"Invalid add-on configuration: {exc}")
    _upgrade(settings, options)
    _write_smtp_password(options)
    _give_to_server_user(_DATA)
    _give_to_server_user(_CONFIG)
    os.setgroups([])
    os.setgid(_GID)
    os.setuid(_UID)
    _start_panel(settings)
    serve_mcp()


if __name__ == "__main__":
    main()
