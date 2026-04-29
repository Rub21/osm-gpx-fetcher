#!/bin/bash
# descarga gpx publicos de osm

set -u

OUT_DIR="gpx_files"
TARGET=10000
START_ID=12317141
BATCH=500
PARALLEL=2
SLEEP_OK="0.2"
SLEEP_BATCH=2

mkdir -p "$OUT_DIR"

fetch_one() {
    id="$1"
    f="$OUT_DIR/$id.gpx"
    [ -f "$f" ] && return 0

    code=$(curl -s -L -A "osmf-gps-research" \
        --connect-timeout 10 --max-time 30 \
        -o "$f" -w "%{http_code}" \
        "https://www.openstreetmap.org/traces/$id/data")

    case "$code" in
        200)
            size=$(wc -c <"$f" | tr -d ' ')
            echo "ok $id  ($size bytes)"
            sleep "$SLEEP_OK"
            ;;
        404|403)
            # traza privada o no existe, saltar
            rm -f "$f"
            ;;
        429|503)
            # rate limit, esperar y reintentar
            rm -f "$f"
            echo "rate limit en id $id, esperando 60s..."
            sleep 60
            ;;
        *)
            rm -f "$f"
            echo "error $code en id $id"
            ;;
    esac
}

export OUT_DIR SLEEP_OK
export -f fetch_one

id=$START_ID
while :; do
    have=$(ls "$OUT_DIR" 2>/dev/null | wc -l)
    if [ "$have" -ge "$TARGET" ]; then
        echo "listo: $have archivos"
        break
    fi

    end=$((id + BATCH - 1))
    echo "probando ids $id..$end  (tengo $have / $TARGET)"

    seq "$id" "$end" | xargs -P "$PARALLEL" -I{} bash -c 'fetch_one "$@"' _ {}

    id=$((end + 1))
    sleep "$SLEEP_BATCH"
done
