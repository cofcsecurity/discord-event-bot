# Discord Event Bot

Bulk-creates native Discord Scheduled Events for the CofC Cybersecurity Club server from a spreadsheet of dates and topics. Run it once per batch of events. It makes API calls and exits. Nothing runs continuously, and no bot needs to stay online afterward. Once the events exist, they live in Discord's Event's Tab.

## Files

- `create_discord_events.py`: main script
- `events.csv`: meeting schedule
## One-time setup

### 1. Create a Discord bot application

1. Go to https://discord.com/developers/applications and click **New Application**. Name it anything (e.g. "CofC Cyber Events Bot").
2. In the left sidebar, click **Bot**.
3. Click **Reset Token** (or **Add Bot** if prompted), confirm, then click **Copy**. Discord only shows the token once — save it somewhere safe. Treat it like a password; anyone with it can control the bot.

### 2. Grant permissions and add the bot to the server

1. In the left sidebar, click **OAuth2 → URL Generator**.
2. Under **Scopes**, check `bot`.
3. Under **Bot Permissions**, check `Manage Events`.
4. Copy the generated URL at the bottom of the page, open it in a browser, and select the CofC Cybersecurity Club server to add the bot.

### 3. Install Python dependencies

```
python3 -m pip install requests
```

If you have multiple Python installs and aren't sure which one runs your script, use the exact interpreter path, e.g.:

```
/usr/bin/python3 -m pip install requests
```

### 4. Set your bot token

Set it as an environment variable rather than pasting it into the script — this keeps it out of any file you might accidentally share or commit:

```
export DISCORD_BOT_TOKEN="paste-your-token-here"
```

This only lasts for the current terminal session. You'll need to run it again if you open a new terminal window/tab later. Confirm it's set with:

```
echo $DISCORD_BOT_TOKEN
```

## Running the script

From the folder containing both files:

```
python3 create_discord_events.py
```

What happens:

- It reads every row in `events.csv`.
- It checks the server's existing scheduled events first, and **skips any event whose title already exists** — so it's safe to re-run without creating duplicates if a previous run got interrupted.
- It creates the remaining events one at a time, waiting between requests to respect Discord's rate limits. If Discord still responds with a rate-limit error, it automatically waits the exact time Discord asks for and retries.
- At the end it prints a summary: how many were created, skipped, and failed, with error details for any failures.

Expected output looks like:

```
[OK] 2026-08-25  Introduction to the Club & CTF Basics
[SKIP] Introduction to Cyber Competitions (already exists)
[IMG] Basic Host Hardening (cover photo added)
...
22 created, 1 cover photos added, 5 skipped (already existed), 0 failed.
```

Check the result in Discord: open the server, click the server name at the top, and select **Events**.

## Modifying the schedule

Everything you'd normally change lives in `events.csv` — no need to touch the Python file.

### Columns

| Column | Required | Description |
|---|---|---|
| `date` | Yes | Meeting date, format `YYYY-MM-DD` (e.g. `2026-08-25`) |
| `title` | Yes | Event name, shown as the event title in Discord |
| `description` | Yes | Event details, shown under the title. The voice-chat link and recording notice are added automatically — don't repeat them here. |
| `start_time` | No | 24-hour format `HH:MM` (e.g. `17:30`). Leave blank to use the default (5:30 PM). |
| `end_time` | No | Same format. Leave blank to use the default (7:30 PM). |
| `location` | No | Physical room or text location. Leave blank to use the default (Simons 281). |
| `image` | No | Path to a cover photo for the event (relative to where you run the script, or absolute). Leave blank for no cover photo. Supports PNG, JPEG, GIF, and WebP, up to 10 MB. Discord displays these at a 16:9 crop, so a landscape image (e.g. 1920x1080) looks best. |

### Adding a new meeting

Add a new row to `events.csv` with at least `date`, `title`, and `description` filled in. Leave `start_time`, `end_time`, and `location` blank to inherit the defaults, or fill them in to override just that meeting.

Example — a one-off meeting in a different room:

```csv
2026-08-30,Special Guest Talk,"Guest speaker from industry on career paths in security.",18:00,19:30,Simons 105,
```

### Adding a cover photo to a meeting

Fill in the `image` column with a path to an image file. It's read from disk and uploaded when the event is created — the file itself doesn't need to be committed anywhere Discord can see it, just present on your machine when you run the script.

```csv
2026-08-30,Special Guest Talk,"Guest speaker from industry on career paths in security.",18:00,19:30,Simons 105,images/guest-talk.jpg
```

If the path doesn't exist, the type is unsupported, or the file is too large, the script prints a warning and creates the event without a cover photo instead of failing.

If an event already exists in Discord (e.g. it was created before you added an `image` for it), the script won't recreate it, but it **will** backfill the cover photo — as long as the event doesn't already have one set. It never overwrites a cover photo that's already there, so anything set manually in Discord is left alone. This shows up in the output as `[IMG] <name> (cover photo added)`.

### Removing a meeting

Delete its row from `events.csv`. This does **not** remove the event from Discord if it was already created — you'll need to delete it manually from the Events tab in Discord (or leave it, since it just won't be re-created).

### Changing an already-created meeting

Editing `events.csv` and re-running the script will **not** update an event that already exists in Discord — the script only skips or creates, it never edits. To change a meeting that's already posted, either:

- Edit it directly in Discord (Events tab → click the event → Edit), or
- Delete it in Discord, then re-run the script so it gets recreated from the CSV with the new details.

### Changing the defaults for every meeting

Open `create_discord_events.py` and edit the constants near the top:

```python
DEFAULT_START = "17:30"
DEFAULT_END = "19:30"
DEFAULT_LOCATION = "Simons 281"
VOICE_CHANNEL_URL = "https://discord.com/channels/745067181422673941/745067181909344289"
```

Changing these only affects events created *after* the change — it won't retroactively update anything already posted to Discord.

## Troubleshooting

**`ModuleNotFoundError: No module named 'requests'`**
Install it for the same Python interpreter you're running the script with: `python3 -m pip install requests`.

**`Set DISCORD_BOT_TOKEN, e.g. export DISCORD_BOT_TOKEN="..."`**
The environment variable isn't set in your current terminal session. Run the `export` command again, then the script, in the same window.

**`401: Unauthorized` from Discord**
The token is wrong, was reset since you copied it, or wasn't included correctly. Re-copy it from the Bot page in the Developer Portal and re-export it.

**`403: Forbidden` or a missing-permissions error**
The bot either isn't in the server, or is missing the "Manage Events" permission. Redo the OAuth2 URL step and make sure `Manage Events` is checked before generating the invite link.

**`429: You are being rate limited`**
Expected occasionally with many events; the script automatically waits and retries. If it fails repeatedly, just re-run the script — it will skip everything already created and pick up where it left off.

**`NotOpenSSLWarning` about LibreSSL**
Harmless. It's a warning, not an error, related to macOS's older SSL library. Ignore it.