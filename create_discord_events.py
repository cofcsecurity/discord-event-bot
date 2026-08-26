import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yaml

GUILD_ID = "745067181422673941"
SCHEDULE_URL = os.environ.get(
    "SCHEDULE_URL",
    "https://raw.githubusercontent.com/cofcsecurity/cofcsecurity.github.io/master/data/schedule.yaml",
)
SCHEDULE_PATH = os.environ.get("SCHEDULE_PATH")  # local file override, mainly for testing
IMAGES_PATH = "images.yaml"
LOCK_PATH = "locked_events.json"
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TZ = ZoneInfo("America/New_York")
DEFAULT_START = "17:30"
DEFAULT_END = "19:30"
DEFAULT_LOCATION = "Simons Center for the Arts, Room 281"
VOICE_CHANNEL_URL = "https://discord.com/channels/745067181422673941/745067181909344289"
FOOTER = (
    f"🎙️ **Join by voice chat:** {VOICE_CHANNEL_URL}\n"
    f"🎥 **This meeting will be recorded** and saved for later viewing."
)

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
ANNOUNCE_CHANNEL_ID = os.environ.get("ANNOUNCE_CHANNEL_ID")
SITE_BASE_URL = "https://cofcsecurity.github.io"
API_BASE = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}


def load_schedule():
    if SCHEDULE_PATH:
        with open(SCHEDULE_PATH, encoding="utf-8") as f:
            text = f.read()
    else:
        resp = requests.get(SCHEDULE_URL)
        resp.raise_for_status()
        text = resp.text
    return yaml.safe_load(text)


def load_images():
    if not os.path.isfile(IMAGES_PATH):
        return {}
    with open(IMAGES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {str(k): v for k, v in data.items()}


def load_events():
    schedule = load_schedule()
    default_location = schedule.get("location") or DEFAULT_LOCATION
    images = load_images()

    rows = []
    for meeting in schedule.get("meetings", []):
        if meeting.get("skipped") or not meeting.get("topic"):
            continue
        meeting_date = str(meeting["date"])
        rows.append({
            "date": meeting_date,
            "title": meeting["topic"].strip(),
            "description": (meeting.get("notes") or "").strip(),
            "start_time": meeting.get("start") or DEFAULT_START,
            "end_time": meeting.get("end") or DEFAULT_END,
            "location": meeting.get("location") or default_location,
            "image": images.get(meeting_date, ""),
            "slides": (meeting.get("slides") or "").strip(),
        })
    return rows


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


def build_announcement(row):
    date = datetime.strptime(row["date"], "%Y-%m-%d").date()
    start_time = row.get("start_time", "").strip() or DEFAULT_START
    end_time = row.get("end_time", "").strip() or DEFAULT_END
    location = row.get("location", "").strip() or DEFAULT_LOCATION

    lines = [
        "@everyone",
        f"**Meeting today: {row['title'].strip()}**",
        f"🗓️ {date.strftime('%A, %B %-d')} · {start_time}–{end_time}",
        f"📍 {location}",
        "",
        row.get("description", "").strip(),
        "",
        FOOTER,
    ]
    slides = (row.get("slides") or "").strip()
    if slides:
        lines.append(f"📑 **Slides:** {SITE_BASE_URL}/{slides}")
    return "\n".join(lines)


def cmd_announce():
    if not ANNOUNCE_CHANNEL_ID:
        sys.exit('Set ANNOUNCE_CHANNEL_ID, e.g. export ANNOUNCE_CHANNEL_ID="..."')

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    todays = [row for row in load_events() if row["date"] == today]

    if not todays:
        print(f"No meeting scheduled for {today}, nothing to announce.")
        return

    url = f"{API_BASE}/channels/{ANNOUNCE_CHANNEL_ID}/messages"
    for row in todays:
        content = build_announcement(row)
        payload = {"content": content, "allowed_mentions": {"parse": ["everyone"]}}

        image_path = (row.get("image") or "").strip()
        image_bytes = image_name = image_mime = None
        if image_path and os.path.isfile(image_path):
            mime, _ = mimetypes.guess_type(image_path)
            if os.path.getsize(image_path) <= MAX_IMAGE_BYTES and mime in IMAGE_TYPES:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                image_name, image_mime = os.path.basename(image_path), mime

        if image_bytes:
            files = {"files[0]": (image_name, image_bytes, image_mime)}
            resp = requests.post(
                url,
                headers={"Authorization": HEADERS["Authorization"]},
                data={"payload_json": json.dumps(payload)},
                files=files,
            )
        else:
            resp = requests.post(url, headers=HEADERS, json=payload)

        if resp.ok:
            print(f"[ANNOUNCE] {row['title']}")
        else:
            print(f"[ANNOUNCE-FAIL] {row['title']} -> {resp.status_code}: {resp.text}")


def existing_events_by_name(url):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return {e["name"]: e for e in resp.json()}


def request_with_retry(method, url, payload, max_retries=5):
    for attempt in range(max_retries):
        resp = requests.request(method, url, headers=HEADERS, json=payload)
        if resp.status_code != 429:
            return resp
        wait = resp.json().get("retry_after", 2) + 0.5
        print(f"  rate limited, waiting {wait:.1f}s...")
        time.sleep(wait)
    return resp


def load_locked():
    if not os.path.isfile(LOCK_PATH):
        return set()
    with open(LOCK_PATH, encoding="utf-8") as f:
        return set(json.load(f))


def save_locked(locked):
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(locked), f, indent=2)
        f.write("\n")


