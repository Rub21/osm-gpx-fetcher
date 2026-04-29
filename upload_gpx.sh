#!/bin/bash
# upload gpx files to osm. tracks done files in upload_status.csv
# to retry failed ones, just delete the FAIL rows from upload_status.csv

[ -f "$(dirname "$0")/.env" ] && source "$(dirname "$0")/.env"

OSM_URL="${OSM_URL:-https://openstreetmap.204-168-242-139.nip.io}"
GPX_DIR="${GPX_DIR:-gpx_files}"
VISIBILITY="${VISIBILITY:-public}"
STATUS_FILE="upload_status.csv"

if [ -z "${TOKEN:-}" ]; then
    echo "missing TOKEN (set it in .env)"
    exit 1
fi

touch "$STATUS_FILE"
ok=0; fail=0; skipped=0

for f in "$GPX_DIR"/*.gpx; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .gpx)

    if grep -q ",$name," "$STATUS_FILE"; then
        skipped=$((skipped+1))
        continue
    fi

    code=$(curl -s -o /tmp/upload_resp.txt -w "%{http_code}" \
        -X POST "$OSM_URL/api/0.6/gpx" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@$f" \
        -F "description=$name" \
        -F "tags=test,bulk" \
        -F "visibility=$VISIBILITY")

    if [ "$code" = "200" ]; then
        ok=$((ok+1))
        trace_id=$(tr -d '\r\n' < /tmp/upload_resp.txt)
        echo "OK $name -> id $trace_id"
        echo "OK,$name,$code,$trace_id" >> "$STATUS_FILE"
    else
        fail=$((fail+1))
        echo "FAIL $name ($code)"
        echo "FAIL,$name,$code," >> "$STATUS_FILE"
    fi
done

echo ""
echo "uploaded: $ok   failed: $fail   skipped: $skipped"
