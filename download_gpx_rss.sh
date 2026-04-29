#!/bin/bash
# download public gpx traces using the osm rss feed
# the feed only returns the ~20 most recent, so loop every few minutes

set -u

OUT_DIR="${OUT_DIR:-gpx_files}"
TARGET="${TARGET:-10000}"
RSS_URL="https://www.openstreetmap.org/traces/rss"
SLEEP_OK="${SLEEP_OK:-1}"
INTERVAL="${INTERVAL:-900}"   # 15 min between rss fetches
UA="osmf-gps-research"

mkdir -p "$OUT_DIR"

fetch_one() {
    local id="$1"
    local f="$OUT_DIR/$id.gpx"
    [ -f "$f" ] && return 0

    local code
    code=$(curl -s -L -A "$UA" \
        --connect-timeout 10 --max-time 30 \
        -o "$f" -w "%{http_code}" \
        "https://www.openstreetmap.org/traces/$id/data")

    case "$code" in
        200)
            local size
            size=$(wc -c <"$f" | tr -d ' ')
            echo "ok $id ($size bytes)"
            sleep "$SLEEP_OK"
            ;;
        404|403)
            rm -f "$f"
            ;;
        429|503)
            rm -f "$f"
            echo "rate limit on id $id, sleeping 60s..."
            sleep 60
            ;;
        *)
            rm -f "$f"
            echo "error $code on id $id"
            ;;
    esac
}

while :; do
    have=$(ls "$OUT_DIR" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$have" -ge "$TARGET" ]; then
        echo "done: $have files"
        break
    fi

    echo "fetching rss feed... (have $have / $TARGET)"
    rss=$(curl -s -A "$UA" --connect-timeout 10 --max-time 30 "$RSS_URL")

    if [ -z "$rss" ]; then
        echo "empty rss or fetch failed, retrying in ${INTERVAL}s"
        sleep "$INTERVAL"
        continue
    fi

    # extract ids from <link>...traces/<id></link>
    ids=$(echo "$rss" | grep -oE "/user/[^/]+/traces/[0-9]+" | grep -oE "[0-9]+$" | sort -u)
    n=$(echo "$ids" | grep -c .)
    echo "found $n traces in feed"

    for id in $ids; do
        fetch_one "$id"
        have=$(ls "$OUT_DIR" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$have" -ge "$TARGET" ]; then
            echo "done: $have files"
            exit 0
        fi
    done

    echo "sleeping ${INTERVAL}s before next rss fetch..."
    sleep "$INTERVAL"
done