def cmd_create(url, locked):
    events = load_events()
    already = existing_events_by_name(url)
    created, skipped, backfilled, failed = 0, 0, 0, []

    for row in events:
        payload = build_payload(row)
        name = payload["name"]

        if name in already:
            if name in locked:
                skipped += 1
                print(f"[LOCKED] {name} (skipped)")
                continue

            existing = already[name]
            if payload.get("image") and not existing.get("image"):
                resp = request_with_retry("PATCH", f"{url}/{existing['id']}", {"image": payload["image"]})
                if resp.ok:
                    backfilled += 1
                    print(f"[IMG] {name} (cover photo added)")
                else:
                    failed.append((name, resp.status_code, resp.text))
                    print(f"[IMG-FAIL] {name} -> {resp.status_code}: {resp.text}")
                time.sleep(1.5)
            else:
                skipped += 1
                print(f"[SKIP] {name} (already exists)")
            continue

        resp = request_with_retry("POST", url, payload)
        if resp.ok:
            created += 1
            print(f"[OK] {payload['scheduled_start_time'][:10]}  {name}")
        else:
            failed.append((name, resp.status_code, resp.text))
            print(f"[FAIL] {name} -> {resp.status_code}: {resp.text}")
        time.sleep(1.5)

    print(
        f"\n{created} created, {backfilled} cover photos added, "
        f"{skipped} skipped (already existed or locked), {len(failed)} failed."
    )
    for name, code, text in failed:
        print(f"  {name}: {code} {text}")


def cmd_edit(url, locked):
    events = load_events()
    existing = existing_events_by_name(url)
    updated, skipped_locked, not_found, failed = 0, 0, 0, []

    for row in events:
        payload = build_payload(row)
        name = payload["name"]

        if name not in existing:
            not_found += 1
            print(f"[SKIP] {name} (not created yet, run with no arguments to create it)")
            continue

        if name in locked:
            skipped_locked += 1
            print(f"[LOCKED] {name} (skipped)")
            continue

        event_id = existing[name]["id"]
        resp = request_with_retry("PATCH", f"{url}/{event_id}", payload)
        if resp.ok:
            updated += 1
            print(f"[EDIT] {name}")
        else:
            failed.append((name, resp.status_code, resp.text))
            print(f"[EDIT-FAIL] {name} -> {resp.status_code}: {resp.text}")
        time.sleep(1.5)

    print(
        f"\n{updated} updated, {skipped_locked} skipped (locked), "
        f"{not_found} not found, {len(failed)} failed."
    )
    for name, code, text in failed:
        print(f"  {name}: {code} {text}")


