#!/bin/bash
# sube gpx a una instancia de osm (por defecto osm-dev local)

set -u

OSM_URL="${OSM_URL:-https://openstreetmap.204-168-242-139.nip.io}"
TOKEN="${TOKEN:-}"
GPX_DIR="${GPX_DIR:-gpx_files}"
VISIBILITY="${VISIBILITY:-public}"   # public, private, trackable, identifiable

if [ -z "$TOKEN" ]; then
    echo "falta TOKEN. ej:  TOKEN=xxx ./upload_gpx.sh"
    exit 1
fi

count=0
fail=0

for f in "$GPX_DIR"/*.gpx; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .gpx)

    code=$(curl -s -o /tmp/upload_resp.txt -w "%{http_code}" \
        -X POST "$OSM_URL/api/0.6/gpx" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@$f" \
        -F "description=test trace $name" \
        -F "tags=test,bulk" \
        -F "visibility=$VISIBILITY")

    if [ "$code" = "200" ]; then
        count=$((count+1))
        trace_id=$(cat /tmp/upload_resp.txt)
        echo "[$count] OK $name -> id $trace_id"
    else
        fail=$((fail+1))
        echo "FAIL $name (http $code)"
    fi
done

echo ""
echo "subidos: $count   fallidos: $fail"
