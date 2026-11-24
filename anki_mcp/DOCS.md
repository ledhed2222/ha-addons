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

## Media downloads

Clients can ask the server to download a media file from a URL instead of sending its bytes. It only downloads from an allow-list of hosts, which by default is `cdn.jsdelivr.net`, `fonts.gstatic.com`, `raw.githubusercontent.com`, `unpkg.com` and `upload.wikimedia.org`.

To replace that list, create `media_url_hosts.txt` in this add-on's config folder (`/addon_configs/<id>_anki_mcp/` on the host, where `<id>` is a short code for this add-on repository; the Samba and File editor add-ons can reach it) and restart the add-on. Put one bare hostname per line; blank lines and `#` comments are ignored. An entry such as `https://example.com` stops the add-on from starting. An empty file refuses every URL. Delete the file to go back to the default list.

```text
# Fontsource and other npm packages
cdn.jsdelivr.net
# Wikipedia and Wikimedia Commons images
upload.wikimedia.org
```

Each host sees this machine's public IP address. To hide it, set **HTTPS proxy** to a proxy URL such as `http://user:password@proxy.lan:3128`. The add-on never logs it. Anki's sync client uses the same proxy, so AnkiWeb sync goes through it too unless you add `ankiweb.net` to **No proxy**, a comma-separated list of hosts that connect directly. The proxy sees the host of every download and sync.

## Data

The collection, sync key and OAuth state live in this add-on's `/data` folder. Home Assistant backups include it. OAuth tokens are stored only as hashes.

## Troubleshooting

Set **Log level** to `debug` to see diagnostics, such as redirect URIs refused during client registration.
