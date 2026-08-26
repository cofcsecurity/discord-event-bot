# Discord Event Bot

Creates and syncs native Discord Scheduled Events for the CofC Cybersecurity Club server, and posts a same-day `@everyone` announcement on meeting days, all from the club website's meeting schedule (`data/schedule.yaml` in [cofcsecurity/cofcsecurity.github.io](https://github.com/cofcsecurity/cofcsecurity.github.io)). Each run makes API calls and exits; nothing runs continuously, and no bot needs to stay online afterward. Once events exist, they live in Discord's Events tab.

Two [scheduled GitHub Actions](#keeping-discord-in-sync-automatically) in this repo keep Discord in sync with the website and post meeting-day announcements automatically, so you generally don't need to run the script by hand — see that section for how they're wired up.

## Files

- `create_discord_events.py`: main script
- `images.yaml`: maps a meeting `date` to a local cover photo path (schedule.yaml itself has no `image` field — that file is owned by the website repo)
- `covers/`: cover photo files referenced by `images.yaml`
- `locked_events.json`: list of event names protected from editing/deletion (created automatically the first time you lock something, see [Locking events](#locking-events))

## One-time setup

### 1. Create a Discord bot application

1. Go to https://discord.com/developers/applications and click **New Application**. Name it anything (e.g. "CofC Cyber Events Bot").
2. In the left sidebar, click **Bot**.
3. Click **Reset Token** (or **Add Bot** if prompted), confirm, then click **Copy**. Discord only shows the token once, so save it somewhere safe. Treat it like a password; anyone with it can control the bot.

### 2. Grant permissions and add the bot to the server

1. In the left sidebar, click **OAuth2 → URL Generator**.
2. Under **Scopes**, check `bot`.
3. Under **Bot Permissions**, check `Manage Events`, `Send Messages`, and `Mention @everyone, @here, and All Roles` (needed for the [meeting-day announcement](#announce)).
4. Copy the generated URL at the bottom of the page, open it in a browser, and select the CofC Cybersecurity Club server to add the bot.
5. In the server itself, make sure the bot's role has permission to post in whichever channel you want announcements to go to.

### 3. Install Python dependencies

```
python3 -m pip install -r requirements.txt
```

If you have multiple Python installs and aren't sure which one runs your script, use the exact interpreter path, e.g.:

```
/usr/bin/python3 -m pip install -r requirements.txt
```

### 4. Set your bot token

Set it as an environment variable rather than pasting it into the script. This keeps it out of any file you might accidentally share or commit:

```
export DISCORD_BOT_TOKEN="paste-your-token-here"
```

This only lasts for the current terminal session. You'll need to run it again if you open a new terminal window/tab later. Confirm it's set with:

```
echo $DISCORD_BOT_TOKEN
```

### 5. Set the announcements channel ID (only needed for `announce`)

1. In Discord, enable Developer Mode: **User Settings → Advanced → Developer Mode**.
2. Right-click the channel meeting-day announcements should post to, and click **Copy Channel ID**.
3. Set it as an environment variable the same way as the bot token:

```
export ANNOUNCE_CHANNEL_ID="paste-the-channel-id-here"
```

## Running the script

From this folder, the script accepts a subcommand. Leaving it off defaults to `create`:

```
python3 create_discord_events.py [create|edit|sync|announce|delete|wipe|lock|unlock|locked]
```

Run `python3 create_discord_events.py --help` (or `<command> --help`) any time for a quick reminder of what's available.

By default the script fetches the schedule straight from the website repo's `master` branch (`SCHEDULE_URL`, see [create_discord_events.py](create_discord_events.py) for the exact URL), so it always reflects whatever's live on the site. For local testing against a schedule you haven't pushed yet, point it at a file instead:

```
SCHEDULE_PATH=../cofcsecurity.github.io/data/schedule.yaml python3 create_discord_events.py
```

### `create` (default)

```
python3 create_discord_events.py
```

- Reads every non-skipped meeting from `schedule.yaml`.
- Checks the server's existing scheduled events first, and **skips any event whose title already exists**, so it's safe to re-run without creating duplicates if a previous run got interrupted.
- Creates the remaining events one at a time, waiting between requests to respect Discord's rate limits. If Discord still responds with a rate-limit error, it automatically waits the exact time Discord asks for and retries.
- For events that already exist but don't have a cover photo yet, backfills one from `images.yaml` (skipped for [locked](#locking-events) events).
- At the end it prints a summary: how many were created, how many cover photos were backfilled, skipped, and failed, with error details for any failures.

Expected output looks like:

```
[OK] 2026-08-25  Introduction to the Club & CTF Basics
[SKIP] Introduction to Cyber Competitions (already exists)
[IMG] Basic Host Hardening (cover photo added)
[LOCKED] Open Lab Project Day & Catch-up (skipped)
...
22 created, 1 cover photos added, 5 skipped (already existed or locked), 0 failed.
```

Check the result in Discord: open the server, click the server name at the top, and select **Events**.

### `edit`

```
python3 create_discord_events.py edit
```

For every meeting in `schedule.yaml` that matches an event already in Discord (by title), updates that event's title, description, date/time, location, and image to match it: a full sync, not just a cover-photo backfill. Events that don't exist yet are left alone (run `create` first, or use `sync` to do both). [Locked](#locking-events) events are skipped and printed as `[LOCKED]`.

### `sync`

```
python3 create_discord_events.py sync
```

Runs `create` then `edit` in one pass: creates any meeting missing from Discord, then updates the rest to match `schedule.yaml`. This is what the [scheduled GitHub Action](#keeping-discord-in-sync-automatically) runs; you generally only need to run it by hand to test a change before it's pushed.

### `announce`

```
python3 create_discord_events.py announce
```

Looks up today's date (Eastern time) in `schedule.yaml`. If there's a meeting and it's not `skipped`, posts a `@everyone` message to the channel set as [`ANNOUNCE_CHANNEL_ID`](#5-set-the-announcements-channel-id-only-needed-for-announce) with the topic, day/date/time, location, the voice-chat link, the cover photo (from `images.yaml`, if set), and a link to that meeting's slides (from `schedule.yaml`'s `slides` field, if set). If there's no meeting today (including a `skipped` one, like a break week), it prints a note and exits without posting.

This is what the [Tuesday/Thursday scheduled GitHub Action](#keeping-discord-in-sync-automatically) runs. It always posts for real (no dry-run mode) — use the flags below to test safely instead.

**Testing it**: add `--no-ping` to post without pinging `@everyone` (the message says so instead, so it's obviously a test), and `--date YYYY-MM-DD` to preview a specific meeting instead of whatever's scheduled for today:

```
python3 create_discord_events.py announce --no-ping --date 2026-08-27
```

This still posts a real message to `ANNOUNCE_CHANNEL_ID`, just without the ping — good for checking formatting, the cover photo, and the slide link before trusting the unattended Tuesday/Thursday run.

The cover photo (if set in `images.yaml`) is attached to the message as an image, shown below the text. A posted message looks like this:

> @everyone
> **Meeting today: Introduction to the Club & CTF Basics**
> 🗓️ Tuesday, August 25 · 17:30–19:30
> 📍 Harbor Walk East 105F
>
> Week after classes start. Club overview, team roles, and a beginner CTF covering CS/security basics.
>
> 🎙️ **Join by voice chat:** https://discord.com/channels/745067181422673941/745067181909344289
> 🎥 **This meeting will be recorded** and saved for later viewing.
> 📑 **Slides:** https://cofcsecurity.github.io/slides/01-introduction.pptx
>
> *[cover photo attached, if one is set for this meeting in `images.yaml`]*

### `delete`

```
python3 create_discord_events.py delete "Event Title"
```

Deletes one event by its exact title. Asks for `[y/N]` confirmation first unless you pass `--yes`. Refuses (and tells you) if the event is [locked](#locking-events); unlock it first if you're sure.

### `wipe`

```
python3 create_discord_events.py wipe
```

Deletes **every** event currently on the server, except [locked](#locking-events) ones. Lists exactly what will be deleted and what will be kept, then requires you to type `WIPE` to confirm (or pass `--yes` to skip the prompt). This is permanent (there's no undo), so use `lock` beforehand on anything you want to keep.

### Locking events

Locking protects an event from `edit`, `delete`, and `wipe`. Useful for anything already RSVP'd to, or hand-edited directly in Discord, that you don't want a future schedule sync to touch.

```
python3 create_discord_events.py lock "Event Title"
python3 create_discord_events.py unlock "Event Title"
python3 create_discord_events.py locked
```

`lock`/`unlock` just add or remove the exact title from `locked_events.json` in this folder. No Discord API call is made, so it works even for events you haven't created yet. `locked` lists everything currently protected. There's no override flag for locked events by design; to change or delete one, `unlock` it first.

## Modifying the schedule

The meeting schedule itself lives in [`data/schedule.yaml`](https://github.com/cofcsecurity/cofcsecurity.github.io/blob/master/data/schedule.yaml) in the **club website repo**, not here — it's the same file that drives the site's schedule page, "next meeting" callout, and calendar (`.ics`) feed. Edit it there; this repo only adds cover photos on top (see [Cover photos](#cover-photos) below) and picks the schedule up automatically.

### Schedule fields (in the website repo)

| Field | Required | Description |
|---|---|---|
| `date` | Yes | Meeting date, `YYYY-MM-DD` |
| `topic` | Yes | Event name, shown as the event title in Discord |
| `notes` | Yes | Event details, shown under the title in Discord. The voice-chat link and recording notice are added automatically, don't repeat them here. |
| `day` | Yes | Day name, shown on the website (not used by this bot) |
| `week` | No | Week number, shown on the website (not used by this bot) |
| `start` | No | 24-hour `HH:MM`. Leave out to use the default (5:30 PM). |
| `end` | No | Same format. Leave out to use the default (7:30 PM). |
| `location` | No | Overrides the schedule-wide default location (`location:` at the top of the file) for just this meeting. |
| `slides` | No | Path to that meeting's slides, relative to the website's `static/` folder (e.g. `slides/03-virtualization.pptx`). Shown as a "Slides" link on the site, and included in the [`announce`](#announce) message. Leave out if there are no slides for that meeting. |
| `skipped` | No | Set `true` for a no-meeting week (e.g. a break). This bot ignores those entries entirely — no Discord event is created and no announcement is posted for them. |

### Adding, removing, or changing a meeting

Add, delete, or edit an entry under `meetings:` in `schedule.yaml` and push to `master`. That push [triggers this repo's sync automatically](#keeping-discord-in-sync-automatically) — no separate step needed here. If you'd rather push the change to Discord yourself first (e.g. to check it before it goes live on the site), run `sync` locally with `SCHEDULE_PATH` pointed at your local copy, as described [above](#running-the-script).

Removing a meeting from `schedule.yaml` does **not** delete it from Discord — `sync` only creates and updates, it never deletes. Run `delete "Exact Event Title"` (or `wipe`) yourself if you need the Discord event gone too.

### Cover photos

Cover photos are specific to Discord, so they're **not** part of `schedule.yaml` — they're mapped in this repo's own [`images.yaml`](images.yaml), keyed by meeting `date`:

```yaml
"2026-08-30": covers/guest-talk.jpg
```

Drop the image file in `covers/` (or point to any path readable from where the script runs) and add its date to `images.yaml`. Supports PNG, JPEG, GIF, and WebP, up to 10 MB. Discord displays these at a 16:9 crop, so a landscape image (e.g. 1920x1080) looks best.

If the path doesn't exist, the type is unsupported, or the file is too large, the script prints a warning and creates the event without a cover photo instead of failing.

If an event already exists in Discord (e.g. it was created before you added an image for it), running `create` (or `sync`) won't recreate it, but it **will** backfill the cover photo, as long as the event doesn't already have one set. It never overwrites a cover photo that's already there, so anything set manually in Discord is left alone. This shows up in the output as `[IMG] <name> (cover photo added)`.

### Changing the defaults for every meeting

Open `create_discord_events.py` and edit the constants near the top:

```python
DEFAULT_START = "17:30"
DEFAULT_END = "19:30"
DEFAULT_LOCATION = "Simons Center for the Arts, Room 281"  # only used if schedule.yaml has no top-level `location`
VOICE_CHANNEL_URL = "https://discord.com/channels/745067181422673941/745067181909344289"
```

`DEFAULT_LOCATION` here is a last-resort fallback; in practice the per-meeting location comes from `schedule.yaml`'s own `location` field. Changing these only affects events created *after* the change; it won't retroactively update anything already posted to Discord.

## Keeping Discord in sync automatically

Two GitHub Actions workflows in this repo run without anyone touching the script by hand:

### [`sync.yml`](.github/workflows/sync.yml) — creates/updates events from `schedule.yaml`

- **On push**: the [website repo has a workflow](https://github.com/cofcsecurity/cofcsecurity.github.io/blob/master/.github/workflows/notify-event-bot.yml) that fires a `repository_dispatch` here whenever `data/schedule.yaml` changes on `master`, which triggers `sync` within a minute or two.
- **Daily, as a safety net**: also runs once a day (9 AM Eastern) in case a dispatch is ever missed.
- **On demand**: trigger it manually from this repo's Actions tab (`Sync Discord Events` → `Run workflow`).

### [`announce.yml`](.github/workflows/announce.yml) — posts the meeting-day announcement

- Runs every Tuesday and Thursday at 9 AM Eastern, calling `announce`. Edit the cron line in the workflow to change how far ahead of the 5:30 PM meeting it posts.
- Also runnable on demand from the Actions tab (`Announce Today's Meeting` → `Run workflow`), which is the easiest way to test it before relying on the schedule.

### Secrets these need

- **This repo** (Settings → Secrets and variables → Actions): `DISCORD_BOT_TOKEN` (same token as [step 4](#4-set-your-bot-token)) for both workflows, plus `ANNOUNCE_CHANNEL_ID` (see [step 5](#5-set-the-announcements-channel-id-only-needed-for-announce)) for `announce.yml`.
- **The website repo**: `DISCORD_BOT_DISPATCH_TOKEN`, a GitHub personal access token with permission to trigger workflows on `cofcsecurity/discord-event-bot` (fine-grained PAT scoped to that repo with **Actions: read and write**). Until it's set, the website-side workflow just skips quietly and the daily `sync` cron still catches changes within a day.

## Troubleshooting

**`ModuleNotFoundError: No module named 'requests'` (or `'yaml'`)**
Install dependencies for the same Python interpreter you're running the script with: `python3 -m pip install -r requirements.txt`.

**`Set DISCORD_BOT_TOKEN, e.g. export DISCORD_BOT_TOKEN="..."`**
The environment variable isn't set in your current terminal session. Run the `export` command again, then the script, in the same window.

**`401: Unauthorized` from Discord**
The token is wrong, was reset since you copied it, or wasn't included correctly. Re-copy it from the Bot page in the Developer Portal and re-export it.

**`403: Forbidden` or a missing-permissions error**
The bot either isn't in the server, or is missing the "Manage Events" permission. Redo the OAuth2 URL step and make sure `Manage Events` is checked before generating the invite link.

**`429: You are being rate limited`**
Expected occasionally with many events; the script automatically waits and retries. If it fails repeatedly, just re-run the script; it will skip everything already created and pick up where it left off.

**`NotOpenSSLWarning` about LibreSSL**
Harmless. It's a warning, not an error, related to macOS's older SSL library. Ignore it.