def cmd_delete(url, locked, args):
    existing = existing_events_by_name(url)
    name = args.name

    if name not in existing:
        sys.exit(f"No event named '{name}' found.")

    if name in locked:
        sys.exit(f"'{name}' is locked. Run `unlock \"{name}\"` first if you really want to delete it.")

    if not args.yes:
        answer = input(f"Delete event '{name}' from Discord? This cannot be undone. [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    event_id = existing[name]["id"]
    resp = request_with_retry("DELETE", f"{url}/{event_id}", None)
    if resp.ok:
        print(f"[DEL] {name}")
    else:
        print(f"[DEL-FAIL] {name} -> {resp.status_code}: {resp.text}")


def cmd_wipe(url, locked, args):
    existing = existing_events_by_name(url)
    targets = {name: e for name, e in existing.items() if name not in locked}
    kept = sorted(name for name in existing if name in locked)

    if not targets:
        print("Nothing to wipe (no events exist, or all existing events are locked).")
        return

    print(f"This will permanently delete {len(targets)} event(s):")
    for name in sorted(targets):
        print(f"  - {name}")
    if kept:
        print(f"\n{len(kept)} locked event(s) will be kept:")
        for name in kept:
            print(f"  - {name}")

    if not args.yes:
        confirm = input(f"\nType WIPE to permanently delete these {len(targets)} event(s): ")
        if confirm != "WIPE":
            print("Aborted.")
            return

    deleted, failed = 0, []
    for name, event in targets.items():
        resp = request_with_retry("DELETE", f"{url}/{event['id']}", None)
        if resp.ok:
            deleted += 1
            print(f"[DEL] {name}")
        else:
            failed.append((name, resp.status_code, resp.text))
            print(f"[DEL-FAIL] {name} -> {resp.status_code}: {resp.text}")
        time.sleep(1.5)

    print(f"\n{deleted} deleted, {len(kept)} locked (kept), {len(failed)} failed.")
    for name, code, text in failed:
        print(f"  {name}: {code} {text}")


def cmd_sync(url, locked):
    """Create anything missing from schedule.yaml, then update existing events to match it. Used by CI."""
    cmd_create(url, locked)
    cmd_edit(url, locked)


def cmd_lock(args, locked):
    if args.name in locked:
        print(f"'{args.name}' is already locked.")
        return
    locked.add(args.name)
    save_locked(locked)
    print(f"[LOCK] {args.name}")


def cmd_unlock(args, locked):
    if args.name not in locked:
        print(f"'{args.name}' is not locked.")
        return
    locked.discard(args.name)
    save_locked(locked)
    print(f"[UNLOCK] {args.name}")


def cmd_show_locked(locked):
    if not locked:
        print("No events are locked.")
        return
    print(f"{len(locked)} locked event(s):")
    for name in sorted(locked):
        print(f"  - {name}")


def build_parser():
    parser = argparse.ArgumentParser(description="Manage Discord scheduled events from schedule.yaml")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("create", help="Create events from schedule.yaml that don't exist yet, and backfill missing cover photos (default)")
    sub.add_parser("edit", help="Update existing events to match schedule.yaml (skips locked events)")
    sub.add_parser("sync", help="create + edit in one pass: create what's missing, update the rest to match schedule.yaml (used by CI)")
    sub.add_parser("announce", help="post an @everyone announcement to the announcements channel for today's meeting, if there is one (used by CI)")

    p_delete = sub.add_parser("delete", help="Delete a single event by exact name")
    p_delete.add_argument("name")
    p_delete.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")

    p_wipe = sub.add_parser("wipe", help="Delete ALL events except locked ones")
    p_wipe.add_argument("--yes", action="store_true", help="Skip the typed confirmation prompt")

    p_lock = sub.add_parser("lock", help="Lock an event by name (immune to edit/delete/wipe)")
    p_lock.add_argument("name")

    p_unlock = sub.add_parser("unlock", help="Unlock a previously locked event")
    p_unlock.add_argument("name")

    sub.add_parser("locked", help="List currently locked events")

    return parser


def main():
    args = build_parser().parse_args()
    command = args.command or "create"

    if not BOT_TOKEN:
        sys.exit('Set DISCORD_BOT_TOKEN, e.g. export DISCORD_BOT_TOKEN="..."')

    url = f"{API_BASE}/guilds/{GUILD_ID}/scheduled-events"
    locked = load_locked()

    if command == "create":
        cmd_create(url, locked)
    elif command == "edit":
        cmd_edit(url, locked)
    elif command == "sync":
        cmd_sync(url, locked)
    elif command == "announce":
        cmd_announce()
    elif command == "delete":
        cmd_delete(url, locked, args)
    elif command == "wipe":
        cmd_wipe(url, locked, args)
    elif command == "lock":
        cmd_lock(args, locked)
    elif command == "unlock":
        cmd_unlock(args, locked)
    elif command == "locked":
        cmd_show_locked(locked)


if __name__ == "__main__":
    main()