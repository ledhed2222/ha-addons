# Anki MCP

Runs [anki-sync-mcp](https://github.com/ledhed2222/anki-sync-mcp) as a headless Anki server for MCP clients such as claude.ai custom connectors. Each person you invite gets their own collection, synced with their own AnkiWeb account, which stays the source of truth. Clients sign in over OAuth with that person's user id and password.

## Setup

1. **Public URL**: the HTTPS address your reverse proxy serves this add-on at, for example `https://anki.example.com`. Proxy it to port 8000 on this host. The proxy must pass the original `Host` header through and forward `/mcp`, `/oauth/login`, `/authorize`, `/token`, `/register`, `/revoke`, `/setup` and `/.well-known/`.
2. **Mail server** (optional): to email setup links, fill in **Mail server**, **Sender address** and, if your server needs them, the port, security, username and password. Without one, the users panel shows each link for you to send yourself.
3. **Scopes**: the default, `read,write,admin`, is what the [anki-notes](https://github.com/ledhed2222/claude-plugins/tree/main/plugins/anki-notes) Claude plugin needs: `admin` lets it create and restyle note types. Drop `admin` to keep clients to notes, cards and decks. `destructive` exposes tools that delete data.
4. **Allow note type changes** (on by default) lets clients with `admin` create note types and change their CSS, template text and names. **Allow full syncs** (on by default) also lets them add, remove or reorder fields and templates; each such change forces a full sync, so sync your other devices first.
5. Start the add-on and open **Anki MCP** in the Home Assistant sidebar. Invite yourself first, then anyone else.

Test with a throwaway AnkiWeb account before pointing it at your real one.

## Users

The **Anki MCP** panel in the sidebar is visible only to Home Assistant administrators. From it you can:

- **Invite** someone with a user id, an email address and, if they don't use AnkiWeb, their sync server's URL. They get a link that walks them through three steps: choosing a password, signing in to AnkiWeb (the password is used once and not stored), and waiting for their collection and media to copy, with a progress bar. They can connect their apps once the copy has finished, by adding `https://<your host>/mcp` as a custom connector and signing in with their user id and password.
- **New setup link** for someone who hasn't finished, for example because their link expired after 72 hours.
- **Reset password**, which sends a link to choose a new one. The old password keeps working until the link is used.
- **Remove** a user, which signs out their apps at once. Their collection stays in the add-on's data folder.

Each open collection uses a few MB of memory and closes after 15 minutes without use. **Open collections** caps how many stay open at once; keep it low on a Raspberry Pi.

## Upgrading from 0.9

The first start of 0.10 moves your collection into the multi-user layout as the user `owner`, keeping your password and AnkiWeb sync. Clients that were already signed in keep working. The **Password**, **Password hash** and AnkiWeb options are then cleared; manage passwords from the users panel from now on. Make sure your reverse proxy also forwards `/setup`.

## Media downloads

Clients can ask the server to download a media file from a URL instead of sending its bytes. It only downloads from an allow-list of hosts, which by default is `cdn.jsdelivr.net`, `fonts.gstatic.com`, `raw.githubusercontent.com`, `unpkg.com`, `upload.wikimedia.org` and `commons.wikimedia.org`.

To replace that list, create `media_url_hosts.txt` in this add-on's config folder (`/addon_configs/<id>_anki_mcp/` on the host, where `<id>` is a short code for this add-on repository; the Samba and File editor add-ons can reach it) and restart the add-on. Put one bare hostname per line; blank lines and `#` comments are ignored. An entry such as `https://example.com` stops the add-on from starting. An empty file refuses every URL. Delete the file to go back to the default list.

```text
# Fontsource and other npm packages
cdn.jsdelivr.net
# Wikipedia and Wikimedia Commons images
upload.wikimedia.org
```

Each host sees this machine's public IP address. To hide it, set **HTTPS proxy** to a proxy URL such as `http://user:password@proxy.lan:3128`. The add-on never logs it. Anki's sync client uses the same proxy, so AnkiWeb sync goes through it too unless you add `ankiweb.net` to **No proxy**, a comma-separated list of hosts that connect directly. The proxy sees the host of every download and sync.

## Data

Every user's collection, sync key and backups, the users file and the OAuth state live in this add-on's `/data` folder. Home Assistant backups include it. Passwords and OAuth tokens are stored only as hashes. The mail server password is stored in plain text in the add-on configuration and in `/data/smtp_password`, as Home Assistant stores other add-on passwords.

## Troubleshooting

Set **Log level** to `debug` to see diagnostics, such as redirect URIs refused during client registration.
