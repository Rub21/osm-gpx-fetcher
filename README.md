# gps-fetcher

Small Docker tool to download public GPS traces from openstreetmap.org RSS feed.

Used to collect a sample of GPX files for testing the GPS traces pipeline.

## Requirements

- Docker / Docker Compose

## Usage

```bash
# build
docker compose build

# run in background (watch mode, default config)
docker compose up -d

# follow logs
docker logs -f osm-gps-fetcher

# stop
docker compose down
```

## Config (env vars in docker-compose.yml)

| Variable              | Default | Description                                       |
|-----------------------|---------|---------------------------------------------------|
| `TARGET_COUNT`        | 10000   | Stop when this many `.gpx` files exist            |
| `DELAY`               | 2.0     | Seconds between individual downloads              |
| `LIMIT`               | 0       | Max traces per RSS fetch (0 = all in feed)        |
| `WATCH`               | 1       | Loop forever (1) or run once (0)                  |
| `WATCH_INTERVAL`      | 900     | Seconds between RSS fetches (15 min)              |
| `RATE_LIMIT_COOLDOWN` | 3600    | Pause on HTTP 429/503 (1 hour)                    |

## Output

```
data/
  gpx/                    # downloaded .gpx files (id_title.gpx)
  index.json              # metadata for each downloaded trace
```

## Notes

- The RSS feed only returns the ~20 most recent traces. To collect many,
  the script must run for hours/days, picking up new traces as they appear.
- Sets a `User-Agent` header identifying the tool.
- Skips files already downloaded.
- On HTTP 429/503 it pauses (respects `Retry-After` if present), then
  resumes automatically.
- For bulk historical data, use the planet GPX dump instead:
  https://planet.openstreetmap.org/gps/

## One-off run (no watch loop)

```bash
docker compose run --rm -e WATCH=0 fetcher --limit 5
```

## Upload GPX to OSM (osm-dev or production)

`upload_gpx.sh` uses the OSM API `POST /api/0.6/gpx` to push the downloaded
files. It needs an OAuth2 access token.

### 1. Register an OAuth2 application

On the target OSM instance go to **My Settings → OAuth 2 Applications →
Register new application** and create one with:

- **Name:** anything (e.g. `gps-fetcher-test`)
- **Redirect URI:** `urn:ietf:wg:oauth:2.0:oob` (out-of-band, paste the code by hand)
- **Confidential application:** yes
- **Permissions / scopes:**
  - `read_prefs` — read user preferences
  - `read_gpx` — read own GPS traces
  - `write_gpx` — upload GPS traces

Save the **Client ID** and **Client Secret**.

- Test instance: https://openstreetmap.204-168-242-139.nip.io/oauth2/applications
- Local dev: http://localhost:3000/oauth2/applications
- Production: https://www.openstreetmap.org/oauth2/applications

### 2. Generate an access token

```bash
pip install requests-oauthlib

export OSM_URL=https://openstreetmap.204-168-242-139.nip.io   # default
export CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxx
export CLIENT_SECRET=xxxxxxxxxxxxxxxxxx

python osm_generate_token.py
```

The script prints an authorization URL. Open it in the browser, log in,
authorize the app and copy the code shown on screen. Paste it back into
the terminal and you get the access token.

### 3. Upload the downloaded traces

```bash
export TOKEN=<access_token_from_step_2>
export OSM_URL=https://openstreetmap.204-168-242-139.nip.io
export GPX_DIR=data/gpx
./upload_gpx.sh
```
