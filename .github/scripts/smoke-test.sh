#!/usr/bin/env bash
# Upgrades a 0.9-style install in the image built as anki-mcp-addon:ci, started the way Supervisor
# would, then checks the server and the users panel come up as the server user.
set -euxo pipefail
trap '[ $? -eq 0 ] || docker logs addon || true' EXIT

image=anki-mcp-addon:ci
in_image() { docker run --rm -v "$data:/data" --entrypoint python "$image" -c "$1"; }

data=$(mktemp -d)
sudo chown -R root:root "$data"
# A collection where 0.9 kept it, with a deck to find again after the move.
in_image 'from anki.collection import Collection; c = Collection("/data/collection.anki2"); c.decks.id("Before upgrade"); c.close()'
password_hash=$(in_image 'from anki_mcp.oauth import hash_password; print(hash_password("ci-password-123"))')
cat <<JSON | sudo tee "$data/options.json" >/dev/null
{"public_url": "http://localhost:8000", "scopes": "read,write", "allow_schema_changes": true,
 "allow_full_sync": true, "max_open_collections": 5, "smtp_port": 587, "smtp_security": "starttls",
 "log_level": "debug", "https_proxy": "http://proxy.invalid:3128", "no_proxy": "ankiweb.net",
 "password_hash": "$password_hash", "sync_username": "ci@example.com", "sync_password": "ci-sync-secret"}
JSON
config=$(mktemp -d)
printf '# test\nexample.com\n' > "$config/media_url_hosts.txt"
chmod 600 "$config/media_url_hosts.txt"
sudo chown -R root:root "$config"

docker run -d --name addon -p 8000:8000 -v "$data:/data" -v "$config:/config" \
  --health-interval=2s --health-start-period=0s "$image"
for _ in $(seq 30); do curl -fs http://localhost:8000/health/live && break; sleep 2; done
curl -fs http://localhost:8000/health/live
test "$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/mcp)" = 401
curl -fs http://localhost:8000/.well-known/oauth-authorization-server >/dev/null

# The old collection moved into users/owner/, and the owner kept the old password and sync login.
sudo test -f "$data/users/owner/collection.anki2"
sudo test ! -e "$data/collection.anki2"
sudo grep -q "\"password_hash\":\"$password_hash\"" "$data/users.json"
sudo grep -q '"sync_username":"ci@example.com"' "$data/users.json"
# The old credentials were cleared from the add-on configuration.
for secret in ci-sync-secret '"password_hash"' '"sync_username"'; do
  if sudo grep -q "$secret" "$data/options.json"; then exit 1; fi
done
test "$(sudo stat -c %u "$data/users.json")" = 10001
test "$(sudo stat -c %u "$data/users/owner/collection.anki2")" = 10001
test "$(sudo stat -c %u "$config/media_url_hosts.txt")" = 10001

# The server runs inside run.py's process, so /proc/<pid>/environ shows only the starting
# environment; check that the options reached the server through what it reports instead.
curl -fs http://localhost:8000/health/ready | grep -q '"max_open_collections":5'
test "$(docker exec addon awk '/^Uid:/ {print $2}' /proc/1/status)" = 10001

# The users panel answers on the ingress port and can invite someone; with no mail server set it
# shows the link, and the server serves that link's setup page.
docker exec -i addon python - <<'PY'
import json, re, urllib.parse, urllib.request
page = urllib.request.urlopen("http://127.0.0.1:8099/", timeout=5).read().decode()
assert "Anki MCP users" in page and "owner" in page, page
form = urllib.parse.urlencode({"user_id": "alex", "email": "", "sync_host": ""}).encode()
invited = urllib.request.urlopen("http://127.0.0.1:8099/invite", data=form, timeout=5).read().decode()
link = re.search(r"http://localhost:8000/setup\?token=[\w-]+", invited)
assert link, invited
setup = urllib.request.urlopen(link.group(0).replace("localhost", "127.0.0.1"), timeout=5).read().decode()
assert "Step 1 of 3" in setup, setup
assert json.load(open("/data/users.json"))["users"]["alex"]["setup"] == "password"
PY

for _ in $(seq 15); do
  status=$(docker inspect -f '{{.State.Health.Status}}' addon)
  [ "$status" = healthy ] && break
  sleep 2
done
test "$status" = healthy
