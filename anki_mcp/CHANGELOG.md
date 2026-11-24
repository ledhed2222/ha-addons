# Changelog

## 0.10.0

- **Breaking:** bump anki-sync-mcp to 0.3.0. Every install is multi-user, and clients sign in with a user id and password. Your reverse proxy must also forward `/setup`.
- New **Anki MCP** sidebar panel for Home Assistant admins to invite users, send new setup links, reset passwords and remove users.
- Invited users set their own password, sign in to AnkiWeb and watch their collection copy. New mail server options send the setup links by email.
- New **Open collections** option caps memory use.
- The first start moves a 0.9 install into the new layout as `owner`, keeping the password and AnkiWeb sync, then clears the old password and AnkiWeb options.

## 0.9.0

- Bump anki-sync-mcp to 0.2.0-oauth.8; add media URL hosts file and HTTPS proxy settings (#19)
