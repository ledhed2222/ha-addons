# Anki MCP

Runs [anki-sync-mcp](https://github.com/ledhed2222/anki-sync-mcp) as a headless Anki client. It syncs your collection with AnkiWeb, which stays the source of truth, and serves it to MCP clients such as claude.ai custom connectors. Clients sign in over OAuth with a password you choose.

## Setup

1. **Password**: choose the password clients sign in with, at least 12 characters. On start the add-on saves it as a hash in **Password hash** and clears **Password**, so no plain-text copy stays in the configuration or in backups. Until then the password is stored in plain text, so restart the add-on right after saving. To change it, enter a new password, save, and restart.
2. **Public URL**: the HTTPS address your reverse proxy serves this add-on at, for example `https://anki.example.com`. Proxy it to port 8000 on this host. The proxy must pass the original `Host` header through and forward `/mcp`, `/oauth/login`, `/authorize`, `/token`, `/register`, `/revoke` and `/.well-known/`.
3. **AnkiWeb username and password**: on the first start, the add-on logs in and downloads your collection. After that it keeps a sync key, so clear the password field.
4. **Scopes**: the default, `read,write,admin`, is what the [anki-notes](https://github.com/ledhed2222/claude-plugins/tree/main/plugins/anki-notes) Claude plugin needs: `admin` lets it create and restyle note types. Drop `admin` to keep clients to notes, cards and decks. `destructive` exposes tools that delete data.
5. **Allow note type changes** (on by default) lets clients with `admin` create note types and change their CSS, template text and names. **Allow full syncs** (on by default) also lets them add, remove or reorder fields and templates; each such change forces a full sync, so sync your other devices first.
6. Start the add-on, then add `https://<your host>/mcp` as a custom connector in claude.ai.

Test with a throwaway AnkiWeb account before pointing it at your real one.

## Data

The collection, sync key and OAuth state live in this add-on's `/data` folder. Home Assistant backups include it. OAuth tokens are stored only as hashes.

## Troubleshooting

Set **Log level** to `debug` to see diagnostics, such as redirect URIs refused during client registration.
