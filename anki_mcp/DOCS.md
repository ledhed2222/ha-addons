# Anki MCP

Runs [anki-sync-mcp](https://github.com/ledhed2222/anki-sync-mcp) as a headless Anki client. It syncs your collection with AnkiWeb, which stays the source of truth, and serves it to MCP clients such as claude.ai custom connectors. Clients sign in over OAuth with a password you choose.

## Setup

1. **Create a password hash** on any machine with Docker:

   ```sh
   docker run --rm -it ghcr.io/ledhed2222/anki-sync-mcp:0.2.0-oauth.1 anki-mcp-hash-password
   ```

   Paste the output into **Password hash**. You type the password itself when a client signs in.
2. **Public URL**: the HTTPS address your reverse proxy serves this add-on at, for example `https://anki.example.com`. Proxy it to port 8000 on this host. The proxy must pass the original `Host` header through and forward `/mcp`, `/oauth/login`, `/authorize`, `/token`, `/register`, `/revoke` and `/.well-known/`.
3. **AnkiWeb username and password**: on the first start, the add-on logs in and downloads your collection. After that it keeps a sync key, so clear the password field.
4. **Scopes**: leave this at `read,write` unless you need more. `admin` and `destructive` expose tools that can rewrite or delete data.
5. Start the add-on, then add `https://<your host>/mcp` as a custom connector in claude.ai.

Test with a throwaway AnkiWeb account before pointing it at your real one.

## Data

The collection, sync key and OAuth state live in this add-on's `/data` folder. Home Assistant backups include it. OAuth tokens are stored only as hashes.

## Troubleshooting

Set **Log level** to `debug` to see diagnostics, such as redirect URIs refused during client registration.
