#!/usr/bin/env bash
# Smoke test for a deployed SynAnno demo (SYNANNO_PUBLIC_DEMO=1).
#
# Usage: scripts/smoke_test.sh http://<host>
#
# Calls /reset and /demo, which wipe the shared demo state (by design: the demo
# is single-user). Makes no other state changes.

set -u

BASE="${1:?usage: $0 http://<host>}"
BASE="${BASE%/}"
H01_SOURCE="gs://h01-release/data/20210601/4nm_raw"
H01_TARGET="gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol"
H01_NEUROPIL="gs://h01-release/data/20210601/proofread_104"

failures=0
pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; failures=$((failures + 1)); }

status() { curl -s -o /dev/null -m "${2:-30}" -w "%{http_code}" "${@:3}" "$1"; }

# 1. Pages load
for path in / /reset /demo; do
    code=$(status "$BASE$path")
    [[ $code == 200 ]] && pass "GET $path -> $code" || fail "GET $path -> $code"
done

# 2. The demo loads, and its Neuroglancer view is served from <host>:9015 with an
#    unguessable token (the same /neuro call the annotation page makes)
code=$(status "$BASE/demo_annotation" 600)
[[ $code == 200 ]] && pass "GET /demo_annotation -> $code" || fail "GET /demo_annotation -> $code"
ng_json=$(curl -s -m 120 -X POST "$BASE/neuro" -d mode=draw -d cz0=0 -d cy0=0 -d cx0=0)
ng_url=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["ng_link"])' "$ng_json" 2>/dev/null)
host="${BASE#*://}"
if [[ $ng_url =~ ^http://${host}:9015/v/([A-Za-z0-9_-]{40,})/$ ]]; then
    pass "Neuroglancer URL $ng_url"
    code=$(status "$ng_url")
    [[ $code == 200 ]] && pass "GET Neuroglancer view -> $code" \
        || fail "GET Neuroglancer view -> $code"
else
    fail "Neuroglancer URL not on $host:9015 with a long token: '${ng_url:-$ng_json}'"
fi

# 3. /load_materialization rejects local files and external URLs
for url in /etc/passwd file:///etc/passwd http://example.com/table.csv; do
    code=$(status "$BASE/load_materialization" 30 -X POST \
        -H "Content-Type: application/json" \
        -d "{\"materialization_url\": \"$url\"}")
    [[ $code =~ ^4 ]] && pass "load_materialization $url -> $code" \
        || fail "load_materialization $url -> $code"
done

# 4. No wildcard CORS header
if curl -s -o /dev/null -D - -m 30 -H "Origin: http://evil.example" "$BASE/" \
    | grep -qi "^access-control-allow-origin"; then
    fail "Access-Control-Allow-Origin header sent"
else
    pass "No Access-Control-Allow-Origin header"
fi

# 5. Credential upload is disabled (rejected before any state change)
creds=$(mktemp)
echo '{"token": "smoke-test-not-a-secret"}' > "$creds"
code=$(status "$BASE/upload" 30 -X POST \
    -F "source_url=$H01_SOURCE" -F "target_url=$H01_TARGET" \
    -F "neuropil_url=$H01_NEUROPIL" -F "view_style=neuron" \
    -F "tiles_per_page=12" -F "secrets_file=@$creds;type=application/json")
rm -f "$creds"
[[ $code == 403 ]] && pass "Credential upload -> $code" || fail "Credential upload -> $code"

echo
if ((failures)); then
    echo "$failures check(s) failed"
    exit 1
fi
echo "All checks passed"
