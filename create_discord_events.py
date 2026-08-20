import base64
import csv
import mimetypes
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

GUILD_ID = "745067181422673941"
CSV_PATH = "events.csv"
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TZ = ZoneInfo("America/New_York")
DEFAULT_START = "17:30"
DEFAULT_END = "19:30"
DEFAULT_LOCATION = "Simons 281"
VOICE_CHANNEL_URL = "https://discord.com/channels/745067181422673941/745067181909344289"
FOOTER = (
    f"🎙️ **Join by voice chat:** {VOICE_CHANNEL_URL}\n"
    f"🎥 **This meeting will be recorded** and saved for later viewing."
)

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit('Set DISCORD_BOT_TOKEN, e.g. export DISCORD_BOT_TOKEN="..."')

API_BASE = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}


def load_events(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def encode_image(path):
    if not path:
        return None
    if not os.path.isfile(path):
        print(f"  [WARN] image not found: {path}, skipping cover photo")
        return None

    size = os.path.getsize(path)
    if size > MAX_IMAGE_BYTES:
        print(f"  [WARN] image too large ({size / 1_000_000:.1f} MB): {path}, skipping cover photo")
        return None

    mime, _ = mimetypes.guess_type(path)
    if mime not in IMAGE_TYPES:
        print(f"  [WARN] unsupported image type for {path}, skipping cover photo")
        return None

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_payload(row):
    date = row["date"].strip()
    start_time = row.get("start_time", "").strip() or DEFAULT_START
    end_time = row.get("end_time", "").strip() or DEFAULT_END
    location = row.get("location", "").strip() or DEFAULT_LOCATION
    image = encode_image((row.get("image") or "").strip())

    start = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    end = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)

    payload = {
        "name": row["title"].strip(),
        "description": f"{row['description'].strip()}\n\n{FOOTER}",
        "scheduled_start_time": start.isoformat(),
        "scheduled_end_time": end.isoformat(),
        "privacy_level": 2,
        "entity_type": 3,
        "entity_metadata": {"location": location},
    }
    if image:
        payload["image"] = image
    return payload


def existing_event_names(url):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return {e["name"] for e in resp.json()}


def post_with_retry(url, payload, max_retries=5):
    for attempt in range(max_retries):
        resp = requests.post(url, headers=HEADERS, json=payload)
        if resp.status_code != 429:
            return resp
        wait = resp.json().get("retry_after", 2) + 0.5
        print(f"  rate limited, waiting {wait:.1f}s...")
        time.sleep(wait)
    return resp


def main():
    events = load_events(CSV_PATH)
    url = f"{API_BASE}/guilds/{GUILD_ID}/scheduled-events"
    already = existing_event_names(url)
    created, skipped, failed = 0, 0, []

    for row in events:
        payload = build_payload(row)
        if payload["name"] in already:
            skipped += 1
            print(f"[SKIP] {payload['name']} (already exists)")
            continue

        resp = post_with_retry(url, payload)
        if resp.ok:
            created += 1
            print(f"[OK] {payload['scheduled_start_time'][:10]}  {payload['name']}")
        else:
            failed.append((payload["name"], resp.status_code, resp.text))
            print(f"[FAIL] {payload['name']} -> {resp.status_code}: {resp.text}")
        time.sleep(1.5)

    print(f"\n{created} created, {skipped} skipped (already existed), {len(failed)} failed.")
    for name, code, text in failed:
        print(f"  {name}: {code} {text}")


if __name__ == "__main__":
    main()