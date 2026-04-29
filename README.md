# gps-fetcher

Small tools to download public GPS traces from openstreetmap.org and upload
them to a target OSM instance (e.g. the test server) for testing the GPS
traces pipeline.

## Pieces

| File                    | What it does                                                              |
|-------------------------|---------------------------------------------------------------------------|
| `fetch.py`              | Python downloader (Docker), uses RSS feed, saves as `<id>_<title>.gpx`    |
| `download_gpx.sh`       | Bash, sequential ID guessing, saves as `<id>.gpx` (slow, lots of 404s)    |
| `download_gpx_rss.sh`   | Bash, uses RSS feed, saves as `<id>.gpx`                                  |
| `osm_generate_token.py` | OAuth2 helper to get an access token                                      |
| `upload_gpx.sh`         | Uploads `.gpx` files to an OSM instance, tracks status in a CSV           |

## Setup

```bash
cp .env.sample .env
# fill in OSM_URL, CLIENT_ID, CLIENT_SECRET, TOKEN as you go
```

`.env` is loaded automatically by the bash and python scripts.

---

## Download traces

### Option A — `fetch.py` (Docker, recommended)

```bash
docker compose build
docker compose up -d            # watch mode, runs in background
docker logs -f osm-gps-fetcher  # follow logs
docker compose down             # stop
```

Output: `data/gpx/<id>_<title>.gpx` and `data/index.json`.

Config (env vars in `docker-compose.yml` or `.env`):

| Variable              | Default | Description                                  |
|-----------------------|---------|----------------------------------------------|
| `TARGET_COUNT`        | 10000   | Stop when this many `.gpx` files exist       |
| `DELAY`               | 2.0     | Seconds between downloads                    |
| `LIMIT`               | 0       | Max traces per RSS fetch (0 = all in feed)   |
| `WATCH`               | 1       | Loop forever (1) or run once (0)             |
| `WATCH_INTERVAL`      | 900     | Seconds between RSS fetches (15 min)         |
| `RATE_LIMIT_COOLDOWN` | 3600    | Pause on HTTP 429/503 (1 hour)               |

One-off run:

```bash
docker compose run --rm -e WATCH=0 fetcher --limit 5
```

### Option B — `download_gpx_rss.sh` (no Docker)

```bash
./download_gpx_rss.sh
```

Reads the same RSS feed and saves to `gpx_files/<id>.gpx`. Useful if you
don't want Docker. Loops forever picking up new traces.

### Notes

- The RSS feed only returns the ~20 most recent traces. To collect many,
  let it run for hours/days.
- For bulk historical data, use the planet GPX dump instead:
  https://planet.openstreetmap.org/gps/

---

## Upload traces to OSM

`upload_gpx.sh` uses the OSM API `POST /api/0.6/gpx`. It needs an OAuth2
access token.

### 1. Register an OAuth2 application

On the target OSM instance go to **My Settings → OAuth 2 Applications →
Register new application**:

- **Name:** anything (e.g. `gps-fetcher-test`)
- **Redirect URI:** `urn:ietf:wg:oauth:2.0:oob` (paste the code by hand)
- **Confidential application:** yes
- **Permissions / scopes:**
  - `read_prefs` — read user preferences
  - `read_gpx` — read own GPS traces
  - `write_gpx` — upload GPS traces

Save the **Client ID** and **Client Secret** into `.env`.

Where to register:

- Test instance: https://openstreetmap.204-168-242-139.nip.io/oauth2/applications
- Local dev: http://localhost:3000/oauth2/applications
- Production: https://www.openstreetmap.org/oauth2/applications

### 2. Generate an access token

```bash
pip install requests-oauthlib
python osm_generate_token.py
```

It prints an authorization URL. Open it in the browser, log in, authorize,
copy the code shown on screen and paste it back. Save the resulting token
into `TOKEN=...` in `.env`.

### 3. Upload

```bash
./upload_gpx.sh
```

Reads `.gpx` files from `$GPX_DIR` (default `gpx_files`) and uploads each.
The result of every upload is appended to `upload_status.csv`:

```
OK,12317108,200,9
FAIL,12317114,413,
```

On re-runs, files already in the log (both `OK` and `FAIL`) are skipped.

### Retry failed uploads

Delete the `FAIL` rows and run again:

```bash
sed -i.bak '/^FAIL,/d' upload_status.csv
./upload_gpx.sh
```

Inspect failures:

```bash
grep ^FAIL, upload_status.csv
```

`413` means the GPX file is bigger than the server's upload limit. It
won't succeed until `client_max_body_size` is raised on the nginx in
front of openstreetmap-website.
