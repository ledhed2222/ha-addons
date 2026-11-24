"""Users panel shown in Home Assistant's sidebar through ingress.

Home Assistant only shows ingress panels to its administrators and authenticates every request
before proxying it from 172.30.32.2, so the panel trusts that address and nothing else (plus
loopback, for checks run inside the container). It edits the same users file as anki-mcp-user,
under the same lock, and the server picks up each change without a restart.
"""

from __future__ import annotations

import base64
import hashlib
import html
import logging
from typing import Any

from anki_mcp.config import Settings, validate_sync_endpoint
from anki_mcp.registration import begin_setup, send_setup_email, setup_link, valid_email
from anki_mcp.users import SETUP_BLOCKS_SIGN_IN, load_users_file, update_users_file, valid_user_id
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

_LOGGER = logging.getLogger("anki_mcp_addon.admin")
INGRESS_CLIENTS = frozenset({"172.30.32.2", "127.0.0.1", "::1"})
_STATUS = {
    "password": "Invited · hasn't chosen a password",
    "ankiweb": "Invited · hasn't signed in to AnkiWeb",
    "syncing": "Copying their collection",
    "failed": "Copy failed",
    "done": "Ready",
    "reset": "Ready · password reset sent",
}
_CSS = """
:root{color-scheme:light dark;--bg:#fafafa;--card:#fff;--text:#1d2125;--muted:#5e6670;
--border:#d4d8dd;--accent:#03a9f4;--accent-text:#fff;--error-bg:#fdecec;--error:#a1260d;
--ok-bg:#e8f5ec;--ok:#1d6b35}
@media (prefers-color-scheme:dark){:root{--bg:#111;--card:#1c1c1c;--text:#e1e1e1;
--muted:#9b9b9b;--border:#3a3a3a;--error-bg:#3a1f1c;--error:#ffb4a6;--ok-bg:#1b3324;--ok:#9be0b0}}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px}
h2{font-size:1.1rem;margin:0 0 12px}
p{margin:0 0 12px}
section{background:var(--card);border:1px solid var(--border);border-radius:12px;
padding:20px;margin:16px 0}
.muted{color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
label{display:block;font-weight:600;font-size:.9rem}
input{display:block;width:100%;margin-top:4px;padding:8px 10px;font:inherit;color:inherit;
background:var(--card);border:1px solid var(--border);border-radius:8px}
button{padding:8px 14px;font:inherit;font-weight:600;color:var(--accent-text);
background:var(--accent);border:0;border-radius:8px;cursor:pointer}
button.quiet{color:var(--text);background:transparent;border:1px solid var(--border)}
button.danger{color:var(--error);background:transparent;border:1px solid var(--error)}
input:focus,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.alert{padding:10px 12px;border-radius:8px;background:var(--error-bg);color:var(--error)}
.ok{padding:10px 12px;border-radius:8px;background:var(--ok-bg);color:var(--ok)}
.link{display:block;padding:10px;border:1px solid var(--border);border-radius:8px;
font-family:ui-monospace,Menlo,monospace;font-size:.85rem;word-break:break-all}
ul{list-style:none;margin:0;padding:0}
li{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:space-between;
padding:12px 0;border-top:1px solid var(--border)}
li:first-child{border-top:0}
.who strong{display:block}
.actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.actions form{display:flex;gap:6px;align-items:center}
.actions input{width:9em;margin:0;padding:6px 8px}
"""
_CSS_HASH = base64.b64encode(hashlib.sha256(_CSS.encode("utf-8")).digest()).decode()


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


