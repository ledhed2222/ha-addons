#!/usr/bin/env bash
# Starts the image built as anki-mcp-addon:ci the way Supervisor would and checks it comes up as the server user.
set -euxo pipefail
trap '[ $? -eq 0 ] || docker logs addon || true' EXIT

data=$(mktemp -d)
cat > "$data/options.json" <<JSON
{"public_url": "http://localhost:8000", "password": "ci-password-123", "password_hash": "",
 "scopes": "read,write", "sync_username": "", "sync_password": "", "log_level": "debug",
 "https_proxy": "http://proxy.invalid:3128", "no_proxy": "ankiweb.net"}
JSON
config=$(mktemp -d)
printf '# test\nexample.com\n' > "$config/media_url_hosts.txt"
chmod 600 "$config/media_url_hosts.txt"
sudo chown -R root:root "$data" "$config"
docker run -d --name addon -p 8000:8000 -v "$data:/data" -v "$config:/config" \
  --health-interval=2s --health-start-period=0s anki-mcp-addon:ci
for _ in $(seq 30); do curl -fs http://localhost:8000/health/live && break; sleep 2; done
curl -fs http://localhost:8000/health/live
test "$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/mcp)" = 401
curl -fs http://localhost:8000/.well-known/oauth-authorization-server >/dev/null
test "$(sudo stat -c %u "$data/state")" = 10001
test "$(sudo stat -c %u "$config/media_url_hosts.txt")" = 10001
# After the privilege drop the server is non-dumpable, so only the host's root can read its environment.
environ=$(sudo cat "/proc/$(docker inspect -f '{{.State.Pid}}' addon)/environ" | tr '\0' '\n')
grep -qx ANKI_MEDIA_URL_HOSTS_FILE=/config/media_url_hosts.txt <<<"$environ"
grep -qx HTTPS_PROXY=http://proxy.invalid:3128 <<<"$environ"
grep -qx NO_PROXY=ankiweb.net <<<"$environ"
# `! cmd` doesn't trip set -e.
if sudo grep -q ci-password-123 "$data/options.json"; then exit 1; fi
sudo grep -q '"password_hash": "scrypt\$' "$data/options.json"
test "$(docker exec addon awk '/^Uid:/ {print $2}' /proc/1/status)" = 10001
for _ in $(seq 15); do
  status=$(docker inspect -f '{{.State.Health.Status}}' addon)
  [ "$status" = healthy ] && break
  sleep 2
done
test "$status" = healthy
