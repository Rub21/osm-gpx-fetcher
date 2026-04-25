#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

RSS_URL = "https://www.openstreetmap.org/traces/rss"
TRACE_URL = "https://www.openstreetmap.org/traces/{id}/data"
USER_AGENT = "osmf-gps-fetcher/0.1 (contact: Rub21)"

LINK_RE = re.compile(r"/user/([^/]+)/traces/(\d+)")


class RateLimited(Exception):
    def __init__(self, code, retry_after=None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(f"HTTP {code} (retry_after={retry_after})")


def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            ra = e.headers.get("Retry-After") if e.headers else None
            try:
                ra = int(ra) if ra else None
            except (TypeError, ValueError):
                ra = None
            raise RateLimited(e.code, ra) from e
        raise


def parse_rss(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        m = LINK_RE.search(link)
        if not m:
            continue
        user, trace_id = m.group(1), m.group(2)
        items.append({
            "id": trace_id,
            "user": user,
            "title": (item.findtext("title") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
            "link": link,
        })
    return items


def safe_filename(name):
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:120] or "trace.gpx"


def download_trace(trace, out_dir, retries=3, sleep=2):
    url = TRACE_URL.format(id=trace["id"])
    fname = f"{trace['id']}_{safe_filename(trace['title'] or 'trace.gpx')}"
    if not fname.endswith(".gpx"):
        fname += ".gpx"
    path = out_dir / fname
    if path.exists() and path.stat().st_size > 0:
        return path, "skip"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            data, _ = http_get(url)
            path.write_bytes(data)
            return path, "ok"
        except RateLimited:
            raise
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (403, 404):
                break
        except Exception as e:
            last_err = str(e)
        time.sleep(sleep * attempt)
    return path, f"error: {last_err}"


def count_gpx(gpx_dir):
    return sum(1 for p in gpx_dir.glob("*.gpx") if p.stat().st_size > 0)


def run_once(out_dir, gpx_dir, target, limit, delay):
    have = count_gpx(gpx_dir)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] gpx count: {have} / target: {target}")

    if target > 0 and have >= target:
        return have, 0, True

    remaining = (target - have) if target > 0 else None

    try:
        xml_bytes, _ = http_get(RSS_URL)
    except RateLimited:
        raise
    except Exception as e:
        print(f"RSS fetch failed: {e}", file=sys.stderr)
        return have, 0, False

    items = parse_rss(xml_bytes)
    print(f"found {len(items)} items in feed")

    if limit > 0:
        items = items[:limit]
    if remaining is not None:
        items = items[:remaining]

    new_count = 0
    results = []
    for i, t in enumerate(items, 1):
        if remaining is not None and new_count >= remaining:
            break
        path, status = download_trace(t, gpx_dir)
        size = path.stat().st_size if path.exists() else 0
        print(f"[{i}/{len(items)}] {t['id']} {t['user']} -> {path.name} ({size} bytes) [{status}]")
        results.append({**t, "file": str(path.relative_to(out_dir)), "size": size, "status": status})
        if status == "ok":
            new_count += 1
        if delay > 0 and i < len(items):
            time.sleep(delay)

    final = count_gpx(gpx_dir)
    index_path = out_dir / "index.json"
    existing = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text())
        except Exception:
            existing = []
    seen_ids = {r.get("id") for r in existing}
    merged = existing + [r for r in results if r["id"] not in seen_ids]
    index_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"new this round: {new_count} | total: {final} / {target}")
    return final, new_count, target > 0 and final >= target


def main():
    ap = argparse.ArgumentParser(description="Download recent public GPS traces from openstreetmap.org RSS feed")
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "/data"), help="output directory")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("LIMIT", "0")), help="max traces to download per run (0 = all in feed)")
    ap.add_argument("--target", type=int, default=int(os.environ.get("TARGET_COUNT", "10000")), help="stop when this many .gpx files exist in output (0 = no target)")
    ap.add_argument("--delay", type=float, default=float(os.environ.get("DELAY", "1.0")), help="seconds between downloads")
    ap.add_argument("--watch", action="store_true", default=os.environ.get("WATCH", "0") == "1", help="loop forever, refetch RSS every --interval seconds")
    ap.add_argument("--interval", type=int, default=int(os.environ.get("WATCH_INTERVAL", "900")), help="seconds between RSS fetches in watch mode (default 900 = 15 min)")
    ap.add_argument("--cooldown", type=int, default=int(os.environ.get("RATE_LIMIT_COOLDOWN", "3600")), help="seconds to wait after HTTP 429/503 (default 3600 = 1h)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    gpx_dir = out_dir / "gpx"
    gpx_dir.mkdir(exist_ok=True)

    print(f"output dir: {out_dir} | target: {args.target} | delay: {args.delay}s | watch: {args.watch} (every {args.interval}s)")

    if not args.watch:
        try:
            run_once(out_dir, gpx_dir, args.target, args.limit, args.delay)
        except RateLimited as rl:
            wait = rl.retry_after or args.cooldown
            print(f"RATE LIMITED (HTTP {rl.code}). single-run mode, exiting. retry after {wait}s.", file=sys.stderr)
            sys.exit(2)
        return

    while True:
        try:
            _, _, done = run_once(out_dir, gpx_dir, args.target, args.limit, args.delay)
        except RateLimited as rl:
            wait = rl.retry_after or args.cooldown
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] RATE LIMITED (HTTP {rl.code}). pausing {wait}s (~{wait // 60} min) before retry.", file=sys.stderr)
            time.sleep(wait)
            continue
        if done:
            print("target reached, exiting watch loop")
            return
        print(f"sleeping {args.interval}s before next RSS fetch...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