class _Panel:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _page(self, notice: str = "", status: int = 200) -> Response:
        users: dict[str, Any] = load_users_file(self._settings.users_file)["users"]
        rows = "".join(self._row(user_id, entry) for user_id, entry in sorted(users.items()))
        email_note = (
            "Setup links are emailed through your mail server."
            if self._settings.smtp_host
            else "No mail server is set in the add-on configuration, so setup links are shown "
            "here for you to send yourself."
        )
        body = (
            "<h1>Anki MCP users</h1><p class='muted'>Each user signs in to MCP clients with their "
            f"own password and gets their own collection, synced with their own AnkiWeb account."
            f"</p>{notice}"
            "<section><h2>Invite someone</h2>"
            f"<p class='muted'>{email_note} They choose a password, sign in to AnkiWeb, and wait "
            "for their collection to copy; then they can connect their apps.</p>"
            "<form method='post' action='invite'><div class='grid'>"
            "<label>User id <input name='user_id' required pattern='[a-z0-9][a-z0-9_\\-]{0,63}' "
            "autocapitalize='none' spellcheck='false' placeholder='alex'></label>"
            "<label>Email <input name='email' type='email' "
            f"{'required ' if self._settings.smtp_host else ''}placeholder='alex@example.com'>"
            "</label><label>Sync server <input name='sync_host' type='url' "
            "placeholder='Empty for AnkiWeb'></label></div>"
            "<p class='muted'>User ids use lowercase letters, digits, _ and -.</p>"
            "<button type='submit'>Invite</button></form></section>"
            f"<section><h2>Users</h2><ul>{rows or '<li>No users yet.</li>'}</ul></section>"
        )
        return HTMLResponse(
            f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Anki MCP users</title><style>{_CSS}</style></head>"
            f"<body><main>{body}</main></body></html>",
            status_code=status,
            headers={
                "Cache-Control": "no-store",
                # Ingress shows the panel in a Home Assistant frame on the same origin.
                "Content-Security-Policy": (
                    f"default-src 'none'; style-src 'sha256-{_CSS_HASH}'; form-action 'self'; "
                    "frame-ancestors 'self'"
                ),
                "Referrer-Policy": "no-referrer",
            },
        )

    def _row(self, user_id: str, entry: dict[str, Any]) -> str:
        stage = entry.get("setup")
        if stage:
            status = _STATUS.get(stage, stage)
        elif entry.get("password_hash"):
            status = "Ready"
        else:
            status = "No password set"
        if stage == "failed" and entry.get("setup_error"):
            status += f": {entry['setup_error']}"
        who = _escape(user_id)
        email = f" · {_escape(entry['email'])}" if entry.get("email") else ""
        hidden = f"<input type='hidden' name='user_id' value='{who}'>"
        actions = []
        if stage in SETUP_BLOCKS_SIGN_IN:
            actions.append(
                f"<form method='post' action='resend'>{hidden}"
                "<button class='quiet' type='submit'>New setup link</button></form>"
            )
        elif entry.get("password_hash"):
            actions.append(
                f"<form method='post' action='reset'>{hidden}"
                "<button class='quiet' type='submit'>Reset password</button></form>"
            )
        actions.append(
            f"<form method='post' action='remove'>{hidden}"
            f"<input name='confirm' required placeholder='Type {who}' aria-label='Type "
            f"{who} to confirm'><button class='danger' type='submit'>Remove</button></form>"
        )
        return (
            f"<li><span class='who'><strong>{who}</strong>"
            f"<span class='muted'>{_escape(status)}{email}</span></span>"
            f"<span class='actions'>{''.join(actions)}</span></li>"
        )

    def _deliver(self, user_id: str, email: str | None, token: str, *, reset: bool) -> str:
        link = setup_link(self._settings, token)
        what = "password reset link" if reset else "setup link"
        if self._settings.smtp_host and email:
            try:
                send_setup_email(self._settings, email, user_id, link, reset=reset)
            except Exception as exc:
                _LOGGER.warning("sending a %s failed: %s", what, type(exc).__name__)
                return self._link_notice(
                    f"The email to {email} failed ({type(exc).__name__}). Send {user_id} this "
                    f"{what} yourself:",
                    link,
                    alert=True,
                )
            return f"<p class='ok'>Sent a {what} to {_escape(email)}.</p>"
        return self._link_notice(f"Send {user_id} this {what}. It works once:", link)

    @staticmethod
    def _link_notice(message: str, link: str, *, alert: bool = False) -> str:
        return (
            f"<section><p class='{'alert' if alert else 'ok'}'>{_escape(message)}</p>"
            f"<code class='link'>{_escape(link)}</code></section>"
        )

    @staticmethod
    def _error(message: str) -> str:
        return f"<p class='alert' role='alert'>{_escape(message)}</p>"

    async def index(self, _: Request) -> Response:
        return self._page()

    async def invite(self, request: Request) -> Response:
        form = await request.form()
        user_id = str(form.get("user_id", "")).strip()
        email = str(form.get("email", "")).strip() or None
        if not valid_user_id(user_id):
            return self._page(self._error("User ids use a-z, 0-9, _ and -, at most 64."), 400)
        if email is None and self._settings.smtp_host:
            return self._page(self._error("Enter an email address to send the link to."), 400)
        if email is not None and not valid_email(email):
            return self._page(self._error("That doesn't look like an email address."), 400)
        try:
            endpoint = validate_sync_endpoint(str(form.get("sync_host", "")).strip())
        except ValueError as exc:
            return self._page(self._error(str(exc)), 400)

        def create(raw: dict[str, Any]) -> str | None:
            if user_id in raw["users"]:
                return None
            entry: dict[str, Any] = {"sync_username": "", "sync_endpoint": endpoint}
            if email:
                entry["email"] = email
            raw["users"][user_id] = entry
            return begin_setup(entry, "password", self._settings.setup_link_hours)

        token = update_users_file(self._settings.users_file, create)
        if token is None:
            return self._page(self._error(f"There is already a user called {user_id}."), 409)
        return self._page(self._deliver(user_id, email, token, reset=False))

    async def resend(self, request: Request) -> Response:
        user_id = str((await request.form()).get("user_id", ""))

        def refresh(raw: dict[str, Any]) -> tuple[str | None, str] | None:
            entry = raw["users"].get(user_id)
            if entry is None or entry.get("setup") not in SETUP_BLOCKS_SIGN_IN:
                return None
            return entry.get("email"), begin_setup(
                entry, entry["setup"], self._settings.setup_link_hours
            )

        result = update_users_file(self._settings.users_file, refresh)
        if result is None:
            return self._page(self._error(f"{user_id} has no unfinished setup."), 409)
        return self._page(self._deliver(user_id, result[0], result[1], reset=False))

    async def reset(self, request: Request) -> Response:
        user_id = str((await request.form()).get("user_id", ""))

        def start(raw: dict[str, Any]) -> tuple[str | None, str] | None:
            entry = raw["users"].get(user_id)
            if entry is None or entry.get("setup") in SETUP_BLOCKS_SIGN_IN:
                return None
            return entry.get("email"), begin_setup(entry, "reset", self._settings.setup_link_hours)

        result = update_users_file(self._settings.users_file, start)
        if result is None:
            return self._page(self._error(f"{user_id} can't reset a password yet."), 409)
        return self._page(self._deliver(user_id, result[0], result[1], reset=True))

    async def remove(self, request: Request) -> Response:
        form = await request.form()
        user_id = str(form.get("user_id", ""))
        if str(form.get("confirm", "")).strip() != user_id:
            return self._page(self._error(f"Type {user_id} to confirm removing them."), 400)
        removed = update_users_file(
            self._settings.users_file, lambda raw: raw["users"].pop(user_id, None) is not None
        )
        if not removed:
            return self._page(self._error(f"There is no user called {user_id}."), 404)
        return self._page(
            f"<p class='ok'>Removed {_escape(user_id)} and signed out their apps. Their "
            "collection is kept in the add-on's data folder.</p>"
        )


def create_admin_app(settings: Settings) -> ASGIApp:
    panel = _Panel(settings)
    app = Starlette(
        routes=[
            Route("/", panel.index, methods=["GET"]),
            Route("/invite", panel.invite, methods=["POST"]),
            Route("/resend", panel.resend, methods=["POST"]),
            Route("/reset", panel.reset, methods=["POST"]),
            Route("/remove", panel.remove, methods=["POST"]),
        ]
    )

    async def ingress_only(scope: Scope, receive: Receive, send: Send) -> None:
        client = scope.get("client") or ("", 0)
        if scope["type"] == "http" and client[0] not in INGRESS_CLIENTS:
            refusal = PlainTextResponse("Open this panel from Home Assistant.", status_code=403)
            await refusal(scope, receive, send)
            return
        await app(scope, receive, send)

    return ingress_only
