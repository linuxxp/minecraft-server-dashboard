#!/usr/bin/env python3
"""
Minecraft Access Log Web Viewer
Runs on port 8090.

Version: 1.16.1
Changelog:
  v1.16.1 (2026-05-07)
    - FIX: plugin <-> JAR matching was wrong for plugins whose names share a
      prefix (ViaVersion + ViaVersionStatus, WorldEdit + WorldGuard, etc.).
      The old logic used substring `pname in fname` and "first candidate wins"
      based on os.listdir() order, so both ViaVersion and ViaVersionStatus
      could end up pointing to ViaVersionStatus.jar — and clicking Update on
      ViaVersion would have downloaded ViaVersionStatus's URL into the wrong
      file.
      New logic computes a similarity score for every (plugin, JAR) pair
      (exact match > "name-version.jar" pattern > prefix > substring fallback),
      then assigns greedily by score with each JAR claimed at most once.
  v1.16.0 (2026-05-06)
    - Chat moved to dedicated /chat page accessible from main nav.
      Removed inline chat panel from dashboard.
    - Persistent chat history in /home/pi/mc-chat-log.json (written by
      mc-access-logger.py v1.4.0). Default range now 24h, with selector for
      1h / 6h / 24h / 7d / 30d / 90d.
    - Search box (highlight matches), sender filter (any/players/server),
      day separators, optional 5s live mode.
    - 90-day retention, 50000-message cap on persisted file.
    - /api/chat now reads from file; falls back to live docker logs scrape
      only when file is empty (fresh deploy).
  v1.15.0 (2026-05-06)
    - Plugin update dedup: download to staging file, SHA-256 vs current; if
      identical, discard the download and report "unchanged" (no JAR replaced,
      no restart banner). History records "unchanged" status.
    - Failed downloads no longer overwrite the existing JAR (staging cleanup).
    - In-game chat panel on dashboard: reads <Player> messages from Docker
      logs (last 2h, 5s poll) and lets the admin send messages via /say.
      Input limited to 200 printable chars, no control characters.
    - Location bookmarks: name + (X,Y,Z) saved to /home/pi/mc-locations.json,
      shown as preset buttons in the Teleport modal. Add/remove from the modal.
      Cyrillic names allowed.
    - New /logs page: tail Docker logs with level filter (INFO/WARN/ERROR),
      search highlight, configurable tail (100-2000), optional 5s live mode.
    - New endpoints: /api/plugins/history dedup-aware, /api/chat,
      /api/chat/send, /api/locations, /api/locations/add, /api/locations/remove,
      /api/logs.
  v1.14.0 (2026-05-02)
    - Plugin update messaging now shows old size, new size, and signed delta
      (e.g. "ViaVersion.jar: 4.8 MB -> 5.1 MB (+304 KB)"). Also distinguishes
      "no change" from real updates and "new install" for fresh files.
    - New persistent update history in /home/pi/mc-plugin-history.json (last
      50 events). Surfaced on the /plugins page as "Recent updates" list at
      the bottom and via "Updated 2h ago" badges on individual plugin cards.
    - New endpoint: GET /api/plugins/history
    - Update All now produces one toast per plugin (sequential, 250ms apart)
      instead of one giant compressed summary, plus a final summary toast.
    - Toast duration extended from 6s -> 12s for plugin update notifications
      so longer messages with size deltas are readable.
  v1.13.2 (2026-05-02)
    - FIX: _respond() returned ok=True even for toast='error' responses,
      misleading AJAX clients into showing a success state for soft failures
      (e.g. "Bad filename"). Now ok=false when toast='error'.
    - Cleanup: removed dead JS code that updated the (no-longer-present)
      backup widget from the dashboard 5s poller. Removed unused
      __BACKUP_AGE_HOURS__ template substitution.
  v1.13.1 (2026-05-01)
    - FIX: Teleport/Nick modal didn't open — modal markup, CSS and JS were
      living in the dashboard template (HTML_TEMPLATE) but the buttons that
      trigger it are rendered by build_player_card() which is only used by
      the /players page (PLAYERS_TEMPLATE). Moved the modal + its JS into
      PLAYERS_TEMPLATE so the buttons can find their target. Cleaned up dead
      CSS in HTML_TEMPLATE that was no longer referenced.
  v1.13.0 (2026-05-01)
    - Backups widget moved off the dashboard onto a new dedicated /backups page
      (full archive list, sizes, deltas, age, status banner, world size summary)
    - Plugins page rebuilt: search box, sort (name/size/status), filter (all
      / no URL / has URL / missing JAR), per-plugin status badge, aggregate
      stats (totals on disk, with/without URL, missing JAR count)
    - Plugin update + update-all are AJAX with toasts and a "restart needed"
      banner that lets you trigger restart in one click after updates
  v1.12.0 (2026-05-01)
    - Teleport from player cards: "Teleport" button opens a modal with
      target-player or coords (X Y Z). Supports tilde-relative (~ ~10 ~).
      Coordinates are validated server-side via regex — no shell injection.
      Quick presets for spawn / build site / "Up 50".
    - Nickname management from player cards: "Nick" button opens the same
      modal (Nickname tab) and runs EssentialsX `/nick`. Empty input rejected;
      explicit "Reset nickname" button runs `/nick <name> off`.
    - Modal closes on backdrop click and Escape key.
  v1.11.0 (2026-05-01)
    - Auto-detect Java vs Bedrock via Mojang API (cached 1h per name);
      onboarding form has live "JAVA detected"/"BEDROCK detected" hint that
      appears as you type (350ms debounced)
    - Player session tracking: pair JOIN/LEAVE events to compute playtime,
      sessions, average and longest. Shown in Players page cards. Capped at
      12h per session to absorb crashes/restart-eaten LEAVE events.
    - Backup widget added under whitelist panel: count + latest size/date +
      world size, with bad/warn coloring if no backup in 30h or 48h
    - Per-player playtime chart on /charts page (bar chart, last N days,
      with dropdown of all known players ordered by total playtime)
    - Skin head icons (mc-heads.net) in: player cards, whitelist panel, online
      list, top players bar chart. Bedrock players get a generic Steve.
    - Toast notifications replace ?msg= query string redirect pattern. Old
      forms still work (server falls back to redirect when client doesn't send
      X-Requested-With: fetch). Existing ?msg= URLs are converted to toast on
      page load and stripped from the address bar.
    - Real-time dashboard updates: /api/status JSON poller, refreshed every 5s.
      No more meta-refresh full reload — only the relevant DOM nodes change.
      Onboarding state transitions still trigger a single full reload to
      re-render the form/banner section.
    - New endpoints: /api/status, /api/players, /api/playtime/<name>,
      /api/detect-platform
  v1.10.0 (2026-05-01)
    - SECURITY: HTML-escape every user-controlled field rendered into the page
      (event rows, player cards, IPs, reasons, msg banners, plugin metadata,
      whitelist names). Closes XSS vector via reasons/Bedrock player names.
    - Tame werkzeug log spam (silence per-request INFO; keep WARNING+ in file)
    - Onboarding banner has live client-side countdown (no full reload tick)
      and auto-refreshes every 15s while waiting so the join is caught fast
    - Onboarding now diagnoses *why* a connection failed (Mojang auth fail,
      version mismatch, generic disconnect) and shows the reason in the banner
      instead of silently waiting until timeout
    - Whitelist remove buttons use data-name + dataset.name (immune to
      apostrophes/quotes in player names — Bedrock allows them)
    - Numeric stats rendered via int() coercion (defense against non-int seeping
      into class names)
  v1.9.0 (2026-05-01)
    - RCON cache (10s TTL) for `list`, `tps`, `memory` and `docker inspect` —
      cuts dashboard render time noticeably (was 4 docker exec calls per load)
    - World size cached for 120s (no more os.walk on multi-GB world per render)
    - Atomic JSON writes everywhere (write-tmp + os.replace) — no more torn
      writes on crash mid-write for onboarding/plugin-urls/state files
    - CSRF protection on every state-changing POST endpoint via Flask sessions
      with a stable signed-cookie secret stored at /home/pi/.mc-web-secret
    - Replaced bare `except: pass` with `log.exception(...)` throughout —
      errors now appear in /home/pi/mc-access-web.log + stderr
    - Plugin update endpoints reject path-traversal filenames and non-http(s) URLs
    - Cache invalidation hooks: whitelist mutations clear `rcon:list` cache
  v1.8.0 (2026-05-01)
    - Added Bedrock onboarding workflow: temporarily disables whitelist, watches
      Docker logs for the new player, auto-runs `fwhitelist add` on detection,
      and re-enables whitelist (avoids manual SSH dance for new kids)
    - Players page now shows REJECTED count + last rejected time per player
    - Other Connections section sorted by rejected count (most aggressive first)
    - Suspicious-IP alert banner is now dismissible (X button) with 24h cookie;
      banner re-appears if a new IP starts attacking
    - Fixed whitelist remove: no longer runs both fwhitelist+whitelist commands
    - Various code-quality fixes (see review notes)
  v1.7.4 (2026-03-28)
    - Fixed nickname display for Geyser players (matches with and without dot prefix)
    - Added /plugins page with plugin list, versions, file sizes, update URLs
    - Added plugin update system with URL persistence (mc-plugin-urls.json)
    - Added Update / Update All buttons on plugins page
    - Added /players page with per-player statistics (joins, IPs, platform, first/last seen)
    - Players page separates whitelisted from other connections (orange styling)
    - Added Players and Plugins navigation across all pages
    - Fixed favicon, strip_ansi handles Minecraft color codes
    - Plugins parsed from Docker startup logs (handles 50000+ line logs)
    - Restart button visually separated from navigation
    - Theme toggle always rightmost button
  v1.7.3 (2026-03-25)
    - Removed hourly distribution chart, kept only daily activity (last 14 days)
    - Added EssentialsX nickname display: "PlayerName (Nickname)" in online list, top players, whitelist
    - Added EssentialsX nickname display next to player names (online list, whitelist, top players)
  v1.7.2 (2026-03-25)
    - Fixed online player count parsing (Paper changed format to "out of maximum")
    - Fixed player names extraction (now handles "default: player" format)
    - Fixed utcnow() deprecation warning
    - Whitelist panel now shows all players from whitelist.json
  v1.7.1 (2026-03-23)
    - Added daily activity chart (joins per day, last 14 days)
    - Activity panel shows daily chart only
  v1.7.0 (2026-03-23)
    - Added /charts page with Chart.js multi-metric graph
    - Metrics: CPU, RAM, MC heap, TPS, player count overlaid with different colors
    - Time range radio buttons: 1d, 2d, 5d, 7d, 15d, 30d, 60d, 90d, 180d
    - Charts button in header navigation
    - Requires mc-access-logger v1.2.0+ for metrics collection
  v1.6.3 (2026-03-23)
    - Added MC RAM (real used / allocated) to status bar from 'memory' RCON command
    - Added auto-refresh countdown timer showing seconds until next refresh
  v1.6.2 (2026-03-23)
    - Fixed whitelist to read directly from whitelist.json (detects BE/JE by dot prefix)
    - Added whitelist ON/OFF toggle buttons
    - Improved whitelist add feedback (shows server response)
    - Auto-strips dot from Bedrock names when adding
    - Note: Bedrock players must connect once before they can be whitelisted
  v1.6.1 (2026-03-23)
    - Fixed TPS parsing (was catching "1" from "1m" instead of "20.0")
    - Added BE/JE badges to whitelist entries
  v1.6.0 (2026-03-23)
    - Added whitelist management (add/remove players, Bedrock/Java toggle)
    - Added server restart button with confirmation
    - Added TPS indicator in status bar
    - Added world size in status bar
    - Added backup count and last backup size in status bar
  v1.5.0 (2026-03-23)
    - Dark/light theme toggle, mobile optimization, suspicious IP alerts
  v1.4.0 (2026-03-22)
    - Top Players, activity chart, colored rows, favicon, online player names
  v1.3.0 (2026-03-22)
    - Fixed ANSI codes, increased fonts, added IP filter
  v1.2.0 (2026-03-22)
    - Added system status bar
  v1.1.0 (2026-03-22)
    - Added HTTP Basic Auth, pagination, auto-refresh
  v1.0.0 (2026-03-22)
    - Initial release
"""

from flask import Flask, request, Response, redirect, url_for, session, abort
from markupsafe import escape as _escape
import json
import os
import re
import glob
import time
import hmac
import secrets
import logging
import functools
import subprocess
import psutil
from datetime import datetime, timedelta, timezone
from collections import Counter

def esc(value):
    """HTML-escape any value (None-safe). Returns plain str, not Markup."""
    if value is None:
        return ''
    return str(_escape(value))

# ----------------------------------------------------------------------------
# Logging — stderr always; file handler if writable. Avoid bare except pass.
# ----------------------------------------------------------------------------
LOG_OUTPUT_FILE = "/home/pi/mc-access-web.log"
_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.append(logging.FileHandler(LOG_OUTPUT_FILE))
except Exception as _e:
    # Filesystem may be RO or path missing; keep stderr only.
    print(f"[startup] could not open log file {LOG_OUTPUT_FILE}: {_e}")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=_log_handlers,
)
log = logging.getLogger('mc-web')
# werkzeug logs every HTTP request at INFO — too noisy for our log file.
# Keep WARNING+ only (so 4xx/5xx still appear) and let our own log calls
# carry the signal we care about.
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# ----------------------------------------------------------------------------
# Atomic JSON write — write-to-tmp + os.replace is atomic on POSIX.
# ----------------------------------------------------------------------------
def atomic_write_json(path, data, **dump_kwargs):
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        # Clean up tmp on failure
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise

# ----------------------------------------------------------------------------
# Tiny TTL cache — for expensive calls (RCON, world dir size).
# ----------------------------------------------------------------------------
_cache = {}

def cached(key, ttl_seconds, getter):
    now = time.monotonic()
    entry = _cache.get(key)
    if entry is not None:
        ts, val = entry
        if now - ts < ttl_seconds:
            return val
    val = getter()
    _cache[key] = (now, val)
    return val

def cache_invalidate(prefix=''):
    for k in list(_cache.keys()):
        if not prefix or k.startswith(prefix):
            _cache.pop(k, None)

app = Flask(__name__)
LOG_FILE = "/home/pi/mc-access-log.json"
METRICS_FILE = "/home/pi/mc-metrics.json"
PLUGIN_URLS_FILE = "/home/pi/mc-plugin-urls.json"
ONBOARDING_FILE = "/home/pi/mc-onboarding-state.json"
BACKUP_DIR = "/opt/minecraft/backups"
WORLD_DIR = "/opt/minecraft/data"

VERSION = "1.16.1"
ONBOARDING_DEFAULT_MINUTES = 5
ONBOARDING_MAX_MINUTES = 30

USERNAME = "linuxxp"
PASSWORD = "mechopuhemeche"

PER_PAGE = 50
SUSPICIOUS_THRESHOLD = 10

FAVICON = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAANklEQVR4nGOQk9MjCTGQqcHvzGKCiBoaMDVjyqJrgJNYudg1YBpMWAOaq4aSBtpHHAkaaJhaARWqDkSJgr4WAAAAAElFTkSuQmCC"

def strip_ansi(text):
    # Remove ANSI escape codes
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # Remove Minecraft §x color/format codes
    text = re.sub(r'§[0-9a-fk-orx]', '', text)
    return text

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response('Login required', 401, {'WWW-Authenticate': 'Basic realm="Minecraft Access Log"'})

def requires_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ----------------------------------------------------------------------------
# CSRF — Flask sessions (signed cookies) with stable secret_key.
# Tokens are random per session; required on all state-changing POSTs.
# ----------------------------------------------------------------------------
SECRET_KEY_FILE = "/home/pi/.mc-web-secret"

def _load_or_create_secret():
    if os.path.exists(SECRET_KEY_FILE):
        try:
            with open(SECRET_KEY_FILE, 'rb') as f:
                data = f.read()
            if len(data) >= 32:
                return data
        except Exception:
            log.exception("could not read secret key file")
    secret = secrets.token_bytes(32)
    try:
        with open(SECRET_KEY_FILE, 'wb') as f:
            f.write(secret)
        os.chmod(SECRET_KEY_FILE, 0o600)
    except Exception:
        log.exception("could not write secret key file %s", SECRET_KEY_FILE)
    return secret

app.secret_key = _load_or_create_secret()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

def get_csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']

def requires_csrf(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        sent = request.form.get('csrf_token', '') or request.headers.get('X-CSRF-Token', '')
        expected = session.get('csrf', '')
        if not sent or not expected or not hmac.compare_digest(sent, expected):
            log.warning("CSRF check failed: path=%s ip=%s", request.path, request.remote_addr)
            return Response('CSRF check failed - refresh the page and try again', 403)
        return f(*args, **kwargs)
    return decorated

def rcon(cmd):
    try:
        result = subprocess.run(['docker', 'exec', 'minecraft', 'rcon-cli', cmd], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return strip_ansi(result.stdout.strip())
        log.warning("rcon non-zero: cmd=%r rc=%d stderr=%s", cmd, result.returncode, result.stderr.strip()[:200])
        return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        log.warning("rcon timeout: cmd=%r", cmd)
        return "Error: timeout"
    except Exception as e:
        log.exception("rcon exception: cmd=%r", cmd)
        return f"Error: {e}"

def rcon_cached(cmd, ttl_seconds=10):
    """Cached RCON for read-only commands. Mutations should use rcon() directly."""
    return cached(f'rcon:{cmd}', ttl_seconds, lambda: rcon(cmd))

def get_dir_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def format_size(size_bytes):
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"

def get_nicknames():
    """Read EssentialsX userdata to build name -> nickname mapping"""
    nicknames = {}
    userdata_dir = os.path.join(WORLD_DIR, 'plugins', 'Essentials', 'userdata')
    if not os.path.isdir(userdata_dir):
        return nicknames
    try:
        for filename in os.listdir(userdata_dir):
            if not filename.endswith('.yml'):
                continue
            filepath = os.path.join(userdata_dir, filename)
            name = None
            nick = None
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('last-account-name:'):
                            name = line.split(':', 1)[1].strip().strip('"').strip("'")
                        elif line.startswith('nickname:'):
                            nick = line.split(':', 1)[1].strip().strip('"').strip("'")
                            # Remove EssentialsX formatting codes (§x, &x, etc)
                            nick = re.sub(r'[§&][0-9a-fk-or]', '', nick)
                if name and nick and nick != name:
                    nicknames[name] = nick
            except Exception:
                # Per-file failure is non-fatal — bad YAML, perms, etc.
                log.debug("nickname parse skipped: %s", filename, exc_info=True)
                continue
    except Exception:
        log.exception("listing essentials userdata failed")
    return nicknames

def format_player_name(name, nicknames):
    """Format player name with nickname if available"""
    nick = nicknames.get(name, '')
    # Try with dot prefix (Geyser logs without dot, EssentialsX stores with dot)
    if not nick and not name.startswith('.'):
        nick = nicknames.get(f'.{name}', '')
    # Try without dot prefix
    if not nick and name.startswith('.'):
        nick = nicknames.get(name[1:], '')
    if nick:
        return f"{name} ({nick})"
    return name

# ----------------------------------------------------------------------------
# Skins — mc-heads.net renders Java skin heads from a username. Bedrock players
# (with dot prefix) return a default Steve avatar — visually consistent.
# ----------------------------------------------------------------------------
def skin_url(name, size=24):
    if not name:
        return ''
    # Strip leading dot (Bedrock prefix from Floodgate)
    clean = name.lstrip('.')
    # mc-heads.net is a free public service that browser-caches via standard headers
    return f'https://mc-heads.net/avatar/{esc(clean)}/{int(size)}.png'

# ----------------------------------------------------------------------------
# Mojang API — used for Java/Bedrock auto-detection. 60s cached per name.
# Returns ('java', uuid) | ('bedrock', None) | ('unknown', None)
# ----------------------------------------------------------------------------
def detect_platform(name):
    """
    Probe Mojang API to see if `name` is a real Java account.
    Cached for 1 hour per name. Falls back to 'unknown' on network failure.
    """
    if not name:
        return ('unknown', None)
    clean = name.lstrip('.').strip()
    if not clean:
        return ('unknown', None)
    # Java usernames: 3-16 chars, alphanumeric + underscore.
    # Bedrock gamertags often violate this (spaces, longer, special chars).
    java_username_re = re.compile(r'^[A-Za-z0-9_]{3,16}$')
    if not java_username_re.match(clean):
        # Definitely NOT a valid Java name — must be Bedrock
        return ('bedrock', None)

    def _probe():
        try:
            import urllib.request
            req = urllib.request.Request(
                f'https://api.mojang.com/users/profiles/minecraft/{clean}',
                headers={'User-Agent': 'mc-access-web/1.11'},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    return ('java', data.get('id', ''))
                if resp.status == 204 or resp.status == 404:
                    return ('bedrock', None)
                return ('unknown', None)
        except Exception:
            log.debug("Mojang lookup failed for %r", clean, exc_info=True)
            return ('unknown', None)

    return cached(f'mojang:{clean}', 3600, _probe)

# ----------------------------------------------------------------------------
# Player sessions — pair JOIN/LEAVE events to compute durations.
# ----------------------------------------------------------------------------
SESSION_MAX_HOURS = 12  # cap unmatched sessions at 12h (server probably restarted)

def compute_player_sessions(events):
    """
    Walk events chronologically and pair JOIN with the next LEAVE per player.
    Returns dict: player_name -> list of (start_iso, end_iso, duration_seconds)
    Unmatched JOINs are capped at SESSION_MAX_HOURS to avoid skewing stats.
    Player names are normalized (Bedrock dot stripped where it's known to differ).
    """
    sessions = {}
    open_sessions = {}  # player -> start_iso

    sorted_events = sorted(events, key=lambda e: e.get('timestamp', ''))

    for e in sorted_events:
        etype = e.get('type', '')
        ts = e.get('timestamp', '')
        if not ts:
            continue
        player = e.get('player', '')
        if not player:
            continue

        if etype == 'JOIN':
            # If there was already an open session for this player, close it
            # synthetically (server probably restarted between).
            if player in open_sessions:
                _close_open_session(sessions, player, open_sessions, ts)
            open_sessions[player] = ts
        elif etype == 'LEAVE':
            if player in open_sessions:
                start = open_sessions.pop(player)
                duration = _diff_seconds(start, ts)
                if duration is not None and 0 < duration <= SESSION_MAX_HOURS * 3600:
                    sessions.setdefault(player, []).append((start, ts, duration))

    # Any still-open sessions get capped at "now" or SESSION_MAX_HOURS, whichever smaller.
    now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    for player, start in open_sessions.items():
        _close_open_session(sessions, player, {player: start}, now_iso, ongoing=True)

    return sessions

def _close_open_session(sessions, player, open_sessions, end_iso, ongoing=False):
    start = open_sessions.get(player, '')
    if not start:
        return
    duration = _diff_seconds(start, end_iso)
    if duration is None:
        return
    # Cap unmatched / very long sessions
    duration = max(0, min(duration, SESSION_MAX_HOURS * 3600))
    if duration > 0:
        sessions.setdefault(player, []).append((start, end_iso, duration))

def _diff_seconds(start_iso, end_iso):
    try:
        s = datetime.fromisoformat(start_iso[:19])
        e = datetime.fromisoformat(end_iso[:19])
        return int((e - s).total_seconds())
    except Exception:
        return None

def merge_sessions_for_bedrock(sessions):
    """
    Bedrock players appear under both '.Name' (JOIN events) and 'Name' (Geyser line).
    Normalize: merge under '.Name' if both exist.
    """
    merged = {}
    keys = list(sessions.keys())
    keyset = set(keys)
    for k in keys:
        if k.startswith('.'):
            target = k
        else:
            dot_v = f'.{k}'
            target = dot_v if dot_v in keyset else k
        merged.setdefault(target, []).extend(sessions.get(k, []))
    return merged

def format_duration(seconds):
    """Human-readable duration: '2h 15m', '45m', '30s'"""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h {m}m" if m else f"{h}h"

def daily_playtime(sessions_for_player, days=14):
    """
    Bucket sessions into per-day totals (seconds).
    Returns list of (date_str, seconds) for the last N days, oldest first.
    """
    today = datetime.now().date()
    buckets = {today - timedelta(days=i): 0 for i in range(days)}
    for start_iso, _end_iso, duration in sessions_for_player:
        try:
            d = datetime.fromisoformat(start_iso[:19]).date()
        except Exception:
            continue
        if d in buckets:
            buckets[d] += duration
    return sorted(buckets.items(), key=lambda x: x[0])


def get_system_status():
    status = {}
    boot_time = datetime.fromtimestamp(int(psutil.boot_time()))
    delta = datetime.now() - boot_time
    days, hours, minutes = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    status['vps_uptime'] = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"

    mem = psutil.virtual_memory()
    status['ram_used'] = f"{mem.used / (1024**3):.1f}"
    status['ram_total'] = f"{mem.total / (1024**3):.1f}"
    status['ram_percent'] = f"{mem.percent}"

    swap = psutil.swap_memory()
    status['swap_used'] = f"{swap.used / (1024**3):.1f}"
    status['swap_total'] = f"{swap.total / (1024**3):.1f}"
    status['swap_percent'] = f"{swap.percent}"

    disk = psutil.disk_usage('/')
    status['disk_used'] = f"{disk.used / (1024**3):.1f}"
    status['disk_total'] = f"{disk.total / (1024**3):.1f}"
    status['disk_percent'] = f"{disk.percent}"

    status['cpu_percent'] = f"{psutil.cpu_percent(interval=0)}"
    status['cpu_cores'] = str(psutil.cpu_count())

    # MC container uptime — cache 30s; container start time only changes on restart
    def _docker_started_at():
        try:
            r = subprocess.run(['docker', 'inspect', '--format', '{{.State.StartedAt}}', 'minecraft'],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            log.exception("docker inspect failed")
        return ''
    try:
        started_str = cached('docker_started_at', 30, _docker_started_at)
        if started_str:
            started_dt = datetime.fromisoformat(started_str[:19])
            mc_delta = datetime.now(timezone.utc).replace(tzinfo=None) - started_dt
            mc_days, mc_hours, mc_minutes = mc_delta.days, mc_delta.seconds // 3600, (mc_delta.seconds % 3600) // 60
            status['mc_uptime'] = f"{mc_days}d {mc_hours}h {mc_minutes}m" if mc_days > 0 else f"{mc_hours}h {mc_minutes}m"
            status['mc_status'] = 'online'
        else:
            status['mc_uptime'] = 'N/A'
            status['mc_status'] = 'offline'
    except Exception:
        log.exception("mc uptime parse failed")
        status['mc_uptime'] = 'N/A'
        status['mc_status'] = 'offline'

    # Online players — cache 10s; clears immediately on whitelist mutations.
    try:
        full_output = rcon_cached('list', ttl_seconds=10)
        if full_output and not full_output.startswith('Error:'):
            lines = full_output.split('\n')
            first_line = lines[0] if lines else ''
            count_match = re.search(r'There are (\d+)', first_line)
            max_match = re.search(r'(?:maximum|max of)\s+(\d+)', first_line)
            if count_match:
                status['players_online'] = count_match.group(1)
                status['players_max'] = max_match.group(1) if max_match else '20'
                player_names = []
                if ':' in first_line:
                    names_part = first_line.split(':', 1)[1].strip()
                    if names_part and 'player' not in names_part.lower():
                        player_names = [n.strip() for n in names_part.split(',') if n.strip()]
                for extra_line in lines[1:]:
                    extra_line = extra_line.strip()
                    if extra_line:
                        if ':' in extra_line:
                            names_part = extra_line.split(':', 1)[1].strip()
                        else:
                            names_part = extra_line
                        if names_part:
                            player_names.extend([n.strip() for n in names_part.split(',') if n.strip()])
                status['player_names'] = player_names
            else:
                status['players_online'] = '0'
                status['players_max'] = '20'
                status['player_names'] = []
        else:
            status['players_online'] = '?'
            status['players_max'] = '?'
            status['player_names'] = []
    except Exception:
        log.exception("online players parse failed")
        status['players_online'] = '?'
        status['players_max'] = '?'
        status['player_names'] = []

    # TPS — cache 10s
    try:
        line = rcon_cached('tps', ttl_seconds=10)
        if line and not line.startswith('Error:') and ':' in line:
            tps_part = line.split(':', 1)[1]
            tps_match = re.findall(r'\*?(\d+\.?\d*)', tps_part)
        else:
            tps_match = []
        if tps_match:
            status['tps'] = tps_match[0]
            try:
                tps_val = float(tps_match[0].replace('*', ''))
                if tps_val >= 19: status['tps_class'] = 'good'
                elif tps_val >= 15: status['tps_class'] = 'warn'
                else: status['tps_class'] = 'bad'
            except ValueError:
                status['tps_class'] = ''
        else:
            status['tps'] = '?'
            status['tps_class'] = ''
    except Exception:
        log.exception("tps parse failed")
        status['tps'] = '?'
        status['tps_class'] = ''

    # World size — walking the world directory is expensive on multi-GB worlds,
    # so we cache for 2 minutes. World size changes slowly anyway.
    try:
        def _world_size():
            total = 0
            for w in ('world', 'world_nether', 'world_the_end'):
                wp = os.path.join(WORLD_DIR, w)
                if os.path.exists(wp):
                    total += get_dir_size(wp)
            return total
        world_size = cached('world_size', 120, _world_size)
        status['world_size'] = format_size(world_size)
    except Exception:
        log.exception("world size compute failed")
        status['world_size'] = '?'

    # Backups
    try:
        backups = sorted(glob.glob(os.path.join(BACKUP_DIR, 'world-*.tar.gz')))
        status['backup_count'] = str(len(backups))
        if backups:
            last = backups[-1]
            status['backup_last_size'] = format_size(os.path.getsize(last))
            status['backup_last_date'] = datetime.fromtimestamp(os.path.getmtime(last)).strftime('%m-%d %H:%M')
        else:
            status['backup_last_size'] = 'N/A'
            status['backup_last_date'] = 'N/A'
    except Exception:
        log.exception("backup listing failed")
        status['backup_count'] = '?'
        status['backup_last_size'] = '?'
        status['backup_last_date'] = '?'

    # MC memory (real usage from Java heap) — cache 10s
    try:
        line = rcon_cached('memory', ttl_seconds=10)
        if line and not line.startswith('Error:'):
            alloc_match = re.search(r'Allocated memory:\s*([\d,]+)\s*MB', line)
            free_match = re.search(r'Free memory:\s*([\d,]+)\s*MB', line)
            if alloc_match and free_match:
                allocated = int(alloc_match.group(1).replace(',', ''))
                free = int(free_match.group(1).replace(',', ''))
                used = allocated - free
                status['mc_ram_used'] = str(used)
                status['mc_ram_alloc'] = str(allocated)
                pct = (used / allocated * 100) if allocated > 0 else 0
                status['mc_ram_percent'] = f"{pct:.0f}"
            else:
                status['mc_ram_used'] = '?'
                status['mc_ram_alloc'] = '?'
                status['mc_ram_percent'] = '0'
        else:
            status['mc_ram_used'] = '?'
            status['mc_ram_alloc'] = '?'
            status['mc_ram_percent'] = '0'
    except Exception:
        log.exception("mc memory parse failed")
        status['mc_ram_used'] = '?'
        status['mc_ram_alloc'] = '?'
        status['mc_ram_percent'] = '0'

    return status

def get_whitelist():
    players = []
    wl_path = os.path.join(WORLD_DIR, 'whitelist.json')
    try:
        if os.path.exists(wl_path):
            with open(wl_path, 'r') as f:
                wl_data = json.load(f)
                for entry in wl_data:
                    name = entry.get('name', '')
                    if name:
                        ptype = 'bedrock' if name.startswith('.') else 'java'
                        players.append((ptype, name))
    except Exception:
        log.exception("whitelist.json read failed")
    return players

# --- Onboarding (auto-whitelist new Bedrock players) ---

def get_onboarding_state():
    """Return onboarding state dict or None if no active onboarding."""
    if not os.path.exists(ONBOARDING_FILE):
        return None
    try:
        with open(ONBOARDING_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        log.exception("onboarding state read failed; clearing")
        clear_onboarding_state()
        return None

def save_onboarding_state(state):
    try:
        atomic_write_json(ONBOARDING_FILE, state, indent=2)
    except Exception:
        log.exception("onboarding state write failed")

def clear_onboarding_state():
    if os.path.exists(ONBOARDING_FILE):
        try:
            os.remove(ONBOARDING_FILE)
        except OSError:
            log.exception("could not remove onboarding state file")

def player_connection_outcome(player_name, since_minutes):
    """
    Inspect docker logs for the player within the last N minutes and classify:
      ('joined', None)            — successful login (whitelist add is safe)
      ('rejected', reason_str)    — connected but was kicked (auth fail / version mismatch)
      ('none', None)              — no trace of this player at all
    Looks for both Geyser connect lines and Java login lines.
    """
    try:
        since_arg = f'{max(1, since_minutes + 1)}m'
        result = subprocess.run(
            ['docker', 'logs', '--since', since_arg, 'minecraft'],
            capture_output=True, text=True, timeout=10
        )
        log_text = strip_ansi(result.stdout + result.stderr)
        clean = re.escape(player_name.lstrip('.'))

        # Successful Bedrock connection (Geyser handles auth before the player reaches Paper)
        if re.search(rf'\[Geyser-Spigot\] Player connected with username {clean}\b', log_text, re.IGNORECASE):
            return ('joined', None)
        # Successful Java login (printed only AFTER Mojang auth succeeded)
        if re.search(rf'\b\.?{clean}\[/\d+\.\d+\.\d+\.\d+:\d+\] logged in', log_text, re.IGNORECASE):
            return ('joined', None)

        # Failed connection — pick the most informative line we can find
        m = re.search(
            rf'\.?{clean} \(/\d+\.\d+\.\d+\.\d+:\d+\) lost connection: (.+)',
            log_text, re.IGNORECASE,
        )
        if m:
            return ('rejected', m.group(1).strip())
        # Mojang auth failure is logged without the IP suffix
        if re.search(rf'\bFailed to verify username!.*?\b{clean}\b', log_text, re.IGNORECASE):
            return ('rejected', 'Failed to verify username (Mojang auth)')
        if re.search(rf'\b{clean}\b.*?\blost connection: Disconnected\b', log_text, re.IGNORECASE):
            return ('rejected', 'Disconnected (client closed before login completed)')

        return ('none', None)
    except subprocess.TimeoutExpired:
        log.warning("docker logs timeout while checking onboarding for %r", player_name)
        return ('none', None)
    except Exception:
        log.exception("docker logs check failed for %r", player_name)
        return ('none', None)

# Backward-compat shim for callers that just want a boolean
def player_connected_recently(player_name, since_minutes):
    outcome, _ = player_connection_outcome(player_name, since_minutes)
    return outcome == 'joined'

def process_onboarding():
    """
    Tick the onboarding state machine. Called on each dashboard load.
    - Player joined successfully: auto-whitelist + re-enable whitelist
    - Player connected but got rejected: surface the reason and keep watching
      (a brief Mojang glitch shouldn't kill the whole onboarding)
    - Timed out: re-enable whitelist
    Returns the (possibly final) state dict, or None if no onboarding active.
    """
    state = get_onboarding_state()
    if not state:
        return None

    name = state.get('name', '').strip()
    platform = state.get('platform', 'bedrock')
    duration = int(state.get('duration_minutes', ONBOARDING_DEFAULT_MINUTES))

    try:
        started = datetime.fromisoformat(state['started_at'])
    except Exception:
        log.warning("onboarding state has invalid started_at: %r", state.get('started_at'))
        clear_onboarding_state()
        return None

    now = datetime.now()
    elapsed_min = (now - started).total_seconds() / 60.0
    seconds_left = max(0, int(duration * 60 - (now - started).total_seconds()))

    outcome, reason = player_connection_outcome(name, since_minutes=int(elapsed_min) + 1) if name else ('none', None)

    if outcome == 'joined':
        clean_name = name.lstrip('.')
        if platform == 'bedrock':
            wl_result = rcon(f'fwhitelist add {clean_name}')
        else:
            wl_result = rcon(f'whitelist add {clean_name}')
        rcon('whitelist on')
        cache_invalidate('rcon:list')
        log.info("onboarding completed: name=%r platform=%s result=%r", name, platform, wl_result)
        clear_onboarding_state()
        return {**state, 'status': 'completed', 'result': wl_result or 'OK'}

    if seconds_left <= 0:
        rcon('whitelist on')
        log.info("onboarding expired: name=%r last_outcome=%s reason=%r", name, outcome, reason)
        clear_onboarding_state()
        return {**state, 'status': 'expired', 'last_outcome': outcome, 'reject_reason': reason}

    # Still active — but tell the user if we noticed a failed attempt
    return {
        **state, 'status': 'active', 'seconds_left': seconds_left,
        'last_outcome': outcome, 'reject_reason': reason,
    }

def get_top_players(events, limit=10):
    joins = [e.get('player', '') for e in events if e.get('type') == 'JOIN' and e.get('player')]
    return Counter(joins).most_common(limit)

def get_hourly_activity(events):
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    hours = [0] * 24
    for e in events:
        if e.get('type') != 'JOIN': continue
        ts = e.get('timestamp', '')
        time_str = e.get('time', '')
        try:
            if 'T' in ts:
                dt = datetime.fromisoformat(ts[:19])
                if dt >= seven_days_ago: hours[dt.hour] += 1
            elif time_str:
                hours[int(time_str.split(':')[0])] += 1
        except (ValueError, IndexError):
            continue
    return hours

def get_daily_activity(events):
    now = datetime.now()
    days = {}
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        days[day] = 0
    for e in events:
        if e.get('type') != 'JOIN': continue
        ts = e.get('timestamp', '')
        try:
            if 'T' in ts:
                day = ts[:10]
                if day in days:
                    days[day] += 1
        except (ValueError, IndexError):
            continue
    return days

def get_suspicious_ips(events):
    rejected = [e for e in events if e.get('type') == 'REJECTED' and e.get('ip')]
    ip_counts = Counter(e['ip'] for e in rejected)
    return {ip: count for ip, count in ip_counts.items() if count >= SUSPICIOUS_THRESHOLD}

def build_activity_chart(hours):
    max_val = max(hours) if max(hours) > 0 else 1
    bars = []
    for h in range(24):
        pct = int((hours[h] / max_val) * 100) if max_val > 0 else 0
        count = hours[h]
        bars.append(f"""<div class="chart-col" title="{h:02d}:00 - {count} joins">
            <div class="chart-bar" style="height:{pct}%"><span class="chart-val">{count if count > 0 else ''}</span></div>
            <div class="chart-label">{h}</div>
        </div>""")
    return '\n'.join(bars)

def build_daily_chart(days):
    values = list(days.values())
    max_val = max(values) if values and max(values) > 0 else 1
    bars = []
    for day, count in days.items():
        pct = int((count / max_val) * 100) if max_val > 0 else 0
        short = day[5:]  # "03-22"
        bars.append(f"""<div class="chart-col" title="{day} - {count} joins">
            <div class="chart-bar daily" style="height:{pct}%"><span class="chart-val">{count if count > 0 else ''}</span></div>
            <div class="chart-label">{short}</div>
        </div>""")
    return '\n'.join(bars)

def build_top_players(top, nicknames=None):
    if not top: return '<div class="empty">No data yet</div>'
    if nicknames is None: nicknames = {}
    max_val = top[0][1]
    rows = []
    medals = ['&#x1F947;', '&#x1F948;', '&#x1F949;']
    for i, (player, count) in enumerate(top):
        pct = int((count / max_val) * 100)
        medal = medals[i] if i < 3 else f'#{i+1}'
        display = format_player_name(player, nicknames)
        skin = skin_url(player, 20)
        rows.append(f"""<div class="top-row">
            <span class="top-rank">{medal}</span>
            <img class="skin-head-sm" src="{skin}" alt="" loading="lazy" onerror="this.style.display='none'">
            <span class="top-name">{esc(display)}</span>
            <div class="top-bar-bg"><div class="top-bar-fill" style="width:{int(pct)}%"></div></div>
            <span class="top-count">{int(count)}</span>
        </div>""")
    return '\n'.join(rows)

def build_alerts(suspicious_ips):
    if not suspicious_ips: return ''
    items = []
    for ip, count in sorted(suspicious_ips.items(), key=lambda x: -x[1]):
        items.append(f'<div class="alert-item">&#x26A0; IP <strong>{esc(ip)}</strong> &mdash; {int(count)} rejected attempts</div>')
    # Signature ties dismissal to the SET of flagged IPs (not counts).
    # If a new IP is flagged later, the signature changes and the banner re-appears.
    import hashlib
    sig = hashlib.md5(':'.join(sorted(suspicious_ips.keys())).encode()).hexdigest()[:10]
    return (
        f'<div class="alert-box" id="alertBox" data-sig="{sig}">'
        f'<button class="alert-close" onclick="dismissAlert()" title="Hide for 24h or until new IP appears">&#x2715;</button>'
        f'{"".join(items)}'
        f'</div>'
    )

def build_whitelist_panel(wl_players, nicknames=None):
    if nicknames is None: nicknames = {}
    rows = ''
    for ptype, name in sorted(wl_players, key=lambda x: x[1]):
        badge = '<span style="color:var(--blue);font-size:0.75em;">BE</span>' if ptype == 'bedrock' else '<span style="color:var(--accent);font-size:0.75em;">JE</span>'
        display = format_player_name(name, nicknames)
        name_attr = esc(name)
        skin = skin_url(name, 20)
        rows += f"""<div class="wl-row">
            <span class="wl-name">
                <img class="skin-head-sm" src="{skin}" alt="" loading="lazy" onerror="this.style.display='none'">
                {badge} {esc(display)}
            </span>
            <button class="wl-remove" data-name="{name_attr}" onclick="removePlayer(this.dataset.name)" title="Remove">&#x2715;</button>
        </div>"""
    if not rows:
        rows = '<div class="empty">No whitelisted players</div>'
    return rows

def percent_class(val_str):
    try:
        val = float(val_str)
        if val >= 90: return 'bad'
        elif val >= 70: return 'warn'
        return 'good'
    except ValueError:
        return ''

def load_events():
    if not os.path.exists(LOG_FILE): return []
    try:
        with open(LOG_FILE, 'r') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        log.warning("events file unreadable or corrupt: %s", LOG_FILE)
        return []

# --- API Endpoints ---

def _wants_json():
    """True if the client wants JSON back (used by fetch-based UI)."""
    return (
        request.headers.get('X-Requested-With') == 'fetch'
        or 'application/json' in (request.headers.get('Accept', ''))
    )

def _respond(message, redirect_to='/', toast='info'):
    """Either JSON (for fetch) or HTML redirect (for plain forms).

    Sets ok=False when toast='error' so AJAX clients can tell apart success
    from a soft failure (e.g. validation error returned with HTTP 200).
    """
    is_ok = toast != 'error'
    if _wants_json():
        return {'ok': is_ok, 'message': message, 'toast': toast}, 200
    from urllib.parse import quote_plus
    return redirect(f'{redirect_to}?msg={quote_plus(message)}')

@app.route('/api/whitelist/add', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_add():
    name = request.form.get('name', '').strip()
    ptype = request.form.get('type', '').strip().lower()
    if not name:
        return _respond('Empty name', toast='error')
    clean_name = name.lstrip('.')

    # Auto-detect platform if not explicitly given (or set to 'auto')
    if ptype not in ('java', 'bedrock'):
        detected, _uuid = detect_platform(clean_name)
        if detected == 'unknown':
            # Ambiguous — default to Java (common case for typed names).
            ptype = 'java'
            log.info("auto-detect inconclusive for %r, defaulting to java", clean_name)
        else:
            ptype = detected
            log.info("auto-detected %r as %s", clean_name, ptype)

    if ptype == 'bedrock':
        result = rcon(f'fwhitelist add {clean_name}')
        if not result:
            result = 'Sent (Bedrock player must have connected once before)'
    else:
        result = rcon(f'whitelist add {clean_name}')
    cache_invalidate('rcon:list')
    log.info("whitelist add: name=%r type=%s result=%r", clean_name, ptype, result)
    msg = f'{ptype.upper()}: {clean_name} - {result}'
    toast = 'error' if result.startswith('Error') else 'success'
    return _respond(msg, toast=toast)

@app.route('/api/whitelist/remove', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_remove():
    name = request.form.get('name', '').strip()
    if not name:
        return _respond('Empty name', toast='error')
    if name.startswith('.'):
        result = rcon(f'fwhitelist remove {name[1:]}')
    else:
        result = rcon(f'whitelist remove {name}')
    cache_invalidate('rcon:list')
    log.info("whitelist remove: name=%r result=%r", name, result)
    return _respond(f'Removed {name} - {result}', toast='success')

@app.route('/api/whitelist/toggle', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_toggle():
    state = request.form.get('state', 'on')
    result = rcon(f'whitelist {state}')
    log.info("whitelist toggle: state=%s result=%r", state, result)
    msg = 'Whitelist ON' if state == 'on' else 'Whitelist OFF - anyone can join!'
    return _respond(msg, toast='warning' if state == 'off' else 'success')

@app.route('/api/whitelist/onboard', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_onboard():
    """
    Start onboarding for a new player.
    Auto-detects platform from Mojang API if not specified.
    """
    name = request.form.get('name', '').strip().lstrip('.')
    platform = request.form.get('platform', '').strip().lower()
    try:
        duration = int(request.form.get('duration', ONBOARDING_DEFAULT_MINUTES))
    except ValueError:
        duration = ONBOARDING_DEFAULT_MINUTES
    duration = max(1, min(duration, ONBOARDING_MAX_MINUTES))

    if not name:
        return _respond('Empty name', toast='error')

    # Auto-detect platform unless explicitly forced
    if platform not in ('java', 'bedrock'):
        detected, _uuid = detect_platform(name)
        platform = detected if detected != 'unknown' else 'bedrock'  # Bedrock is the safer default for kids
        log.info("onboarding auto-detect: %r -> %s", name, platform)

    existing = get_onboarding_state()
    if existing:
        return _respond(f'Onboarding already active for {existing.get("name","?")}', toast='warning')

    rcon('whitelist off')
    save_onboarding_state({
        'name': name,
        'platform': platform,
        'duration_minutes': duration,
        'started_at': datetime.now().replace(microsecond=0).isoformat(),
    })
    log.info("onboarding started: name=%r platform=%s duration=%d", name, platform, duration)
    return _respond(f'Onboarding {name} ({platform.upper()}) - whitelist OFF for {duration} min', toast='info')

@app.route('/api/whitelist/onboard/cancel', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_onboard_cancel():
    rcon('whitelist on')
    clear_onboarding_state()
    log.info("onboarding cancelled")
    return _respond('Onboarding cancelled - whitelist ON', toast='info')

@app.route('/api/restart', methods=['POST'])
@requires_auth
@requires_csrf
def api_restart():
    try:
        subprocess.Popen(['docker', 'compose', '-f', '/opt/minecraft/docker-compose.yml', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cache_invalidate()
        log.info("server restart triggered")
        return _respond('Server restarting...', toast='warning')
    except Exception as e:
        log.exception("restart trigger failed")
        return _respond(f'Error: {e}', toast='error')

# ----------------------------------------------------------------------------
# Teleport — calls /tp via RCON. Coordinates can be:
#   - integers/decimals: "100 64 -200"
#   - tilde-relative: "~ ~ ~10"
#   - mix: "~5 80 ~"
#   - target player name: "OtherPlayer" (teleport to that player)
# We never accept anything that isn't a name or a coord triple — no shell injection.
# ----------------------------------------------------------------------------

# Coord token: optional ~, optional - sign, digits with optional decimal point
COORD_TOKEN_RE = re.compile(r'^~?-?\d+(?:\.\d+)?$|^~$')
# Java player name (also matches the bare alphanumeric form of Bedrock names typed
# without dot — RCON adds the dot back automatically when needed via Floodgate)
PLAYER_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,32}$')

def _validate_coords(s):
    """Parse '100 64 -200' or '~ ~ ~10' into a normalized 3-token string, or None."""
    parts = s.strip().split()
    if len(parts) != 3:
        return None
    for p in parts:
        if not COORD_TOKEN_RE.match(p):
            return None
    return ' '.join(parts)

@app.route('/api/teleport', methods=['POST'])
@requires_auth
@requires_csrf
def api_teleport():
    name = request.form.get('name', '').strip()
    target = request.form.get('target', '').strip()
    coords = request.form.get('coords', '').strip()

    # Strip any leading dot the user typed — RCON wants dotted form for Bedrock
    # but Floodgate also accepts the dotless form via partial match. We pass the
    # raw whitelist name (with or without dot) since that's what the user clicked.
    if not name or not PLAYER_NAME_RE.match(name.lstrip('.')):
        return _respond('Bad player name', toast='error')

    # Either target (another player) OR coords, not both
    if target and coords:
        return _respond('Specify either target player OR coordinates, not both', toast='error')

    if target:
        if not PLAYER_NAME_RE.match(target.lstrip('.')):
            return _respond('Bad target name', toast='error')
        cmd = f'tp {name} {target}'
    elif coords:
        normalized = _validate_coords(coords)
        if not normalized:
            return _respond('Coordinates must be 3 numbers (or ~ for relative)', toast='error')
        cmd = f'tp {name} {normalized}'
    else:
        return _respond('Empty target and coordinates', toast='error')

    result = rcon(cmd)
    log.info("teleport: cmd=%r result=%r", cmd, result)
    if result.startswith('Error') or 'No entity was found' in (result or '') or 'Incorrect argument' in (result or ''):
        return _respond(f'Teleport failed: {result}', toast='error')
    return _respond(f'Teleported {name}: {result or "OK"}', toast='success')

# ----------------------------------------------------------------------------
# Nicknames — uses EssentialsX's `/nick` command, which sets a custom display
# name for the player. The change is persisted in EssentialsX userdata.
# Reset is achieved with `/nick <name> off`.
# ----------------------------------------------------------------------------

# Allow letters, digits, spaces and a few common symbols. Stays tight enough
# that no shell metacharacter gets through.
NICK_RE = re.compile(r'^[A-Za-z0-9_\- ]{1,24}$')

@app.route('/api/nick', methods=['POST'])
@requires_auth
@requires_csrf
def api_nick():
    name = request.form.get('name', '').strip()
    nick = request.form.get('nick', '').strip()
    reset = request.form.get('reset', '') in ('1', 'true', 'on', 'yes')

    if not name or not PLAYER_NAME_RE.match(name.lstrip('.')):
        return _respond('Bad player name', toast='error')

    if reset or nick == '':
        cmd = f'nick {name} off'
        action = 'cleared nickname'
    else:
        if not NICK_RE.match(nick):
            return _respond('Nickname: 1-24 chars, letters/digits/space/dash/underscore only', toast='error')
        cmd = f'nick {name} {nick}'
        action = f'set nickname to "{nick}"'

    result = rcon(cmd)
    log.info("nick: cmd=%r result=%r", cmd, result)

    # EssentialsX returns various confirmations; any "Error" prefix means RCON failure
    if result.startswith('Error'):
        return _respond(f'Nick failed: {result}', toast='error')

    return _respond(f'{name}: {action}. {result}', toast='success')

@app.route('/api/detect-platform')
@requires_auth
def api_detect_platform():
    """Used by the onboarding form to show 'Java/Bedrock detected' hint live."""
    name = request.args.get('name', '').strip().lstrip('.')
    if not name:
        return {'platform': 'unknown'}, 200
    platform, _uuid = detect_platform(name)
    return {'platform': platform, 'name': name}, 200

@app.route('/api/metrics')
@requires_auth
def api_metrics():
    days = int(request.args.get('days', 1))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    data = []
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, 'r') as f:
                all_data = json.load(f)
                data = [d for d in all_data if d.get('ts', '') >= cutoff]
        except (json.JSONDecodeError, FileNotFoundError):
            data = []
    # Downsample if too many points (keep max ~500 points for chart performance)
    if len(data) > 500:
        step = len(data) // 500
        data = data[::step]
    return json.dumps(data), 200, {'Content-Type': 'application/json'}

@app.route('/api/status')
@requires_auth
def api_status():
    """Lightweight JSON status used by dashboard's real-time poller."""
    sys_status = get_system_status()
    onboarding = process_onboarding()
    events = load_events()
    suspicious = get_suspicious_ips(events)

    # Recent events for live "last activity" tail
    recent = []
    for e in events[-15:][::-1]:
        recent.append({
            'time': (e.get('timestamp', '') + ' ' + e.get('time', '')).strip().replace('T', ' ')[:19],
            'type': e.get('type', ''),
            'player': e.get('player', ''),
            'ip': e.get('ip', ''),
            'reason': e.get('reason', ''),
        })

    onboarding_payload = None
    if onboarding:
        onboarding_payload = {
            'name': onboarding.get('name', ''),
            'platform': onboarding.get('platform', ''),
            'status': onboarding.get('status', ''),
            'seconds_left': onboarding.get('seconds_left', 0),
            'last_outcome': onboarding.get('last_outcome', ''),
            'reject_reason': onboarding.get('reject_reason', ''),
            'result': onboarding.get('result', ''),
        }

    return json.dumps({
        'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'mc_status': sys_status.get('mc_status', '?'),
        'mc_uptime': sys_status.get('mc_uptime', '?'),
        'players_online': sys_status.get('players_online', '?'),
        'players_max': sys_status.get('players_max', '?'),
        'player_names': sys_status.get('player_names', []),
        'tps': sys_status.get('tps', '?'),
        'tps_class': sys_status.get('tps_class', ''),
        'cpu_percent': sys_status.get('cpu_percent', '0'),
        'cpu_class': percent_class(sys_status.get('cpu_percent', '0')),
        'ram_used': sys_status.get('ram_used', '?'),
        'ram_total': sys_status.get('ram_total', '?'),
        'ram_percent': sys_status.get('ram_percent', '0'),
        'ram_class': percent_class(sys_status.get('ram_percent', '0')),
        'swap_percent': sys_status.get('swap_percent', '0'),
        'mc_ram_used': sys_status.get('mc_ram_used', '?'),
        'mc_ram_alloc': sys_status.get('mc_ram_alloc', '?'),
        'mc_ram_percent': sys_status.get('mc_ram_percent', '0'),
        'mc_ram_class': percent_class(sys_status.get('mc_ram_percent', '0')),
        'world_size': sys_status.get('world_size', '?'),
        'backup_count': sys_status.get('backup_count', '?'),
        'backup_last_size': sys_status.get('backup_last_size', '?'),
        'backup_last_date': sys_status.get('backup_last_date', '?'),
        'backup_age_hours': _hours_since_backup(sys_status.get('backup_last_date', '')),
        'suspicious_ip_count': len(suspicious),
        'event_count': len(events),
        'recent_events': recent,
        'onboarding': onboarding_payload,
    }), 200, {'Content-Type': 'application/json'}

def _hours_since_backup(backup_date_str):
    """Parse '04-15 22:30' style date into hours since now (rough estimate)."""
    if not backup_date_str or backup_date_str in ('?', 'N/A'):
        return None
    try:
        # Format is "MM-DD HH:MM" — assume current year
        year = datetime.now().year
        d = datetime.strptime(f"{year}-{backup_date_str}", "%Y-%m-%d %H:%M")
        # If that's in the future, must be previous year
        if d > datetime.now():
            d = datetime.strptime(f"{year-1}-{backup_date_str}", "%Y-%m-%d %H:%M")
        return round((datetime.now() - d).total_seconds() / 3600, 1)
    except Exception:
        return None

@app.route('/api/players')
@requires_auth
def api_players():
    """Lightweight player roster used by charts page dropdown."""
    events = load_events()
    nicknames = get_nicknames()
    stats = get_player_stats(events, nicknames)
    out = []
    for p in stats:
        if p.get('joins', 0) == 0 and p.get('session_count', 0) == 0:
            continue
        out.append({
            'name': p['name'],
            'display': p['display'],
            'platform': p['platform'],
            'total_seconds': p.get('total_seconds', 0),
            'total_human': format_duration(p.get('total_seconds', 0)),
            'session_count': p.get('session_count', 0),
        })
    return json.dumps(out), 200, {'Content-Type': 'application/json'}

@app.route('/api/playtime/<player>')
@requires_auth
def api_playtime(player):
    """Return per-day playtime totals for a single player (last 30 days)."""
    days = max(1, min(int(request.args.get('days', 30)), 180))
    events = load_events()
    sessions = merge_sessions_for_bedrock(compute_player_sessions(events))
    player_sessions = sessions.get(player, [])
    if not player_sessions and not player.startswith('.'):
        # Try with dot prefix (Bedrock)
        player_sessions = sessions.get(f'.{player}', [])
    daily = daily_playtime(player_sessions, days=days)
    return json.dumps({
        'player': player,
        'sessions': [
            {'start': s, 'end': e, 'duration': d} for s, e, d in player_sessions
        ],
        'daily': [
            {'date': d.isoformat(), 'seconds': sec} for d, sec in daily
        ],
        'total_seconds': sum(s[2] for s in player_sessions),
        'session_count': len(player_sessions),
    }), 200, {'Content-Type': 'application/json'}

CHARTS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Charts</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        :root[data-theme="dark"] {
            --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460;
            --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3;
            --border2: #333; --red: #e74c3c; --blue: #48bfe3; --yellow: #e7a33c;
        }
        :root[data-theme="light"] {
            --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1;
            --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f;
            --border2: #ccc; --red: #c0392b; --blue: #2980b9; --yellow: #d4a017;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 20px; font-size: 1em; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; display: inline-block; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; line-height: 1; }
        .theme-toggle:hover { background: var(--bg3); }
        .chart-container { background: var(--bg2); border-radius: 8px; padding: 20px; margin-bottom: 18px; }
        .range-selector { display: flex; gap: 6px; margin-bottom: 18px; flex-wrap: wrap; }
        .range-btn { background: var(--bg2); color: var(--text2); border: 1px solid var(--border2); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.9em; transition: all 0.2s; }
        .range-btn:hover { border-color: var(--accent); color: var(--accent); }
        .range-btn.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
        .loading { text-align: center; padding: 40px; color: var(--text2); }
        .legend-info { color: var(--text2); font-size: 0.85em; margin-top: 10px; }

        @media (max-width: 768px) {
            body { padding: 12px; }
            h1 { font-size: 1.3em; }
            .range-btn { padding: 6px 12px; font-size: 0.85em; }
            .chart-container { padding: 12px; }
        }
    </style>
    <script>
        function toggleTheme() {
            var html = document.documentElement;
            var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            document.cookie = 'theme=' + next + ';path=/;max-age=31536000';
            document.getElementById('themeIcon').innerHTML = next === 'dark' ? '&#x2600;' : '&#x1F319;';
            if (window.metricsChart) updateChartColors();
        }
        (function() {
            var match = document.cookie.match(/theme=(dark|light)/);
            if (match) document.documentElement.setAttribute('data-theme', match[1]);
        })();
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>Server Charts</h1>
            <div class="subtitle">System metrics over time</div>
        </div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/plugins" class="btn">&#x1F9E9; Plugins</a>
            <a href="/players" class="btn">&#x1F465; Players</a>
            <a href="/backups" class="btn">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>

    <div class="range-selector">
        <button class="range-btn active" onclick="loadData(1, this)">1 day</button>
        <button class="range-btn" onclick="loadData(2, this)">2 days</button>
        <button class="range-btn" onclick="loadData(5, this)">5 days</button>
        <button class="range-btn" onclick="loadData(7, this)">7 days</button>
        <button class="range-btn" onclick="loadData(15, this)">15 days</button>
        <button class="range-btn" onclick="loadData(30, this)">30 days</button>
        <button class="range-btn" onclick="loadData(60, this)">60 days</button>
        <button class="range-btn" onclick="loadData(90, this)">90 days</button>
        <button class="range-btn" onclick="loadData(180, this)">180 days</button>
    </div>

    <div class="chart-container">
        <canvas id="metricsChart" height="110"></canvas>
        <div class="loading" id="loadingMsg">Loading metrics data...</div>
    </div>

    <div class="legend-info">
        Data collected every 5 minutes. CPU, RAM, MC heap and Swap are in %. TPS is 0-20 (shown as 0-100% scale). Players shown as count.
    </div>

    <h2 style="color:var(--accent);margin-top:30px;font-size:1.2em;">&#x1F465; Per-Player Playtime</h2>
    <div class="range-selector" style="margin-top:10px;">
        <select id="playerSelect" style="background:var(--bg2);color:var(--text);border:1px solid var(--border2);padding:8px 12px;border-radius:6px;font-size:0.95em;">
            <option value="">-- select a player --</option>
        </select>
        <select id="playerDays" style="background:var(--bg2);color:var(--text);border:1px solid var(--border2);padding:8px 12px;border-radius:6px;font-size:0.95em;margin-left:8px;">
            <option value="14">14 days</option>
            <option value="30" selected>30 days</option>
            <option value="60">60 days</option>
            <option value="90">90 days</option>
        </select>
    </div>
    <div class="chart-container" style="margin-top:14px;">
        <canvas id="playtimeChart" height="90"></canvas>
        <div class="loading" id="playtimeMsg" style="display:none;">Loading playtime...</div>
    </div>
    <div id="playtimeSummary" style="text-align:center;color:var(--text2);font-size:0.9em;margin-top:8px;"></div>

    <script>
        var metricsChart = null;

        function getColors() {
            var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            return {
                cpu: '#e74c3c',
                ram: '#e7a33c',
                mc_heap: '#48bfe3',
                tps: '#4ecca3',
                players: '#a855f7',
                swap: '#f472b6',
                grid: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                text: isDark ? '#888' : '#666'
            };
        }

        function updateChartColors() {
            if (!metricsChart) return;
            var c = getColors();
            metricsChart.options.scales.y.grid.color = c.grid;
            metricsChart.options.scales.x.grid.color = c.grid;
            metricsChart.options.scales.y.ticks.color = c.text;
            metricsChart.options.scales.x.ticks.color = c.text;
            metricsChart.options.scales.y2.ticks.color = c.text;
            metricsChart.update();
        }

        function loadData(days, btn) {
            // Update active button
            document.querySelectorAll('.range-btn').forEach(function(b) { b.classList.remove('active'); });
            if (btn) btn.classList.add('active');

            document.getElementById('loadingMsg').style.display = 'block';

            fetch('/api/metrics?days=' + days)
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    document.getElementById('loadingMsg').style.display = 'none';
                    renderChart(data);
                })
                .catch(function(err) {
                    document.getElementById('loadingMsg').textContent = 'Error loading data: ' + err;
                });
        }

        function renderChart(data) {
            var labels = data.map(function(d) { return d.ts; });
            var c = getColors();

            var datasets = [
                { label: 'CPU %', data: data.map(function(d) { return d.cpu; }), borderColor: c.cpu, backgroundColor: c.cpu + '20', borderWidth: 1.5, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
                { label: 'RAM %', data: data.map(function(d) { return d.ram; }), borderColor: c.ram, backgroundColor: c.ram + '20', borderWidth: 1.5, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
                { label: 'MC Heap %', data: data.map(function(d) { return d.mc_heap; }), borderColor: c.mc_heap, backgroundColor: c.mc_heap + '20', borderWidth: 1.5, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
                { label: 'Swap %', data: data.map(function(d) { return d.swap; }), borderColor: c.swap, backgroundColor: c.swap + '20', borderWidth: 1.5, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
                { label: 'TPS (x5)', data: data.map(function(d) { return d.tps * 5; }), borderColor: c.tps, backgroundColor: c.tps + '20', borderWidth: 2, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
                { label: 'Players', data: data.map(function(d) { return d.players; }), borderColor: c.players, backgroundColor: c.players + '30', borderWidth: 2, pointRadius: 0, fill: true, tension: 0.3, yAxisID: 'y2' }
            ];

            if (metricsChart) metricsChart.destroy();

            var ctx = document.getElementById('metricsChart').getContext('2d');
            metricsChart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'top', labels: { usePointStyle: true, padding: 15, color: c.text, font: { size: 12 } } },
                        tooltip: {
                            callbacks: {
                                title: function(items) {
                                    var ts = items[0].label;
                                    return ts.replace('T', ' ');
                                },
                                label: function(item) {
                                    if (item.dataset.label === 'TPS (x5)') return 'TPS: ' + (item.raw / 5).toFixed(1);
                                    if (item.dataset.label === 'Players') return 'Players: ' + item.raw;
                                    return item.dataset.label + ': ' + item.raw.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: c.grid },
                            ticks: { color: c.text, maxTicksLimit: 12, maxRotation: 0,
                                callback: function(val, idx) {
                                    var label = this.getLabelForValue(val);
                                    if (!label) return '';
                                    var parts = label.split('T');
                                    if (parts.length === 2) {
                                        return parts[1].substring(0, 5);
                                    }
                                    return label;
                                }
                            }
                        },
                        y: {
                            position: 'left',
                            min: 0, max: 100,
                            grid: { color: c.grid },
                            ticks: { color: c.text, callback: function(v) { return v + '%'; } },
                            title: { display: true, text: 'Percent / TPS scaled', color: c.text }
                        },
                        y2: {
                            position: 'right',
                            min: 0,
                            grid: { drawOnChartArea: false },
                            ticks: { color: c.text, stepSize: 1 },
                            title: { display: true, text: 'Players', color: c.text }
                        }
                    }
                }
            });
        }

        // Load 1 day by default
        window.addEventListener('load', function() {
            loadData(1, document.querySelector('.range-btn.active'));
            // Fix theme icon
            var match = document.cookie.match(/theme=(dark|light)/);
            var theme = match ? match[1] : 'dark';
            document.getElementById('themeIcon').innerHTML = theme === 'dark' ? '&#x2600;' : '&#x1F319;';

            // ----- Per-player playtime chart -----
            populatePlayerSelect();
            document.getElementById('playerSelect').addEventListener('change', loadPlaytime);
            document.getElementById('playerDays').addEventListener('change', loadPlaytime);

            // Auto-load player from URL query (?player=NAME)
            var urlPlayer = new URLSearchParams(window.location.search).get('player');
            if (urlPlayer) {
                setTimeout(function() {
                    document.getElementById('playerSelect').value = urlPlayer;
                    loadPlaytime();
                }, 200);
            }
        });

        // Pulls player list from /players page (cheap workaround) or
        // alternatively from event log via /api/status. Use status's recent_events
        // is too small — query /api/players (created next).
        var playtimeChart = null;
        function populatePlayerSelect() {
            fetch('/api/players')
                .then(function(r){ return r.json(); })
                .then(function(arr) {
                    var sel = document.getElementById('playerSelect');
                    arr.forEach(function(p) {
                        var opt = document.createElement('option');
                        opt.value = p.name;
                        opt.textContent = p.display + ' (' + p.platform + ', ' + p.total_human + ')';
                        sel.appendChild(opt);
                    });
                })
                .catch(function(){});
        }

        function loadPlaytime() {
            var name = document.getElementById('playerSelect').value;
            if (!name) {
                if (playtimeChart) { playtimeChart.destroy(); playtimeChart = null; }
                document.getElementById('playtimeSummary').textContent = '';
                return;
            }
            var days = document.getElementById('playerDays').value;
            document.getElementById('playtimeMsg').style.display = 'block';
            fetch('/api/playtime/' + encodeURIComponent(name) + '?days=' + days)
                .then(function(r){ return r.json(); })
                .then(function(d) {
                    document.getElementById('playtimeMsg').style.display = 'none';
                    renderPlaytime(d);
                })
                .catch(function(err) {
                    document.getElementById('playtimeMsg').textContent = 'Error: ' + err;
                });
        }

        function fmtDur(seconds) {
            if (seconds < 60) return seconds + 's';
            if (seconds < 3600) return Math.floor(seconds/60) + 'm';
            var h = Math.floor(seconds/3600);
            var m = Math.floor((seconds % 3600)/60);
            return m ? (h + 'h ' + m + 'm') : (h + 'h');
        }

        function renderPlaytime(d) {
            var c = getColors();
            var labels = d.daily.map(function(x){ return x.date; });
            var values = d.daily.map(function(x){ return Math.round(x.seconds / 60); });

            if (playtimeChart) playtimeChart.destroy();
            var ctx = document.getElementById('playtimeChart').getContext('2d');
            playtimeChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Minutes per day',
                        data: values,
                        backgroundColor: c.players,
                        borderColor: c.players,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: function(item) { return fmtDur(item.raw * 60); } } }
                    },
                    scales: {
                        x: { grid: { color: c.grid }, ticks: { color: c.text, maxTicksLimit: 15 } },
                        y: { grid: { color: c.grid }, ticks: { color: c.text, callback: function(v){ return v + 'm'; } },
                             title: { display: true, text: 'Minutes', color: c.text } }
                    }
                }
            });
            document.getElementById('playtimeSummary').textContent =
                d.session_count + ' sessions, ' + fmtDur(d.total_seconds) + ' total over ' + d.daily.length + ' days';
        }
    </script>
</body>
</html>
"""

@app.route('/charts')
@requires_auth
def charts():
    html = CHARTS_TEMPLATE.replace('__FAVICON__', FAVICON)
    return html

def load_plugin_urls():
    if os.path.exists(PLUGIN_URLS_FILE):
        try:
            with open(PLUGIN_URLS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            log.exception("plugin urls read failed")
    return {}

def save_plugin_urls(urls):
    try:
        atomic_write_json(PLUGIN_URLS_FILE, urls, indent=2)
    except Exception:
        log.exception("plugin urls write failed")

def _normalize_plugin_name(s):
    """Lowercase, strip dashes/underscores/spaces — used for fuzzy matching."""
    return re.sub(r'[-_\s]', '', s.lower())

def _match_score(plugin_name, jar_filename):
    """
    Score how well a JAR filename matches a plugin name.
    Higher = better match. Returns 0 when the filename clearly doesn't match.

    Rules:
      - exact match (Plugin.jar == "Plugin"): 1000
      - filename starts with "{plugin}-" or "{plugin}.": 900 (e.g. ViaVersion-5.9.1.jar)
      - filename starts with the plugin name and next char is non-letter: 800
      - filename equals the plugin name normalized: 700
      - plugin name is a *prefix* of filename, but next char is a letter: 100 (weak)
      - plugin name appears as substring elsewhere: 50 (very weak)
      - else: 0
    """
    base = jar_filename
    if base.lower().endswith('.jar'):
        base = base[:-4]
    p = plugin_name
    pl = p.lower()
    bl = base.lower()
    pn = _normalize_plugin_name(p)
    bn = _normalize_plugin_name(base)

    # Exact (case-insensitive)
    if bl == pl:
        return 1000
    # Starts with "{plugin_name}-" or "{plugin_name}_" — most common JAR convention
    if bl.startswith(pl + '-') or bl.startswith(pl + '_') or bl.startswith(pl + '.'):
        return 900
    # Starts with plugin name and next char is non-letter (digit, version)
    if bl.startswith(pl) and len(bl) > len(pl) and not bl[len(pl)].isalpha():
        return 800
    # Normalized exact match (handles things like "World Edit" vs "WorldEdit.jar")
    if bn == pn:
        return 700
    # Normalized prefix with non-letter boundary in original
    if bn.startswith(pn) and len(bn) > len(pn):
        # Be careful: "viaversion" startswith for "viaversionstatus" is true here,
        # which is exactly the bug we're fixing. So we score this LOW so the
        # exact match always wins.
        return 100
    # Substring (very weak — last resort)
    if pn in bn:
        return 50
    return 0

def get_plugins_list():
    plugins = []
    try:
        # Use grep to find the Bukkit plugins line efficiently (logs can be 50000+ lines)
        result = subprocess.run('docker logs minecraft 2>&1 | grep -A 2 "Bukkit plugins"', shell=True, capture_output=True, text=True, timeout=15)
        text = strip_ansi(result.stdout)
        lines = text.split('\n')
        found_idx = -1
        for i, line in enumerate(lines):
            if 'Bukkit plugins' in line:
                found_idx = i
        if found_idx >= 0:
            plugin_text = lines[found_idx]
            for j in range(found_idx + 1, min(found_idx + 5, len(lines))):
                stripped = lines[j].strip()
                if stripped.startswith('-') or (stripped and not stripped.startswith('[')):
                    plugin_text += ' ' + stripped
                else:
                    break
            match = re.search(r'Bukkit plugins\s*\(\d+\):\s*(.*)', plugin_text, re.DOTALL)
            if match:
                after = re.sub(r'^-\s*', '', match.group(1).strip())
                seen = set()
                for item in re.split(r',\s*', after):
                    item = item.strip()
                    m = re.match(r'([A-Za-z][A-Za-z0-9_-]+(?:[- ][A-Za-z0-9_]+)*)\s*\((.+)\)', item)
                    if m:
                        name = m.group(1).strip()
                        version = m.group(2).strip()
                        if name not in seen:
                            seen.add(name)
                            plugins.append({'name': name, 'version': version})
    except Exception:
        log.exception("plugin list parse failed")

    plugins_dir = os.path.join(WORLD_DIR, 'plugins')
    urls = load_plugin_urls()

    # ---- Two-pass JAR assignment to prevent shared-filename bugs ----
    #
    # The previous "first candidate wins" logic was wrong: substring matching
    # made plugin "ViaVersion" claim "ViaVersionStatus.jar" as easily as
    # "ViaVersion.jar", and the winner depended on filesystem ordering. So
    # both plugins ended up pointing to the same JAR.
    #
    # Fix: compute a similarity score for every (plugin, jar) pair, then
    # assign greedily by descending score, with each JAR claimed at most once.
    try:
        all_jars = [f for f in os.listdir(plugins_dir) if f.endswith('.jar')]
    except Exception:
        log.exception("plugins dir listing failed")
        all_jars = []

    # Build (score, plugin_index, jar_filename) tuples
    candidates = []
    for idx, p in enumerate(plugins):
        for jar in all_jars:
            score = _match_score(p['name'], jar)
            if score > 0:
                candidates.append((score, idx, jar))

    # Greedy: highest score first; each plugin and each jar claimed once.
    # Tie-break by plugin index (stable) and jar name (alphabetical) for
    # deterministic output.
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    assigned_plugins = set()
    assigned_jars = set()
    for score, idx, jar in candidates:
        if idx in assigned_plugins or jar in assigned_jars:
            continue
        try:
            full = os.path.join(plugins_dir, jar)
            size = os.path.getsize(full)
            plugins[idx]['file'] = jar
            plugins[idx]['size'] = format_size(size)
        except Exception:
            log.exception("plugin file stat failed for %r -> %r", plugins[idx]['name'], jar)
            plugins[idx]['file'] = '?'
            plugins[idx]['size'] = '?'
        assigned_plugins.add(idx)
        assigned_jars.add(jar)

    # Anyone unmatched -> '?'
    for idx, p in enumerate(plugins):
        if 'file' not in p:
            p['file'] = '?'
            p['size'] = '?'
        p['url'] = urls.get(p.get('file', ''), '')

    return plugins

def get_player_stats(events, nicknames):
    players = {}
    for e in events:
        player = e.get('player', '')
        if not player:
            continue
        if player not in players:
            players[player] = {
                'joins': 0, 'leaves': 0, 'rejected': 0,
                'ips': set(), 'rejected_ips': set(),
                'first_seen': '', 'last_seen': '',
                'last_rejected': '', 'geyser': False,
            }
        ts = e.get('timestamp', '')
        etype = e.get('type', '')
        if etype == 'JOIN':
            players[player]['joins'] += 1
            ip = e.get('ip', '')
            if ip:
                players[player]['ips'].add(ip)
            if not players[player]['first_seen'] or ts < players[player]['first_seen']:
                players[player]['first_seen'] = ts
            if not players[player]['last_seen'] or ts > players[player]['last_seen']:
                players[player]['last_seen'] = ts
        elif etype == 'LEAVE':
            players[player]['leaves'] += 1
        elif etype == 'REJECTED':
            players[player]['rejected'] += 1
            ip = e.get('ip', '')
            if ip:
                players[player]['rejected_ips'].add(ip)
            if not players[player]['last_rejected'] or ts > players[player]['last_rejected']:
                players[player]['last_rejected'] = ts
        elif etype == 'GEYSER_CONNECT':
            players[player]['geyser'] = True
    # Merge dot and non-dot versions (Bedrock: .Name from JOIN + Name from GEYSER)
    merged = {}
    for name, stats in players.items():
        # For Bedrock players: merge ".Name" and "Name" under ".Name"
        # For Java players: keep as-is (no dot)
        if name.startswith('.'):
            key = name
        else:
            # Check if a dot version exists (meaning this is the Geyser side)
            dot_version = f'.{name}'
            if dot_version in players:
                key = dot_version  # merge under dot version
            else:
                key = name  # Java player, keep as-is
        if key not in merged:
            merged[key] = {
                'joins': 0, 'leaves': 0, 'rejected': 0,
                'ips': set(), 'rejected_ips': set(),
                'first_seen': '', 'last_seen': '',
                'last_rejected': '', 'geyser': False,
            }
        merged[key]['joins'] += stats['joins']
        merged[key]['leaves'] += stats['leaves']
        merged[key]['rejected'] += stats['rejected']
        merged[key]['ips'].update(stats['ips'])
        merged[key]['rejected_ips'].update(stats['rejected_ips'])
        if stats['first_seen'] and (not merged[key]['first_seen'] or stats['first_seen'] < merged[key]['first_seen']):
            merged[key]['first_seen'] = stats['first_seen']
        if stats['last_seen'] and (not merged[key]['last_seen'] or stats['last_seen'] > merged[key]['last_seen']):
            merged[key]['last_seen'] = stats['last_seen']
        if stats['last_rejected'] and (not merged[key]['last_rejected'] or stats['last_rejected'] > merged[key]['last_rejected']):
            merged[key]['last_rejected'] = stats['last_rejected']
        if stats['geyser']:
            merged[key]['geyser'] = True
    # Convert sets to lists and add nicknames + session stats
    sessions = merge_sessions_for_bedrock(compute_player_sessions(events))
    result = []
    for name, stats in merged.items():
        stats['name'] = name
        stats['display'] = format_player_name(name, nicknames)
        stats['ips'] = sorted(stats['ips'])
        stats['rejected_ips'] = sorted(stats['rejected_ips'])
        stats['platform'] = 'Bedrock' if stats['geyser'] or name.startswith('.') else 'Java'
        # Session stats
        player_sessions = sessions.get(name, [])
        if not player_sessions and name.startswith('.'):
            player_sessions = sessions.get(name[1:], [])
        stats['session_count'] = len(player_sessions)
        stats['total_seconds'] = sum(s[2] for s in player_sessions)
        stats['avg_seconds'] = (stats['total_seconds'] // len(player_sessions)) if player_sessions else 0
        stats['longest_seconds'] = max((s[2] for s in player_sessions), default=0)
        result.append(stats)
    return sorted(result, key=lambda x: x['total_seconds'], reverse=True)

PLUGIN_HISTORY_FILE = "/home/pi/mc-plugin-history.json"
PLUGIN_HISTORY_MAX = 50  # keep last N events

def load_plugin_history():
    if os.path.exists(PLUGIN_HISTORY_FILE):
        try:
            with open(PLUGIN_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            log.exception("plugin history read failed")
    return []

def append_plugin_history(entry):
    """entry: {filename, old_size, new_size, status, timestamp}"""
    h = load_plugin_history()
    h.append(entry)
    if len(h) > PLUGIN_HISTORY_MAX:
        h = h[-PLUGIN_HISTORY_MAX:]
    try:
        atomic_write_json(PLUGIN_HISTORY_FILE, h)
    except Exception:
        log.exception("plugin history write failed")

@app.route('/api/plugins/update', methods=['POST'])
@requires_auth
@requires_csrf
def api_plugin_update():
    filename = request.form.get('file', '').strip()
    url = request.form.get('url', '').strip()
    if not filename or not url:
        return _respond('Missing file or URL', redirect_to='/plugins', toast='error')
    if '/' in filename or '\\' in filename or filename.startswith('.'):
        log.warning("plugin update rejected: bad filename %r", filename)
        return _respond('Bad filename', redirect_to='/plugins', toast='error')
    if not (url.startswith('http://') or url.startswith('https://')):
        return _respond('URL must be http(s)', redirect_to='/plugins', toast='error')
    urls = load_plugin_urls()
    urls[filename] = url
    save_plugin_urls(urls)
    plugins_dir = os.path.join(WORLD_DIR, 'plugins')
    filepath = os.path.join(plugins_dir, filename)
    old_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    old_hash = _file_sha256(filepath) if os.path.exists(filepath) else None
    ts = datetime.now().replace(microsecond=0).isoformat()
    # Download to a staging path so we can compare before replacing
    staging = filepath + '.new'
    try:
        result = subprocess.run(['curl', '-fL', '-o', staging, url], capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(staging):
            new_size = os.path.getsize(staging)
            new_hash = _file_sha256(staging)
            # Dedup: identical content -> discard download, no restart needed
            if old_hash and new_hash == old_hash:
                try:
                    os.remove(staging)
                except OSError:
                    log.exception("could not remove staging file %s", staging)
                log.info("plugin unchanged: file=%s sha256=%s", filename, new_hash[:12])
                append_plugin_history({
                    'filename': filename, 'timestamp': ts, 'status': 'unchanged',
                    'old_size': old_size, 'new_size': new_size, 'delta': 0,
                    'sha256': new_hash,
                })
                msg = f'{filename}: identical to current version ({format_size(new_size)}). No restart needed.'
                if _wants_json():
                    return {
                        'ok': True, 'message': msg, 'toast': 'info',
                        'filename': filename, 'old_size': old_size, 'new_size': new_size,
                        'delta': 0, 'unchanged': True, 'timestamp': ts,
                    }, 200
                return _respond(msg, redirect_to='/plugins', toast='info')
            # Different content -> promote staging into place atomically
            os.replace(staging, filepath)
            delta = new_size - old_size
            log.info("plugin updated: file=%s old=%d new=%d delta=%+d hash_changed=%s",
                     filename, old_size, new_size, delta, old_hash != new_hash)
            append_plugin_history({
                'filename': filename, 'timestamp': ts, 'status': 'ok',
                'old_size': old_size, 'new_size': new_size, 'delta': delta,
                'sha256': new_hash,
            })
            if old_size == 0:
                change_part = f'(new install, {format_size(new_size)})'
            elif delta == 0:
                # Same size but different content (rare — recompile / different build)
                change_part = f'(content changed, same size: {format_size(new_size)})'
            elif delta > 0:
                change_part = f'({format_size(old_size)} -> {format_size(new_size)}, +{format_size(delta)})'
            else:
                change_part = f'({format_size(old_size)} -> {format_size(new_size)}, -{format_size(-delta)})'
            msg = f'Updated {filename} {change_part}. Restart needed!'
            if _wants_json():
                return {
                    'ok': True, 'message': msg, 'toast': 'success',
                    'filename': filename, 'old_size': old_size, 'new_size': new_size,
                    'delta': delta, 'unchanged': False, 'timestamp': ts,
                }, 200
            return _respond(msg, redirect_to='/plugins', toast='success')
        # Curl failed
        if os.path.exists(staging):
            try: os.remove(staging)
            except OSError: pass
        log.warning("plugin update failed: file=%s rc=%d stderr=%s", filename, result.returncode, result.stderr[:200])
        append_plugin_history({
            'filename': filename, 'timestamp': ts, 'status': 'failed',
            'old_size': old_size, 'new_size': old_size, 'delta': 0,
            'error': result.stderr[:200],
        })
        return _respond(f'Error downloading {filename}: {result.stderr[:100]}', redirect_to='/plugins', toast='error')
    except Exception as e:
        if os.path.exists(staging):
            try: os.remove(staging)
            except OSError: pass
        log.exception("plugin update exception: file=%s", filename)
        append_plugin_history({
            'filename': filename, 'timestamp': ts, 'status': 'error',
            'old_size': old_size, 'new_size': old_size, 'delta': 0,
            'error': str(e)[:200],
        })
        return _respond(f'Error: {e}', redirect_to='/plugins', toast='error')

def _file_sha256(path):
    """Compute SHA256 of a file. Returns hex string or None on error."""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        log.exception("sha256 compute failed for %s", path)
        return None

@app.route('/api/plugins/update-all', methods=['POST'])
@requires_auth
@requires_csrf
def api_plugin_update_all():
    urls = load_plugin_urls()
    if not urls:
        return _respond('No plugin URLs configured', redirect_to='/plugins', toast='warning')
    plugins_dir = os.path.join(WORLD_DIR, 'plugins')
    items = []
    ok_count = 0
    unchanged_count = 0
    fail_count = 0
    for filename, url in urls.items():
        ts = datetime.now().replace(microsecond=0).isoformat()
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            log.warning("update-all skipping bad filename %r", filename)
            items.append({'filename': filename, 'status': 'skipped', 'reason': 'bad-filename'})
            fail_count += 1
            continue
        if not (url.startswith('http://') or url.startswith('https://')):
            items.append({'filename': filename, 'status': 'skipped', 'reason': 'bad-url'})
            fail_count += 1
            continue
        filepath = os.path.join(plugins_dir, filename)
        old_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        old_hash = _file_sha256(filepath) if os.path.exists(filepath) else None
        staging = filepath + '.new'
        try:
            result = subprocess.run(['curl', '-fL', '-o', staging, url], capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(staging):
                new_size = os.path.getsize(staging)
                new_hash = _file_sha256(staging)
                if old_hash and new_hash == old_hash:
                    # Identical — discard
                    try: os.remove(staging)
                    except OSError: pass
                    log.info("update-all unchanged: file=%s", filename)
                    append_plugin_history({
                        'filename': filename, 'timestamp': ts, 'status': 'unchanged',
                        'old_size': old_size, 'new_size': new_size, 'delta': 0,
                        'sha256': new_hash,
                    })
                    items.append({
                        'filename': filename, 'status': 'unchanged',
                        'old_size': old_size, 'new_size': new_size, 'delta': 0,
                        'old_human': format_size(old_size), 'new_human': format_size(new_size),
                    })
                    unchanged_count += 1
                    continue
                # Different — replace
                os.replace(staging, filepath)
                delta = new_size - old_size
                log.info("update-all ok: file=%s old=%d new=%d delta=%+d", filename, old_size, new_size, delta)
                append_plugin_history({
                    'filename': filename, 'timestamp': ts, 'status': 'ok',
                    'old_size': old_size, 'new_size': new_size, 'delta': delta,
                    'sha256': new_hash,
                })
                items.append({
                    'filename': filename, 'status': 'ok',
                    'old_size': old_size, 'new_size': new_size, 'delta': delta,
                    'old_human': format_size(old_size), 'new_human': format_size(new_size),
                })
                ok_count += 1
            else:
                if os.path.exists(staging):
                    try: os.remove(staging)
                    except OSError: pass
                log.warning("update-all failed: file=%s rc=%d", filename, result.returncode)
                append_plugin_history({
                    'filename': filename, 'timestamp': ts, 'status': 'failed',
                    'old_size': old_size, 'new_size': old_size, 'delta': 0,
                    'error': result.stderr[:200],
                })
                items.append({'filename': filename, 'status': 'failed', 'reason': 'curl-error'})
                fail_count += 1
        except Exception as e:
            if os.path.exists(staging):
                try: os.remove(staging)
                except OSError: pass
            log.exception("update-all exception: file=%s", filename)
            append_plugin_history({
                'filename': filename, 'timestamp': ts, 'status': 'error',
                'old_size': old_size, 'new_size': old_size, 'delta': 0,
                'error': str(e)[:200],
            })
            items.append({'filename': filename, 'status': 'error', 'reason': str(e)[:80]})
            fail_count += 1
    parts = []
    if ok_count: parts.append(f'{ok_count} updated')
    if unchanged_count: parts.append(f'{unchanged_count} unchanged')
    if fail_count: parts.append(f'{fail_count} failed')
    summary = ', '.join(parts) if parts else 'nothing to do'
    if ok_count > 0:
        summary += '. Restart needed!'
    if _wants_json():
        return {
            'ok': fail_count == 0,
            'message': summary,
            'toast': 'success' if (fail_count == 0 and ok_count > 0) else ('info' if fail_count == 0 else 'warning'),
            'items': items, 'restart_needed': ok_count > 0,
        }, 200
    text_lines = []
    for it in items:
        if it['status'] == 'ok':
            text_lines.append(f"{it['filename']}: {it['old_human']} -> {it['new_human']}")
        elif it['status'] == 'unchanged':
            text_lines.append(f"{it['filename']}: unchanged")
        else:
            text_lines.append(f"{it['filename']}: {it['status'].upper()}")
    full_msg = summary + ' Details: ' + ' | '.join(text_lines)
    return _respond(full_msg, redirect_to='/plugins', toast='success' if fail_count == 0 else 'warning')

@app.route('/api/plugins/history')
@requires_auth
def api_plugin_history():
    h = load_plugin_history()
    # Newest first
    return json.dumps(list(reversed(h))), 200, {'Content-Type': 'application/json'}

# ----------------------------------------------------------------------------
# Location bookmarks — named (X, Y, Z) coordinates persisted to JSON.
# Used as one-tap presets in the Teleport modal on /players.
# ----------------------------------------------------------------------------
LOCATIONS_FILE = "/home/pi/mc-locations.json"
LOCATION_NAME_MAX = 30
LOCATION_NAME_RE = re.compile(r'^[A-Za-z0-9 _\-\u0400-\u04ff]{1,30}$')  # Cyrillic allowed

def load_locations():
    if os.path.exists(LOCATIONS_FILE):
        try:
            with open(LOCATIONS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            log.exception("locations read failed")
    return []

def save_locations(locs):
    try:
        atomic_write_json(LOCATIONS_FILE, locs, indent=2)
    except Exception:
        log.exception("locations write failed")

@app.route('/api/locations')
@requires_auth
def api_locations_list():
    return json.dumps(load_locations()), 200, {'Content-Type': 'application/json'}

@app.route('/api/locations/add', methods=['POST'])
@requires_auth
@requires_csrf
def api_locations_add():
    name = request.form.get('name', '').strip()
    coords = request.form.get('coords', '').strip()
    if not name or not LOCATION_NAME_RE.match(name):
        return _respond('Bad location name (1-30 chars, letters/digits/space/dash)', toast='error')
    normalized = _validate_coords(coords)
    if not normalized:
        return _respond('Coordinates must be 3 numbers', toast='error')
    locs = load_locations()
    # Replace if same name exists, else append
    locs = [l for l in locs if l.get('name') != name]
    locs.append({'name': name, 'coords': normalized, 'added_at': datetime.now().replace(microsecond=0).isoformat()})
    save_locations(locs)
    log.info("location added: %s = %s", name, normalized)
    if _wants_json():
        return {'ok': True, 'message': f'Saved "{name}"', 'toast': 'success'}, 200
    return _respond(f'Saved "{name}"', toast='success')

@app.route('/api/locations/remove', methods=['POST'])
@requires_auth
@requires_csrf
def api_locations_remove():
    name = request.form.get('name', '').strip()
    if not name:
        return _respond('Missing name', toast='error')
    locs = load_locations()
    before = len(locs)
    locs = [l for l in locs if l.get('name') != name]
    if len(locs) == before:
        return _respond(f'No location "{name}"', toast='warning')
    save_locations(locs)
    log.info("location removed: %s", name)
    if _wants_json():
        return {'ok': True, 'message': f'Removed "{name}"', 'toast': 'success'}, 200
    return _respond(f'Removed "{name}"', toast='success')

# ----------------------------------------------------------------------------
# Chat — reads persisted chat history from /home/pi/mc-chat-log.json (written
# by mc-access-logger.py every 5 minutes). Long retention (90 days), cap 50k.
# Also forwards admin messages to in-game chat via the `say` RCON command.
# ----------------------------------------------------------------------------
CHAT_FILE = "/home/pi/mc-chat-log.json"

def load_chat_messages():
    """Read the full persisted chat history (oldest first)."""
    if not os.path.exists(CHAT_FILE):
        return []
    try:
        with open(CHAT_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        log.exception("chat file read failed")
    return []

def get_recent_chat(since_minutes=None, since_iso=None, limit=500):
    """
    Return chat messages, optionally filtered by minutes-ago or ISO cutoff.
    Falls back to live docker logs scrape if the persisted file is empty
    (e.g. fresh deploy before logger has run).
    """
    msgs = load_chat_messages()
    if not msgs:
        # Fallback: scrape recent live logs if file is empty
        return _scrape_chat_from_docker(since_minutes or 120, limit)

    if since_iso:
        msgs = [m for m in msgs if m.get('timestamp', '') >= since_iso]
    elif since_minutes is not None:
        cutoff = (datetime.now() - timedelta(minutes=int(since_minutes))).strftime("%Y-%m-%dT%H:%M:%S")
        msgs = [m for m in msgs if m.get('timestamp', '') >= cutoff]
    return msgs[-limit:]

def _scrape_chat_from_docker(since_minutes, limit):
    """Last-resort live scrape from docker logs. Used only when chat file is empty."""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--since', f'{int(since_minutes)}m', 'minecraft'],
            capture_output=True, text=True, timeout=10
        )
        text = strip_ansi(result.stdout + result.stderr)
    except Exception:
        log.exception("docker logs failed for chat fallback")
        return []
    messages = []
    for line in text.splitlines():
        line = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*', '', line)
        m = CHAT_RE.search(line)
        if m:
            messages.append({'time': m.group(1), 'sender': m.group(2),
                             'text': m.group(3), 'kind': 'chat'})
            continue
        m = SERVER_SAY_RE.search(line)
        if m:
            messages.append({'time': m.group(1), 'sender': 'Server',
                             'text': m.group(2), 'kind': 'server'})
    return messages[-limit:]

# Match Vanilla/Paper format: "[HH:MM:SS INFO]: <Player> message"
CHAT_RE = re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: <([^>]+)> (.+)$')
SERVER_SAY_RE = re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: \[(?:Server|Not Secure\] \[Server)\] (.+)$')

@app.route('/api/chat')
@requires_auth
def api_chat():
    """Returns chat messages.

    Params:
      minutes  — last N minutes (default 1440 = 24h, max 90 days)
      since    — ISO timestamp ('2026-04-01T00:00:00') for explicit cutoff
      limit    — max messages to return (default 500, max 5000)
    """
    since_iso = request.args.get('since', '').strip() or None
    try:
        minutes = int(request.args.get('minutes', 1440))
    except ValueError:
        minutes = 1440
    minutes = max(1, min(minutes, 90 * 24 * 60))  # cap at 90 days
    try:
        limit = int(request.args.get('limit', 500))
    except ValueError:
        limit = 500
    limit = max(10, min(limit, 5000))

    msgs = get_recent_chat(
        since_minutes=None if since_iso else minutes,
        since_iso=since_iso,
        limit=limit,
    )
    total = len(load_chat_messages())
    return json.dumps({
        'messages': msgs,
        'count': len(msgs),
        'total_persisted': total,
    }), 200, {'Content-Type': 'application/json'}

# Restrict chat input: printable text, no control chars, reasonable length.
# Minecraft itself will further sanitize, but we don't want shell metacharacters
# leaking into RCON arguments.
CHAT_TEXT_MAX = 200
CHAT_TEXT_RE = re.compile(r'^[^\x00-\x1f\x7f]{1,200}$')

@app.route('/api/chat/send', methods=['POST'])
@requires_auth
@requires_csrf
def api_chat_send():
    text = request.form.get('text', '').strip()
    if not text:
        return _respond('Empty message', toast='error')
    if not CHAT_TEXT_RE.match(text):
        return _respond('Message contains invalid characters', toast='error')
    if len(text) > CHAT_TEXT_MAX:
        return _respond(f'Message too long (max {CHAT_TEXT_MAX} chars)', toast='error')
    # Use the `say` command — broadcasts a [Server] prefix in chat
    result = rcon(f'say {text}')
    log.info("chat sent: text=%r result=%r", text[:80], result[:80])
    if _wants_json():
        return {'ok': True, 'message': 'Message sent', 'toast': 'success'}, 200
    return _respond('Message sent', toast='success')

# ----------------------------------------------------------------------------
# Logs viewer — read recent Docker logs with filter / search / tail count.
# ----------------------------------------------------------------------------
LOG_LEVELS = ('INFO', 'WARN', 'ERROR', 'DEBUG')
LOG_LINE_LEVEL_RE = re.compile(r'\b(INFO|WARN|WARNING|ERROR|FATAL|DEBUG|TRACE)\b')

@app.route('/api/logs')
@requires_auth
def api_logs():
    """
    Read last N lines from Docker logs with optional level filter and search.
    Caps tail at 2000 to keep response size reasonable.
    """
    try:
        tail = int(request.args.get('tail', 200))
    except ValueError:
        tail = 200
    tail = max(10, min(tail, 2000))

    level = (request.args.get('level', '') or '').upper().strip()
    search = (request.args.get('search', '') or '').strip()

    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(tail), 'minecraft'],
            capture_output=True, text=True, timeout=15,
        )
        text = strip_ansi(result.stdout + result.stderr)
    except Exception:
        log.exception("docker logs failed for /api/logs")
        return json.dumps({'lines': [], 'error': 'docker logs failed'}), 200, {'Content-Type': 'application/json'}

    lines = []
    for raw in text.splitlines():
        # Strip Docker timestamp prefix if present
        m = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s*(.*)$', raw)
        if m:
            ts = m.group(1)
            content = m.group(2)
        else:
            ts = ''
            content = raw

        # Detect level
        lm = LOG_LINE_LEVEL_RE.search(content)
        line_level = ''
        if lm:
            lev = lm.group(1)
            line_level = 'WARN' if lev == 'WARNING' else ('ERROR' if lev == 'FATAL' else lev)

        # Apply level filter
        if level:
            if level == 'WARN':
                if line_level not in ('WARN', 'ERROR', 'FATAL'):
                    continue
            elif level == 'ERROR':
                if line_level not in ('ERROR', 'FATAL'):
                    continue
            elif level == 'INFO':
                if line_level not in ('INFO', 'WARN', 'ERROR', 'FATAL'):
                    continue
            elif level == 'DEBUG':
                pass  # show all

        # Apply substring search (case-insensitive)
        if search and search.lower() not in content.lower():
            continue

        lines.append({
            'ts': ts,
            'level': line_level,
            'text': content,
        })

    return json.dumps({
        'lines': lines,
        'total_scanned': len(text.splitlines()),
        'tail': tail,
        'level': level,
        'search': search,
    }), 200, {'Content-Type': 'application/json'}

# /logs page route — registered later alongside template definition

PLUGINS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Plugins</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --yellow: #e7a33c; --red: #e74c3c; --msg-bg: #1b3a4b; --tag-join-bg: #1b4332; --tag-reject-bg: #3d1111; --tag-gdiscon-bg: #3d2911; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --yellow: #d4a017; --red: #c0392b; --msg-bg: #d1ecf1; --tag-join-bg: #d5f5e3; --tag-reject-bg: #fadbd8; --tag-gdiscon-bg: #fcf3cf; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; display: inline-block; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .btn-update { color: var(--blue); border-color: var(--blue); font-size: 0.8em; padding: 4px 10px; }
        .btn-update:hover { background: var(--blue); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; line-height: 1; }
        .msg-box { background: var(--msg-bg); border: 1px solid var(--blue); border-radius: 8px; padding: 10px 16px; margin-bottom: 18px; color: var(--blue); font-size: 0.9em; word-break: break-all; }

        /* Toolbar with search + sort + summary */
        .plugin-toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; }
        .plugin-toolbar input, .plugin-toolbar select { background: var(--bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 12px; border-radius: 6px; font-size: 0.9em; }
        .plugin-toolbar input[type=search] { flex: 1; min-width: 180px; }
        .plugin-toolbar label { color: var(--text2); font-size: 0.85em; }

        /* Plugin counters */
        .plugin-stats { display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 14px; color: var(--text2); font-size: 0.9em; }
        .plugin-stats strong { color: var(--text); font-family: monospace; }
        .plugin-stats .pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; background: var(--bg2); border-radius: 12px; }
        .plugin-stats .pill.ok { color: var(--accent); }
        .plugin-stats .pill.warn { color: var(--yellow); }
        .plugin-stats .pill.bad { color: var(--red); }

        .plugin-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
        .plugin-card { background: var(--bg2); border: 1px solid var(--border3); border-radius: 12px; padding: 14px; transition: border-color 0.15s; }
        .plugin-card:hover { border-color: var(--accent); }
        .plugin-card.no-url { border-left: 3px solid var(--yellow); }
        .plugin-card.no-jar { border-left: 3px solid var(--red); }
        .plugin-card.has-url { border-left: 3px solid var(--accent); }
        .plugin-name { font-size: 1.1em; font-weight: 700; color: var(--accent); margin-bottom: 4px; word-break: break-word; }
        .plugin-version { font-family: monospace; background: var(--bg3); color: var(--text); padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
        .plugin-status { font-size: 0.7em; padding: 2px 8px; border-radius: 10px; margin-left: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
        .plugin-status.ok { background: var(--tag-join-bg); color: var(--accent); }
        .plugin-status.warn { background: var(--tag-gdiscon-bg); color: var(--yellow); }
        .plugin-status.bad { background: var(--tag-reject-bg); color: var(--red); }
        .plugin-meta { color: var(--text2); font-size: 0.82em; margin-top: 4px; word-break: break-all; }
        .plugin-url { display: flex; gap: 4px; margin-top: 8px; }
        .plugin-url input { flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--border2); padding: 4px 8px; border-radius: 4px; font-size: 0.8em; min-width: 0; }
        .plugin-count { color: var(--text2); font-size: 0.95em; margin-bottom: 16px; }

        .restart-banner { background: var(--tag-gdiscon-bg); color: var(--yellow); border: 1px solid var(--yellow); border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.9em; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .restart-banner button { background: var(--yellow); color: #000; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; font-weight: 600; margin-left: auto; }

        /* Recent update badge on plugin cards */
        .recent-badge { display: inline-block; font-size: 0.7em; padding: 2px 8px; border-radius: 10px; margin-left: 6px; background: var(--tag-join-bg); color: var(--accent); }
        .recent-badge.recent-fail { background: var(--tag-reject-bg); color: var(--red); }

        /* Update history list */
        .history-list { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
        .history-row { background: var(--bg2); border: 1px solid var(--border3); border-left: 3px solid var(--accent); border-radius: 6px; padding: 8px 12px; font-size: 0.85em; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .history-row.failed { border-left-color: var(--red); }
        .history-row.skipped { border-left-color: var(--yellow); }
        .history-row.unchanged { border-left-color: var(--text3); opacity: 0.85; }
        .history-row .h-status.unchanged { color: var(--text2); font-style: italic; }
        .history-row .h-time { color: var(--text3); font-family: monospace; font-size: 0.8em; min-width: 130px; }
        .history-row .h-name { color: var(--text); font-weight: 600; flex: 1; min-width: 100px; word-break: break-all; }
        .history-row .h-change { color: var(--text2); font-family: monospace; font-size: 0.85em; }
        .history-row .h-delta { font-family: monospace; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
        .history-row .h-delta.up { background: var(--tag-join-bg); color: var(--accent); }
        .history-row .h-delta.down { background: var(--tag-gdiscon-bg); color: var(--yellow); }
        .history-row .h-delta.zero { color: var(--text3); }
        .history-row .h-status.fail { color: var(--red); }
        .history-row .h-status.skip { color: var(--yellow); }

        @media (max-width: 600px) { body { padding: 12px; } .plugin-grid { grid-template-columns: 1fr; } }

        #toastContainer { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 9999; max-width: 360px; pointer-events: none; }
        .toast { pointer-events: auto; padding: 12px 16px; border-radius: 8px; font-size: 0.9em; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: flex; align-items: flex-start; gap: 10px; }
        .toast.toast-success { background: #2d8f6f; }
        .toast.toast-error { background: #c0392b; }
        .toast.toast-warning { background: #d4a017; color: #1a1a2e; }
        .toast.toast-info { background: #2980b9; }
        .toast .toast-close { background: none; border: none; color: inherit; cursor: pointer; font-size: 1.2em; line-height: 1; opacity: 0.7; padding: 0; margin-left: auto; }
    </style>
    <script>
        var CSRF_TOKEN = '__CSRF__';
        function toggleTheme() { var h=document.documentElement,n=h.getAttribute('data-theme')==='dark'?'light':'dark'; h.setAttribute('data-theme',n); document.cookie='theme='+n+';path=/;max-age=31536000'; document.getElementById('themeIcon').innerHTML=n==='dark'?'&#x2600;':'&#x1F319;'; }
        (function(){var m=document.cookie.match(/theme=(dark|light)/);if(m)document.documentElement.setAttribute('data-theme',m[1]);})();
    </script>
</head>
<body>
    <div class="header">
        <div><h1>Server Plugins</h1><div class="subtitle">Installed plugins and versions</div></div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/charts" class="btn">&#x1F4CA; Charts</a>
            <a href="/players" class="btn">&#x1F465; Players</a>
            <a href="/backups" class="btn">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <button id="updateAllBtn" class="btn btn-update">&#x21BB; Update All</button>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>
    __MSG__

    <div id="restartBanner" class="restart-banner" style="display:none;">
        &#x26A0;&#xFE0F; <strong>Plugin file changed.</strong> A server restart is required for the new version to load.
        <button id="restartFromPluginsBtn">&#x21BB; Restart server</button>
    </div>

    <div class="plugin-stats">
        __STATS__
    </div>

    <div class="plugin-toolbar">
        <input type="search" id="pluginSearch" placeholder="Search plugins by name..." autocomplete="off">
        <label>Sort:</label>
        <select id="pluginSort">
            <option value="name">Name</option>
            <option value="name-desc">Name (Z-A)</option>
            <option value="size-desc">Size (large first)</option>
            <option value="size">Size (small first)</option>
            <option value="status">Status (issues first)</option>
        </select>
        <label>Filter:</label>
        <select id="pluginFilter">
            <option value="all">All plugins</option>
            <option value="no-url">No URL configured</option>
            <option value="has-url">Has URL</option>
            <option value="no-jar">JAR missing</option>
        </select>
    </div>

    <div class="plugin-grid" id="pluginGrid">__PLUGIN_CARDS__</div>

    <h2 id="historyTitle" style="display:none;color:var(--accent);margin-top:30px;font-size:1.1em;">&#x1F551; Recent updates</h2>
    <div id="historyList" class="history-list"></div>

    <div id="toastContainer"></div>

    <script>
        function showToast(msg, type, durationMs) {
            type = type || 'info';
            durationMs = durationMs || 6000;
            var c = document.getElementById('toastContainer');
            var t = document.createElement('div');
            t.className = 'toast toast-' + type;
            t.innerHTML = '<span></span><button class="toast-close" type="button">&#x2715;</button>';
            t.firstChild.textContent = msg;
            t.querySelector('.toast-close').addEventListener('click', function(){ t.remove(); });
            c.appendChild(t);
            setTimeout(function(){ if (t.parentNode) t.remove(); }, durationMs);
        }

        // Show ?msg= param as toast and clean URL
        (function() {
            var p = new URLSearchParams(window.location.search);
            var msg = p.get('msg');
            if (msg) {
                showToast(msg, msg.toLowerCase().indexOf('error')>=0 || msg.toLowerCase().indexOf('failed')>=0 ? 'error' : 'info', 12000);
                p.delete('msg');
                history.replaceState({}, '', window.location.pathname + (p.toString()?'?'+p:''));
            }
        })();

        // Filter / sort / search
        function applyView() {
            var q = (document.getElementById('pluginSearch').value || '').toLowerCase();
            var sort = document.getElementById('pluginSort').value;
            var filter = document.getElementById('pluginFilter').value;
            var grid = document.getElementById('pluginGrid');
            var cards = Array.from(grid.children);

            cards.forEach(function(card) {
                var name = (card.dataset.name || '').toLowerCase();
                var status = card.dataset.status || 'ok';
                var matchQ = !q || name.indexOf(q) >= 0;
                var matchF = (filter === 'all') ||
                             (filter === 'no-url' && status === 'no-url') ||
                             (filter === 'has-url' && status === 'has-url') ||
                             (filter === 'no-jar' && status === 'no-jar');
                card.style.display = (matchQ && matchF) ? '' : 'none';
            });

            cards.sort(function(a, b) {
                if (sort === 'name') return (a.dataset.name||'').localeCompare(b.dataset.name||'');
                if (sort === 'name-desc') return (b.dataset.name||'').localeCompare(a.dataset.name||'');
                if (sort === 'size-desc') return (parseInt(b.dataset.size,10)||0) - (parseInt(a.dataset.size,10)||0);
                if (sort === 'size') return (parseInt(a.dataset.size,10)||0) - (parseInt(b.dataset.size,10)||0);
                if (sort === 'status') {
                    var rank = { 'no-jar': 0, 'no-url': 1, 'has-url': 2 };
                    return (rank[a.dataset.status]||9) - (rank[b.dataset.status]||9);
                }
                return 0;
            });
            cards.forEach(function(c) { grid.appendChild(c); });
        }

        document.getElementById('pluginSearch').addEventListener('input', applyView);
        document.getElementById('pluginSort').addEventListener('change', applyView);
        document.getElementById('pluginFilter').addEventListener('change', applyView);

        function fmtSize(b) {
            if (!b && b !== 0) return '?';
            if (b >= 1024*1024*1024) return (b/1024/1024/1024).toFixed(1) + ' GB';
            if (b >= 1024*1024) return (b/1024/1024).toFixed(1) + ' MB';
            if (b >= 1024) return (b/1024).toFixed(1) + ' KB';
            return b + ' B';
        }
        function fmtDelta(d) {
            if (d === 0) return '0 B';
            var sign = d > 0 ? '+' : '-';
            return sign + fmtSize(Math.abs(d));
        }
        function fmtAgoShort(iso) {
            try {
                var diffMs = Date.now() - new Date(iso).getTime();
                var s = Math.floor(diffMs / 1000);
                if (s < 60) return s + 's ago';
                if (s < 3600) return Math.floor(s/60) + 'm ago';
                if (s < 86400) return Math.floor(s/3600) + 'h ago';
                return Math.floor(s/86400) + 'd ago';
            } catch(e) { return ''; }
        }

        // Build a rich success message about an updated plugin
        function plugMsg(item) {
            var fn = item.filename || '?';
            var os_ = item.old_size, ns = item.new_size, d = item.delta;
            if (item.unchanged || item.status === 'unchanged') return fn + ': identical to current (' + fmtSize(ns) + ')';
            if (os_ === 0) return 'Installed ' + fn + ' (' + fmtSize(ns) + ')';
            if (d === 0) return fn + ': content changed, same size (' + fmtSize(ns) + ')';
            return fn + ': ' + fmtSize(os_) + ' -> ' + fmtSize(ns) + ' (' + fmtDelta(d) + ')';
        }

        // Load and render update history
        function refreshHistory() {
            fetch('/api/plugins/history', { headers: { 'X-Requested-With': 'fetch' } })
                .then(function(r){ return r.json(); })
                .then(function(arr) {
                    var box = document.getElementById('historyList');
                    var title = document.getElementById('historyTitle');
                    box.innerHTML = '';
                    if (!arr.length) { title.style.display = 'none'; return; }
                    title.style.display = 'block';
                    // Show latest 15
                    arr.slice(0, 15).forEach(function(e) {
                        var row = document.createElement('div');
                        var rowCls = '';
                        if (e.status === 'failed' || e.status === 'error') rowCls = 'failed';
                        else if (e.status === 'unchanged') rowCls = 'unchanged';
                        else if (e.status === 'skipped') rowCls = 'skipped';
                        row.className = 'history-row ' + rowCls;
                        var time = document.createElement('span'); time.className = 'h-time';
                        time.textContent = (e.timestamp || '').replace('T', ' ').slice(0, 19);
                        row.appendChild(time);
                        var name = document.createElement('span'); name.className = 'h-name';
                        name.textContent = e.filename;
                        row.appendChild(name);
                        if (e.status === 'ok') {
                            var change = document.createElement('span'); change.className = 'h-change';
                            change.textContent = fmtSize(e.old_size) + ' -> ' + fmtSize(e.new_size);
                            row.appendChild(change);
                            var delta = document.createElement('span');
                            var d = e.delta || 0;
                            delta.className = 'h-delta ' + (d > 0 ? 'up' : d < 0 ? 'down' : 'zero');
                            delta.textContent = fmtDelta(d);
                            row.appendChild(delta);
                        } else if (e.status === 'unchanged') {
                            var unch = document.createElement('span');
                            unch.className = 'h-status unchanged';
                            unch.textContent = '\u2713 unchanged (' + fmtSize(e.new_size) + ')';
                            row.appendChild(unch);
                        } else {
                            var st = document.createElement('span');
                            st.className = 'h-status ' + (e.status === 'failed' || e.status === 'error' ? 'fail' : 'skip');
                            st.textContent = e.status.toUpperCase() + (e.error ? ' - ' + e.error : '');
                            row.appendChild(st);
                        }
                        box.appendChild(row);
                    });
                    // Mark cards that were updated in the last 24h
                    var recent = {};
                    arr.forEach(function(e) {
                        if (e.status !== 'ok') return;
                        if (recent[e.filename]) return;  // keep most recent
                        recent[e.filename] = e;
                    });
                    document.querySelectorAll('.plugin-card').forEach(function(card) {
                        // Find the file= hidden input to extract filename
                        var hidden = card.querySelector('input[name="file"]');
                        if (!hidden) return;
                        var fn = hidden.value;
                        // Remove old badge
                        var oldBadge = card.querySelector('.recent-badge');
                        if (oldBadge) oldBadge.remove();
                        var ent = recent[fn];
                        if (!ent) return;
                        var ageMs = Date.now() - new Date(ent.timestamp).getTime();
                        if (ageMs > 24*3600*1000) return;
                        var badge = document.createElement('span');
                        badge.className = 'recent-badge';
                        badge.textContent = 'Updated ' + fmtAgoShort(ent.timestamp);
                        var nameEl = card.querySelector('.plugin-name');
                        if (nameEl) nameEl.appendChild(badge);
                    });
                })
                .catch(function(){});
        }
        document.addEventListener('DOMContentLoaded', refreshHistory);

        // Update All — sequential, with one toast per plugin
        document.getElementById('updateAllBtn').addEventListener('click', function() {
            if (!confirm('Update all plugins with saved URLs? Each one will be downloaded in turn.')) return;
            var btn = this;
            btn.disabled = true;
            btn.textContent = 'Updating...';
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fetch('/api/plugins/update-all', {
                method: 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); })
              .then(function(res) {
                  btn.disabled = false;
                  btn.innerHTML = '&#x21BB; Update All';
                  if (!res.ok || !res.data) {
                      showToast('Update-all request failed', 'error');
                      return;
                  }
                  var items = res.data.items || [];
                  // Per-item toasts so each is individually readable
                  items.forEach(function(it, idx) {
                      setTimeout(function() {
                          if (it.status === 'ok') {
                              showToast(plugMsg(it), 'success', 12000);
                          } else if (it.status === 'unchanged') {
                              showToast(it.filename + ': identical to current (' + it.new_human + ')', 'info', 12000);
                          } else {
                              showToast(it.filename + ': ' + (it.reason || it.status), 'error', 12000);
                          }
                      }, idx * 250);
                  });
                  // Final summary
                  setTimeout(function() {
                      showToast(res.data.message, res.data.toast || 'success', 12000);
                  }, items.length * 250 + 100);
                  // Restart banner only if at least one file actually changed
                  if (res.data.restart_needed) {
                      document.getElementById('restartBanner').style.display = 'flex';
                  }
                  refreshHistory();
              }).catch(function(err) {
                  btn.disabled = false;
                  btn.innerHTML = '&#x21BB; Update All';
                  showToast('Network: ' + err, 'error');
              });
        });

        // Per-plugin update via AJAX
        document.querySelectorAll('form.plugin-url-form').forEach(function(form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                var fd = new FormData(form);
                var btn = form.querySelector('button');
                btn.disabled = true;
                btn.textContent = '...';
                fetch(form.action, {
                    method: 'POST',
                    body: fd,
                    headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
                }).then(function(r){ return r.json().then(function(d){ return {ok: r.ok, data: d}; }); })
                  .then(function(res) {
                      btn.disabled = false;
                      btn.textContent = 'Update';
                      if (res.ok && res.data && res.data.ok) {
                          var msg = res.data.filename ? plugMsg(res.data) : (res.data.message || 'Updated');
                          var toastType = res.data.unchanged ? 'info' : (res.data.toast || 'success');
                          showToast(msg, toastType, 12000);
                          // Skip restart banner if file was identical
                          if (!res.data.unchanged) {
                              document.getElementById('restartBanner').style.display = 'flex';
                          }
                          refreshHistory();
                      } else {
                          showToast((res.data && res.data.message) || 'Error', 'error', 12000);
                      }
                  }).catch(function(err) {
                      btn.disabled = false;
                      btn.textContent = 'Update';
                      showToast('Network: ' + err, 'error');
                  });
            });
        });

        // Restart from plugins banner
        document.getElementById('restartFromPluginsBtn').addEventListener('click', function() {
            if (!confirm('Restart the Minecraft server now?')) return;
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fetch('/api/restart', {
                method: 'POST', body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,data:d}; }); })
              .then(function(res) {
                  showToast((res.data && res.data.message) || 'Restarting...', 'warning');
              });
        });

        (function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();
    </script>
</body></html>
"""

PLAYERS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Players</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --yellow: #e7a33c; --red: #e74c3c; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --yellow: #d4a017; --red: #c0392b; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; display: inline-block; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; line-height: 1; }
        .player-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 12px; }
        .player-card { background: var(--bg2); border: 1px solid var(--border3); border-radius: 12px; padding: 16px; }
        .player-card.not-wl { border-left: 3px solid var(--yellow); opacity: 0.75; }
        .player-card.not-wl .player-name { color: var(--yellow); }
        .player-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .player-name { font-size: 1.15em; font-weight: 700; color: var(--accent); }
        .player-platform { font-size: 0.75em; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
        .platform-bedrock { background: #1b3a4b; color: var(--blue); }
        .platform-java { background: #1b4332; color: var(--accent); }
        .player-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.85em; }
        .stat-row { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid var(--border3); }
        .stat-label { color: var(--text2); }
        .stat-value { color: var(--text); font-family: monospace; }
        .stat-value.rej { color: var(--red); font-weight: 600; }
        .stat-value.play { color: var(--accent); font-weight: 600; }
        .player-ips { margin-top: 6px; font-size: 0.8em; color: var(--text2); }
        .player-ips code { background: var(--bg3); padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
        .player-count { color: var(--text2); font-size: 0.95em; margin-bottom: 16px; }
        .section-title { color: var(--accent); font-size: 1.15em; margin: 20px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border3); }
        .section-title.others { color: var(--text3); font-size: 1em; margin-top: 30px; }
        .wl-badge { font-size: 0.7em; padding: 1px 6px; border-radius: 3px; background: #1b4332; color: var(--accent); margin-left: 6px; }

        /* Skin heads */
        .skin-head { width: 32px; height: 32px; image-rendering: pixelated; border-radius: 4px; vertical-align: middle; margin-right: 8px; background: var(--bg3); }
        .skin-head-sm { width: 20px; height: 20px; image-rendering: pixelated; border-radius: 3px; vertical-align: middle; background: var(--bg3); }
        .player-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .player-header .player-name { display: flex; align-items: center; gap: 6px; flex: 1; }

        .player-chart-link { display: inline-block; margin-top: 8px; font-size: 0.78em; color: var(--blue); text-decoration: none; padding: 3px 8px; border: 1px solid var(--blue); border-radius: 4px; }
        .player-chart-link:hover { background: #1b3a4b; }

        /* Player action buttons */
        .player-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
        .player-action-btn { background: var(--bg3); color: var(--text); border: 1px solid var(--border2); padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.78em; }
        .player-action-btn:hover { background: var(--accent); color: var(--bg); border-color: var(--accent); }

        /* Modal dialog */
        .modal-backdrop { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
        .modal-backdrop.show { display: flex; }
        .modal { background: var(--bg2); border: 1px solid var(--border3); border-radius: 12px; padding: 20px 22px; max-width: 460px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
        .modal h3 { color: var(--accent); margin-bottom: 14px; font-size: 1.1em; display: flex; align-items: center; gap: 8px; }
        .modal label { display: block; color: var(--text2); font-size: 0.85em; margin-top: 12px; margin-bottom: 4px; }
        .modal input[type="text"] { width: 100%; background: var(--bg3); color: var(--text); border: 1px solid var(--border2); padding: 8px 12px; border-radius: 6px; font-size: 0.95em; box-sizing: border-box; }
        .modal .modal-help { font-size: 0.78em; color: var(--text3); margin-top: 4px; }
        .modal .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px; flex-wrap: wrap; }
        .modal .modal-btn { padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.9em; border: 1px solid var(--border2); background: var(--bg3); color: var(--text); }
        .modal .modal-btn.primary { background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 600; }
        .modal .modal-btn.danger { background: var(--red); color: #fff; border-color: var(--red); }
        .modal .modal-btn:hover { opacity: 0.85; }
        .modal-tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid var(--border2); }
        .modal-tab { padding: 8px 14px; cursor: pointer; color: var(--text2); border-bottom: 2px solid transparent; font-size: 0.9em; }
        .modal-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
        .modal-tab:hover { color: var(--text); }
        .modal-section { display: none; }
        .modal-section.active { display: block; }
        .coord-row { display: flex; gap: 6px; }
        .coord-row input { flex: 1; }
        .preset-btns { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
        .preset-btn { background: var(--bg3); color: var(--blue); border: 1px solid var(--blue); padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.78em; }
        .preset-btn:hover { background: #1b3a4b; }

        /* Toast */
        #toastContainer { position: fixed; bottom: 24px; right: 24px; display: flex; flex-direction: column; gap: 10px; z-index: 9999; max-width: 360px; pointer-events: none; }
        .toast { pointer-events: auto; padding: 12px 16px; border-radius: 8px; font-size: 0.9em; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: flex; align-items: flex-start; gap: 10px; }
        .toast.toast-success { background: #2d8f6f; }
        .toast.toast-error { background: #c0392b; }
        .toast.toast-warning { background: #d4a017; color: #1a1a2e; }
        .toast.toast-info { background: #2980b9; }
        .toast .toast-close { background: none; border: none; color: inherit; cursor: pointer; font-size: 1.2em; line-height: 1; opacity: 0.7; padding: 0; margin-left: auto; }

        @media (max-width: 600px) { body { padding: 12px; } .player-grid { grid-template-columns: 1fr; } .player-stats { grid-template-columns: 1fr; } }
    </style>
    <script>
        function toggleTheme() { var h=document.documentElement,n=h.getAttribute('data-theme')==='dark'?'light':'dark'; h.setAttribute('data-theme',n); document.cookie='theme='+n+';path=/;max-age=31536000'; document.getElementById('themeIcon').innerHTML=n==='dark'?'&#x2600;':'&#x1F319;'; }
        (function(){var m=document.cookie.match(/theme=(dark|light)/);if(m)document.documentElement.setAttribute('data-theme',m[1]);})();
    </script>
</head>
<body>
    <div class="header">
        <div><h1>Players</h1><div class="subtitle">Whitelisted players and statistics</div></div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/charts" class="btn">&#x1F4CA; Charts</a>
            <a href="/plugins" class="btn">&#x1F9E9; Plugins</a>
            <a href="/backups" class="btn">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>
    <div class="player-count">__PLAYER_COUNT__ whitelisted players</div>
    __PLAYER_SECTIONS__

    <div id="toastContainer" aria-live="polite"></div>

    <!-- Action modal (Teleport / Nick) -->
    <div class="modal-backdrop" id="actionModal">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
            <h3 id="modalTitle">&#x2699;&#xFE0F; <span id="modalPlayerName">Player</span></h3>
            <div class="modal-tabs">
                <div class="modal-tab" data-tab="teleport" onclick="switchModalTab('teleport')">&#x1F4CD; Teleport</div>
                <div class="modal-tab" data-tab="nick" onclick="switchModalTab('nick')">&#x270F;&#xFE0F; Nickname</div>
            </div>
            <div class="modal-section" id="teleportSection">
                <label>To player (leave empty to use coordinates):</label>
                <input type="text" id="tpTarget" placeholder="e.g. Petar4o">
                <div class="modal-help">If filled, target player's location will be used.</div>

                <label style="margin-top:14px;">Or coordinates (X Y Z):</label>
                <div class="coord-row">
                    <input type="text" id="tpX" placeholder="X">
                    <input type="text" id="tpY" placeholder="Y">
                    <input type="text" id="tpZ" placeholder="Z">
                </div>
                <div class="modal-help">Use <code>~</code> for relative (e.g. <code>~ ~10 ~</code> = 10 blocks up).</div>

                <div class="preset-btns" id="locationPresets">
                    <!-- Filled dynamically from /api/locations -->
                    <button type="button" class="preset-btn" onclick="setCoords('~','~50','~')">&#x2191; Up 50</button>
                </div>
                <div class="bookmark-add" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;">
                    <input type="text" id="bookmarkName" placeholder="Bookmark name..." maxlength="30" style="flex:1;min-width:120px;">
                    <button type="button" class="modal-btn" onclick="saveBookmark()" style="background:var(--blue);color:#fff;border-color:var(--blue);">Save current X/Y/Z as bookmark</button>
                </div>
                <div class="modal-help">Saved bookmarks appear as buttons above and persist across all players.</div>
            </div>
            <div class="modal-section" id="nickSection">
                <label>New nickname (1-24 chars):</label>
                <input type="text" id="nickValue" placeholder="e.g. Ivancho" maxlength="24">
                <div class="modal-help">Letters, digits, spaces, dash and underscore. Empty / Reset removes the nickname.</div>
            </div>
            <div class="modal-actions">
                <button type="button" class="modal-btn" onclick="closeModal()">Cancel</button>
                <button type="button" class="modal-btn danger" id="modalSecondaryBtn" onclick="modalSecondary()" style="display:none;">Reset</button>
                <button type="button" class="modal-btn primary" id="modalPrimaryBtn" onclick="modalSubmit()">Apply</button>
            </div>
        </div>
    </div>

    <script>
        var CSRF_TOKEN = '__CSRF__';

        // Toast helper
        function showToast(msg, type) {
            type = type || 'info';
            var c = document.getElementById('toastContainer');
            if (!c) return;
            var t = document.createElement('div');
            t.className = 'toast toast-' + type;
            t.innerHTML = '<span></span><button class="toast-close" type="button">&#x2715;</button>';
            t.firstChild.textContent = msg;
            t.querySelector('.toast-close').addEventListener('click', function(){ t.remove(); });
            c.appendChild(t);
            setTimeout(function() { if (t.parentNode) t.remove(); }, 6000);
        }

        // Modal logic
        var modalState = { player: '', tab: 'teleport' };

        function openTeleport(name) { openModal(name, 'teleport'); }
        function openNick(name) { openModal(name, 'nick'); }

        function openModal(name, tab) {
            modalState.player = name;
            document.getElementById('modalPlayerName').textContent = name;
            document.getElementById('tpTarget').value = '';
            document.getElementById('tpX').value = '';
            document.getElementById('tpY').value = '';
            document.getElementById('tpZ').value = '';
            document.getElementById('nickValue').value = '';
            switchModalTab(tab);
            document.getElementById('actionModal').classList.add('show');
        }

        function closeModal() {
            document.getElementById('actionModal').classList.remove('show');
        }

        function switchModalTab(tab) {
            modalState.tab = tab;
            document.querySelectorAll('.modal-tab').forEach(function(el) {
                el.classList.toggle('active', el.dataset.tab === tab);
            });
            document.getElementById('teleportSection').classList.toggle('active', tab === 'teleport');
            document.getElementById('nickSection').classList.toggle('active', tab === 'nick');
            document.getElementById('modalSecondaryBtn').style.display = (tab === 'nick') ? 'inline-block' : 'none';
            document.getElementById('modalSecondaryBtn').textContent = 'Reset nickname';
        }

        function setCoords(x, y, z) {
            document.getElementById('tpX').value = x;
            document.getElementById('tpY').value = y;
            document.getElementById('tpZ').value = z;
        }

        // Location bookmarks — load and render as preset buttons
        function loadBookmarks() {
            fetch('/api/locations', { headers: { 'X-Requested-With': 'fetch' } })
                .then(function(r){ return r.json(); })
                .then(function(arr) {
                    var box = document.getElementById('locationPresets');
                    if (!box) return;
                    // Keep the "Up 50" button (last) and replace anything before it
                    box.innerHTML = '';
                    arr.forEach(function(loc) {
                        var wrap = document.createElement('span');
                        wrap.style.cssText = 'display:inline-flex;align-items:center;gap:2px;';
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'preset-btn';
                        btn.textContent = '\u2691 ' + loc.name + ' (' + loc.coords + ')';
                        btn.onclick = function() {
                            var p = loc.coords.split(/[ ]+/);
                            if (p.length === 3) setCoords(p[0], p[1], p[2]);
                        };
                        var del = document.createElement('button');
                        del.type = 'button';
                        del.className = 'preset-btn';
                        del.style.cssText = 'padding:2px 6px;color:var(--red);border-color:var(--red);';
                        del.textContent = '\u2715';
                        del.title = 'Delete bookmark';
                        del.onclick = function() { removeBookmark(loc.name); };
                        wrap.appendChild(btn);
                        wrap.appendChild(del);
                        box.appendChild(wrap);
                    });
                    // Always add the relative "Up 50" preset
                    var up = document.createElement('button');
                    up.type = 'button';
                    up.className = 'preset-btn';
                    up.textContent = '\u2191 Up 50';
                    up.onclick = function() { setCoords('~', '~50', '~'); };
                    box.appendChild(up);
                })
                .catch(function(){});
        }

        function saveBookmark() {
            var name = (document.getElementById('bookmarkName').value || '').trim();
            var x = document.getElementById('tpX').value.trim();
            var y = document.getElementById('tpY').value.trim();
            var z = document.getElementById('tpZ').value.trim();
            if (!name) { showToast('Enter a bookmark name', 'error'); return; }
            if (!x || !y || !z) { showToast('Fill in X/Y/Z first', 'error'); return; }
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fd.append('name', name);
            fd.append('coords', x + ' ' + y + ' ' + z);
            fetch('/api/locations/add', {
                method: 'POST', body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,data:d}; }); })
              .then(function(res) {
                  if (res.ok && res.data && res.data.ok) {
                      showToast(res.data.message, 'success');
                      document.getElementById('bookmarkName').value = '';
                      loadBookmarks();
                  } else {
                      showToast((res.data && res.data.message) || 'Error', 'error');
                  }
              }).catch(function(err){ showToast('Network: ' + err, 'error'); });
        }

        function removeBookmark(name) {
            if (!confirm('Delete bookmark "' + name + '"?')) return;
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fd.append('name', name);
            fetch('/api/locations/remove', {
                method: 'POST', body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,data:d}; }); })
              .then(function(res) {
                  if (res.ok && res.data && res.data.ok) {
                      showToast(res.data.message, 'success');
                      loadBookmarks();
                  } else {
                      showToast((res.data && res.data.message) || 'Error', 'error');
                  }
              }).catch(function(err){ showToast('Network: ' + err, 'error'); });
        }

        // Load bookmarks once when page is ready (so first modal open already has them)
        document.addEventListener('DOMContentLoaded', loadBookmarks);

        function modalSubmit() {
            if (modalState.tab === 'teleport') {
                var target = document.getElementById('tpTarget').value.trim();
                var x = document.getElementById('tpX').value.trim();
                var y = document.getElementById('tpY').value.trim();
                var z = document.getElementById('tpZ').value.trim();
                var fd = new FormData();
                fd.append('csrf_token', CSRF_TOKEN);
                fd.append('name', modalState.player);
                if (target) {
                    fd.append('target', target);
                } else if (x || y || z) {
                    fd.append('coords', x + ' ' + y + ' ' + z);
                } else {
                    showToast('Provide a target player or coordinates', 'error');
                    return;
                }
                postAction('/api/teleport', fd);
            } else if (modalState.tab === 'nick') {
                var nick = document.getElementById('nickValue').value.trim();
                if (!nick) {
                    showToast('Enter a nickname (or use Reset to clear)', 'error');
                    return;
                }
                var fd = new FormData();
                fd.append('csrf_token', CSRF_TOKEN);
                fd.append('name', modalState.player);
                fd.append('nick', nick);
                postAction('/api/nick', fd);
            }
        }

        function modalSecondary() {
            if (modalState.tab !== 'nick') return;
            if (!confirm('Clear nickname for ' + modalState.player + '?')) return;
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fd.append('name', modalState.player);
            fd.append('reset', '1');
            postAction('/api/nick', fd);
        }

        function postAction(url, fd) {
            fetch(url, {
                method: 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r) {
                return r.json().then(function(data) { return { ok: r.ok, data: data }; });
            }).then(function(res) {
                if (res.ok && res.data && res.data.ok) {
                    showToast(res.data.message || 'OK', res.data.toast || 'success');
                    closeModal();
                } else {
                    showToast((res.data && res.data.message) || 'Error', 'error');
                }
            }).catch(function(err) {
                showToast('Network error: ' + err, 'error');
            });
        }

        // Backdrop click + Escape to close
        document.addEventListener('DOMContentLoaded', function() {
            var backdrop = document.getElementById('actionModal');
            if (backdrop) {
                backdrop.addEventListener('click', function(e) {
                    if (e.target === backdrop) closeModal();
                });
            }
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeModal();
            });
        });

        (function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();
    </script>
</body></html>
"""

# ----------------------------------------------------------------------------
# Backup details — full file listing for the /backups page
# ----------------------------------------------------------------------------
def get_backups_list():
    """Return [{filename, size_bytes, size_human, mtime, age_human, path}, ...]
    sorted newest-first."""
    backups = []
    try:
        for path in sorted(glob.glob(os.path.join(BACKUP_DIR, 'world-*.tar.gz'))):
            try:
                st = os.stat(path)
                mtime = datetime.fromtimestamp(st.st_mtime)
                age = datetime.now() - mtime
                backups.append({
                    'filename': os.path.basename(path),
                    'size_bytes': st.st_size,
                    'size_human': format_size(st.st_size),
                    'mtime': mtime.strftime('%Y-%m-%d %H:%M'),
                    'mtime_iso': mtime.isoformat(),
                    'age_seconds': int(age.total_seconds()),
                    'age_human': format_duration(int(age.total_seconds())),
                })
            except OSError:
                log.exception("could not stat backup %s", path)
    except Exception:
        log.exception("backup listing failed")
    return list(reversed(backups))  # newest first

@app.route('/backups')
@requires_auth
def backups_page():
    backups = get_backups_list()
    msg = request.args.get('msg', '')
    msg_html = f'<div class="msg-box">{esc(msg)}</div>' if msg else ''
    csrf = get_csrf_token()

    # Aggregate stats
    total_size = sum(b['size_bytes'] for b in backups)
    avg_size = total_size // len(backups) if backups else 0
    newest = backups[0] if backups else None
    oldest = backups[-1] if backups else None

    # Status line color (mirrors dashboard widget rules)
    status_html = ''
    if not backups:
        status_html = '<div class="backup-status-line bad">No backups yet!</div>'
    else:
        age_h = newest['age_seconds'] / 3600
        if age_h > 48:
            status_html = f'<div class="backup-status-line bad">Last backup is {age_h/24:.1f} days old!</div>'
        elif age_h > 30:
            status_html = f'<div class="backup-status-line warn">Last backup is {age_h:.1f}h old.</div>'
        else:
            status_html = f'<div class="backup-status-line ok">Last backup {newest["age_human"]} ago.</div>'

    # World size now (live)
    world_size = 0
    for w in ('world', 'world_nether', 'world_the_end'):
        wp = os.path.join(WORLD_DIR, w)
        if os.path.exists(wp):
            try:
                world_size += get_dir_size(wp)
            except Exception:
                log.exception("world size compute failed for %s", wp)

    # Backup deltas (size growth between consecutive backups, if 2+ exist)
    rows = []
    sorted_old_to_new = list(reversed(backups))
    prev_size = None
    for b in sorted_old_to_new:
        delta = ''
        delta_class = ''
        if prev_size is not None:
            d = b['size_bytes'] - prev_size
            sign = '+' if d > 0 else ''
            delta = f'{sign}{format_size(abs(d)) if d else "0 B"}'
            if d > 0:
                delta_class = 'value good'
            elif d < 0:
                delta_class = 'value warn'
                delta = f'-{format_size(abs(d))}'
        prev_size = b['size_bytes']
        b['delta'] = delta
        b['delta_class'] = delta_class
    # Display in newest-first order
    for b in backups:
        rows.append(b)

    cards = ''
    for b in rows:
        delta_html = f'<span class="{b["delta_class"]}">{esc(b["delta"])}</span>' if b['delta'] else '<span class="value">&mdash;</span>'
        cards += f"""<tr>
            <td><code>{esc(b['filename'])}</code></td>
            <td>{esc(b['size_human'])}</td>
            <td>{delta_html}</td>
            <td>{esc(b['mtime'])}</td>
            <td>{esc(b['age_human'])} ago</td>
        </tr>"""
    if not cards:
        cards = '<tr><td colspan="5" style="text-align:center;color:var(--text3);padding:30px;">No backup files found in ' + esc(BACKUP_DIR) + '</td></tr>'

    summary = (
        f'<div class="backup-summary">'
        f'<div class="bkstat"><span class="bkstat-label">Backups</span><span class="bkstat-value">{len(backups)}</span></div>'
        f'<div class="bkstat"><span class="bkstat-label">Total size</span><span class="bkstat-value">{esc(format_size(total_size))}</span></div>'
        f'<div class="bkstat"><span class="bkstat-label">Avg size</span><span class="bkstat-value">{esc(format_size(avg_size)) if backups else "—"}</span></div>'
        f'<div class="bkstat"><span class="bkstat-label">World size</span><span class="bkstat-value">{esc(format_size(world_size))}</span></div>'
        f'<div class="bkstat"><span class="bkstat-label">Newest</span><span class="bkstat-value">{esc(newest["mtime"]) if newest else "—"}</span></div>'
        f'<div class="bkstat"><span class="bkstat-label">Oldest</span><span class="bkstat-value">{esc(oldest["mtime"]) if oldest else "—"}</span></div>'
        f'</div>'
    )

    html = BACKUPS_TEMPLATE.replace('__FAVICON__', FAVICON)
    html = html.replace('__CSRF__', csrf)
    html = html.replace('__MSG__', msg_html)
    html = html.replace('__SUMMARY__', summary)
    html = html.replace('__STATUS__', status_html)
    html = html.replace('__ROWS__', cards)
    html = html.replace('__BACKUP_DIR__', esc(BACKUP_DIR))
    html = html.replace('__VERSION__', VERSION)
    return html

BACKUPS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Backups</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --yellow: #e7a33c; --red: #e74c3c; --tag-join-bg: #1b4332; --tag-reject-bg: #3d1111; --tag-gdiscon-bg: #3d2911; --msg-bg: #1b3a4b; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --yellow: #d4a017; --red: #c0392b; --tag-join-bg: #d5f5e3; --tag-reject-bg: #fadbd8; --tag-gdiscon-bg: #fcf3cf; --msg-bg: #d6eaf8; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 20px; font-size: 1em; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; display: inline-block; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; line-height: 1; }
        .msg-box { background: var(--msg-bg); border: 1px solid var(--blue); border-radius: 8px; padding: 10px 16px; margin-bottom: 16px; color: var(--blue); font-size: 0.95em; }

        .backup-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
        .bkstat { background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; }
        .bkstat-label { color: var(--text2); font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.5px; }
        .bkstat-value { color: var(--text); font-size: 1.15em; font-weight: 600; font-family: monospace; }

        .backup-status-line { padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 0.95em; }
        .backup-status-line.ok { background: var(--tag-join-bg); color: var(--accent); border: 1px solid var(--accent); }
        .backup-status-line.warn { background: var(--tag-gdiscon-bg); color: var(--yellow); border: 1px solid var(--yellow); }
        .backup-status-line.bad { background: var(--tag-reject-bg); color: var(--red); border: 1px solid var(--red); }

        table { width: 100%; border-collapse: collapse; background: var(--bg2); border-radius: 12px; overflow: hidden; }
        th, td { padding: 10px 12px; text-align: left; font-size: 0.9em; }
        thead { background: var(--bg3); }
        thead th { color: var(--accent); font-weight: 600; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; }
        tbody tr { border-top: 1px solid var(--border3); }
        tbody tr:hover { background: rgba(255,255,255,0.02); }
        td code { color: var(--blue); font-size: 0.85em; word-break: break-all; }
        .value { font-family: monospace; }
        .value.good { color: var(--accent); }
        .value.warn { color: var(--yellow); }
        .value.bad { color: var(--red); }

        .backup-dir-info { color: var(--text3); font-size: 0.82em; margin-top: 16px; padding: 10px 12px; background: var(--bg2); border-radius: 8px; }
        .backup-dir-info code { color: var(--blue); }
    </style>
    <script>(function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.documentElement.setAttribute('data-theme',t);})();
        function toggleTheme() { var h=document.documentElement; var n=h.getAttribute('data-theme')==='dark'?'light':'dark'; h.setAttribute('data-theme',n); document.cookie='theme='+n+';path=/;max-age=31536000'; document.getElementById('themeIcon').innerHTML=n==='dark'?'&#x2600;':'&#x1F319;'; }
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>&#x1F4BE; Backups</h1>
            <div class="subtitle">World archives in __BACKUP_DIR__</div>
        </div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/charts" class="btn">&#x1F4CA; Charts</a>
            <a href="/plugins" class="btn">&#x1F9E9; Plugins</a>
            <a href="/players" class="btn">&#x1F465; Players</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>
    __MSG__
    __STATUS__
    __SUMMARY__
    <table>
        <thead>
            <tr><th>Filename</th><th>Size</th><th>&Delta; vs prev</th><th>Created</th><th>Age</th></tr>
        </thead>
        <tbody>__ROWS__</tbody>
    </table>
    <div class="backup-dir-info">
        Backups are created by the host's backup cron job (outside this app). To restore a backup:
        stop the server (<code>docker compose down</code>), extract the chosen tarball into the world directory, then start again.
        <br>v__VERSION__
    </div>
    <script>(function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();</script>
</body>
</html>
"""

# ----------------------------------------------------------------------------
# Logs page
# ----------------------------------------------------------------------------
@app.route('/logs')
@requires_auth
def logs_page():
    html = LOGS_TEMPLATE.replace('__FAVICON__', FAVICON)
    html = html.replace('__VERSION__', VERSION)
    return html

LOGS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Logs</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --yellow: #e7a33c; --red: #e74c3c; --info-bg: #1b3a4b; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --yellow: #d4a017; --red: #c0392b; --info-bg: #d6eaf8; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 16px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; }

        .log-toolbar { background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .log-toolbar input, .log-toolbar select { background: var(--bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 12px; border-radius: 6px; font-size: 0.9em; }
        .log-toolbar input[type=search] { flex: 1; min-width: 180px; }
        .log-toolbar label { color: var(--text2); font-size: 0.85em; }
        .log-toolbar .auto-refresh { display: inline-flex; align-items: center; gap: 4px; color: var(--text2); font-size: 0.85em; cursor: pointer; }
        .log-toolbar .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text3); transition: background 0.2s; }
        .log-toolbar .live-dot.on { background: var(--accent); animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }

        .log-stats { color: var(--text3); font-size: 0.8em; margin-bottom: 8px; }
        .log-box { background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 0; max-height: 70vh; overflow-y: auto; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 0.78em; line-height: 1.45; }
        .log-line { padding: 3px 12px; border-bottom: 1px solid var(--border3); white-space: pre-wrap; word-break: break-word; display: flex; gap: 10px; }
        .log-line:last-child { border-bottom: none; }
        .log-line.lvl-WARN { background: rgba(231,163,60,0.07); border-left: 2px solid var(--yellow); }
        .log-line.lvl-ERROR { background: rgba(231,76,60,0.10); border-left: 2px solid var(--red); }
        .log-line.lvl-INFO { border-left: 2px solid transparent; }
        .log-time { color: var(--text3); white-space: nowrap; min-width: 145px; font-size: 0.92em; }
        .log-level { display: inline-block; min-width: 56px; padding: 0 6px; border-radius: 3px; text-align: center; font-weight: 600; font-size: 0.92em; }
        .log-level.INFO { color: var(--blue); }
        .log-level.WARN { color: var(--yellow); }
        .log-level.ERROR { color: var(--red); }
        .log-text { color: var(--text); flex: 1; }
        .log-text mark { background: var(--yellow); color: #000; padding: 0 2px; border-radius: 2px; }
        .empty { color: var(--text3); text-align: center; padding: 30px; font-style: italic; font-family: -apple-system, sans-serif; }

        @media (max-width: 600px) { body { padding: 12px; } .log-time { min-width: 90px; } .log-line { font-size: 0.7em; } }
    </style>
    <script>
        (function(){var m=document.cookie.match(/theme=(dark|light)/);if(m)document.documentElement.setAttribute('data-theme',m[1]);})();
        function toggleTheme() { var h=document.documentElement,n=h.getAttribute('data-theme')==='dark'?'light':'dark'; h.setAttribute('data-theme',n); document.cookie='theme='+n+';path=/;max-age=31536000'; document.getElementById('themeIcon').innerHTML=n==='dark'?'&#x2600;':'&#x1F319;'; }
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>&#x1F4DC; Server Logs</h1>
            <div class="subtitle">Tail of <code>docker logs minecraft</code></div>
        </div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/charts" class="btn">&#x1F4CA; Charts</a>
            <a href="/plugins" class="btn">&#x1F9E9; Plugins</a>
            <a href="/players" class="btn">&#x1F465; Players</a>
            <a href="/backups" class="btn">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>

    <div class="log-toolbar">
        <input type="search" id="logSearch" placeholder="Search (substring)..." autocomplete="off">
        <label>Level:</label>
        <select id="logLevel">
            <option value="">All</option>
            <option value="INFO">INFO+</option>
            <option value="WARN">WARN+</option>
            <option value="ERROR">ERROR only</option>
        </select>
        <label>Tail:</label>
        <select id="logTail">
            <option value="100">100</option>
            <option value="200" selected>200</option>
            <option value="500">500</option>
            <option value="1000">1000</option>
            <option value="2000">2000 (max)</option>
        </select>
        <button class="btn" onclick="loadLogs()" style="padding:7px 14px;font-size:0.85em;">Refresh</button>
        <label class="auto-refresh">
            <input type="checkbox" id="autoRefresh">
            <span class="live-dot" id="liveDot"></span>
            <span>Live (5s)</span>
        </label>
    </div>

    <div class="log-stats" id="logStats"></div>
    <div class="log-box" id="logBox"><div class="empty">Loading...</div></div>

    <script>
        var autoTimer = null;

        function escapeHtml(s) {
            return String(s)
                .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
        }
        function highlightSearch(text, query) {
            if (!query) return escapeHtml(text);
            var safe = escapeHtml(text);
            var qSafe = query.replace(/[-/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&');
            try {
                var re = new RegExp('(' + qSafe + ')', 'gi');
                return safe.replace(re, '<mark>$1</mark>');
            } catch(e) {
                return safe;
            }
        }

        function loadLogs() {
            var params = new URLSearchParams();
            params.set('tail', document.getElementById('logTail').value);
            var lvl = document.getElementById('logLevel').value;
            if (lvl) params.set('level', lvl);
            var search = document.getElementById('logSearch').value;
            if (search) params.set('search', search);

            return fetch('/api/logs?' + params.toString(), { headers: { 'X-Requested-With': 'fetch' } })
                .then(function(r){ return r.json(); })
                .then(function(d) {
                    var box = document.getElementById('logBox');
                    var stats = document.getElementById('logStats');
                    var lines = d.lines || [];
                    if (!lines.length) {
                        box.innerHTML = '<div class="empty">No matching log lines</div>';
                        stats.textContent = 'Scanned ' + (d.total_scanned || 0) + ' lines, no matches.';
                        return;
                    }
                    var atBottom = (box.scrollTop + box.clientHeight >= box.scrollHeight - 40);
                    var html = '';
                    lines.forEach(function(line) {
                        var time = line.ts ? line.ts.replace('T', ' ').slice(0, 19) : '';
                        var level = line.level || 'INFO';
                        html += '<div class="log-line lvl-' + escapeHtml(level) + '">';
                        html += '<span class="log-time">' + escapeHtml(time) + '</span>';
                        html += '<span class="log-level ' + escapeHtml(level) + '">' + escapeHtml(level) + '</span>';
                        html += '<span class="log-text">' + highlightSearch(line.text, search) + '</span>';
                        html += '</div>';
                    });
                    box.innerHTML = html;
                    stats.textContent = 'Showing ' + lines.length + ' of ' + (d.total_scanned || 0) + ' tailed lines'
                        + (lvl ? ' (level >= ' + lvl + ')' : '')
                        + (search ? ' matching "' + search + '"' : '');
                    // Stick to bottom only if user was already there
                    if (atBottom) box.scrollTop = box.scrollHeight;
                })
                .catch(function(err) {
                    document.getElementById('logBox').innerHTML = '<div class="empty">Error: ' + escapeHtml(String(err)) + '</div>';
                });
        }

        document.getElementById('logSearch').addEventListener('input', debounce(loadLogs, 300));
        document.getElementById('logLevel').addEventListener('change', loadLogs);
        document.getElementById('logTail').addEventListener('change', loadLogs);
        document.getElementById('autoRefresh').addEventListener('change', function() {
            var dot = document.getElementById('liveDot');
            if (this.checked) {
                dot.classList.add('on');
                if (autoTimer) clearInterval(autoTimer);
                autoTimer = setInterval(loadLogs, 5000);
            } else {
                dot.classList.remove('on');
                if (autoTimer) clearInterval(autoTimer);
                autoTimer = null;
            }
        });

        function debounce(fn, ms) {
            var t = null;
            return function() {
                clearTimeout(t);
                t = setTimeout(fn, ms);
            };
        }

        // Initial load + scroll to bottom
        loadLogs().then(function() {
            var box = document.getElementById('logBox');
            box.scrollTop = box.scrollHeight;
        });

        (function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();
    </script>
</body>
</html>
"""

# ----------------------------------------------------------------------------
# Chat page
# ----------------------------------------------------------------------------
@app.route('/chat')
@requires_auth
def chat_page():
    csrf = get_csrf_token()
    html = CHAT_TEMPLATE.replace('__FAVICON__', FAVICON)
    html = html.replace('__CSRF__', csrf)
    html = html.replace('__VERSION__', VERSION)
    return html

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Chat</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --yellow: #e7a33c; --red: #e74c3c; --info-bg: #1b3a4b; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --yellow: #d4a017; --red: #c0392b; --info-bg: #d6eaf8; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; font-size: 15px; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        .subtitle { color: var(--text2); margin-bottom: 16px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; }

        .chat-toolbar { background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .chat-toolbar input, .chat-toolbar select { background: var(--bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 12px; border-radius: 6px; font-size: 0.9em; }
        .chat-toolbar input[type=search] { flex: 1; min-width: 180px; }
        .chat-toolbar label { color: var(--text2); font-size: 0.85em; }
        .chat-toolbar .auto-refresh { display: inline-flex; align-items: center; gap: 4px; color: var(--text2); font-size: 0.85em; cursor: pointer; }
        .chat-toolbar .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text3); }
        .chat-toolbar .live-dot.on { background: var(--accent); animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }

        .chat-stats { color: var(--text3); font-size: 0.82em; margin-bottom: 8px; }
        .chat-box { background: var(--bg2); border: 1px solid var(--border3); border-radius: 10px; padding: 8px; max-height: 65vh; min-height: 300px; overflow-y: auto; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 0.88em; line-height: 1.55; }
        .chat-line { padding: 3px 8px; border-radius: 4px; word-break: break-word; }
        .chat-line:hover { background: var(--bg3); }
        .chat-line .chat-day { display: block; color: var(--text3); font-size: 0.8em; margin: 12px 0 4px; padding: 3px 6px; border-bottom: 1px solid var(--border3); font-family: -apple-system, sans-serif; }
        .chat-line .chat-time { color: var(--text3); font-size: 0.85em; margin-right: 8px; }
        .chat-line .chat-sender { color: var(--blue); font-weight: 700; margin-right: 4px; }
        .chat-line.kind-server .chat-sender { color: var(--yellow); }
        .chat-line .chat-text { color: var(--text); }
        .chat-line .chat-text mark { background: var(--yellow); color: #000; padding: 0 2px; border-radius: 2px; }
        .empty { color: var(--text3); text-align: center; padding: 40px; font-style: italic; font-family: -apple-system, sans-serif; }

        .send-form { display: flex; gap: 6px; margin-top: 14px; }
        .send-form input { flex: 1; background: var(--bg2); color: var(--text); border: 1px solid var(--border2); padding: 10px 14px; border-radius: 8px; font-size: 0.95em; }
        .send-form button { background: var(--accent); color: var(--bg); border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 0.95em; font-weight: 700; }
        .send-form button:hover { opacity: 0.85; }
        .send-help { font-size: 0.78em; color: var(--text3); margin-top: 4px; }

        #toastContainer { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 9999; max-width: 360px; pointer-events: none; }
        .toast { pointer-events: auto; padding: 12px 16px; border-radius: 8px; font-size: 0.9em; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: flex; align-items: flex-start; gap: 10px; }
        .toast.toast-success { background: #2d8f6f; }
        .toast.toast-error { background: #c0392b; }
        .toast.toast-info { background: #2980b9; }
        .toast .toast-close { background: none; border: none; color: inherit; cursor: pointer; font-size: 1.2em; line-height: 1; opacity: 0.7; padding: 0; margin-left: auto; }

        @media (max-width: 600px) { body { padding: 12px; } .chat-line { font-size: 0.78em; } }
    </style>
    <script>
        var CSRF_TOKEN = '__CSRF__';
        (function(){var m=document.cookie.match(/theme=(dark|light)/);if(m)document.documentElement.setAttribute('data-theme',m[1]);})();
        function toggleTheme() { var h=document.documentElement,n=h.getAttribute('data-theme')==='dark'?'light':'dark'; h.setAttribute('data-theme',n); document.cookie='theme='+n+';path=/;max-age=31536000'; document.getElementById('themeIcon').innerHTML=n==='dark'?'&#x2600;':'&#x1F319;'; }
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>&#x1F4AC; In-game Chat</h1>
            <div class="subtitle">Player and server messages — persisted history</div>
        </div>
        <div class="header-btns">
            <a href="/" class="btn">&#x2190; Dashboard</a>
            <a href="/charts" class="btn">&#x1F4CA; Charts</a>
            <a href="/players" class="btn">&#x1F465; Players</a>
            <a href="/plugins" class="btn">&#x1F9E9; Plugins</a>
            <a href="/backups" class="btn">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>

    <div class="chat-toolbar">
        <input type="search" id="chatSearch" placeholder="Search messages..." autocomplete="off">
        <label>Range:</label>
        <select id="chatRange">
            <option value="60">Last hour</option>
            <option value="360">Last 6 hours</option>
            <option value="1440" selected>Last 24 hours</option>
            <option value="10080">Last 7 days</option>
            <option value="43200">Last 30 days</option>
            <option value="129600">Last 90 days</option>
        </select>
        <label>Sender:</label>
        <select id="chatSender">
            <option value="">Any</option>
            <option value="players">Players only</option>
            <option value="server">Server only</option>
        </select>
        <button class="btn" onclick="loadChat()" style="padding:7px 14px;font-size:0.85em;">Refresh</button>
        <label class="auto-refresh">
            <input type="checkbox" id="autoRefresh" checked>
            <span class="live-dot on" id="liveDot"></span>
            <span>Live (5s)</span>
        </label>
    </div>

    <div class="chat-stats" id="chatStats"></div>
    <div class="chat-box" id="chatBox"><div class="empty">Loading...</div></div>

    <form class="send-form" id="sendForm">
        <input type="text" id="chatInput" placeholder="Type a message to broadcast as [Server]..." maxlength="200" autocomplete="off">
        <button type="submit">&#x27A4; Send</button>
    </form>
    <div class="send-help">Sent via <code>/say</code> — visible in-game as <code>[Server] message</code>. Max 200 chars.</div>

    <div id="toastContainer"></div>

    <script>
        var autoTimer = null;
        var allMessages = [];

        function showToast(msg, type) {
            type = type || 'info';
            var c = document.getElementById('toastContainer');
            var t = document.createElement('div');
            t.className = 'toast toast-' + type;
            t.innerHTML = '<span></span><button class="toast-close" type="button">&#x2715;</button>';
            t.firstChild.textContent = msg;
            t.querySelector('.toast-close').addEventListener('click', function(){ t.remove(); });
            c.appendChild(t);
            setTimeout(function(){ if (t.parentNode) t.remove(); }, 6000);
        }

        function escapeHtml(s) {
            return String(s)
                .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
        }
        function highlightSearch(text, q) {
            if (!q) return escapeHtml(text);
            var safe = escapeHtml(text);
            var qSafe = q.replace(/[-/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&');
            try {
                return safe.replace(new RegExp('(' + qSafe + ')', 'gi'), '<mark>$1</mark>');
            } catch(e) { return safe; }
        }

        function dayLabel(iso) {
            // 'YYYY-MM-DDTHH:MM:SS' -> 'YYYY-MM-DD'
            return (iso || '').slice(0, 10);
        }

        function render() {
            var box = document.getElementById('chatBox');
            var stats = document.getElementById('chatStats');
            var search = (document.getElementById('chatSearch').value || '').trim().toLowerCase();
            var senderFilter = document.getElementById('chatSender').value;

            var filtered = allMessages.filter(function(m) {
                if (senderFilter === 'players' && m.kind === 'server') return false;
                if (senderFilter === 'server' && m.kind !== 'server') return false;
                if (search) {
                    var hay = ((m.sender || '') + ' ' + (m.text || '')).toLowerCase();
                    if (hay.indexOf(search) < 0) return false;
                }
                return true;
            });

            stats.textContent = 'Showing ' + filtered.length + ' of ' + allMessages.length + ' messages'
                + (search ? ' matching "' + search + '"' : '')
                + (senderFilter ? ' (' + senderFilter + ')' : '');

            if (!filtered.length) {
                box.innerHTML = '<div class="empty">No messages</div>';
                return;
            }
            var atBottom = (box.scrollTop + box.clientHeight >= box.scrollHeight - 40);
            var html = '';
            var lastDay = null;
            filtered.forEach(function(m) {
                var d = dayLabel(m.timestamp || '');
                if (d !== lastDay) {
                    html += '<div class="chat-day">' + escapeHtml(d) + '</div>';
                    lastDay = d;
                }
                html += '<div class="chat-line kind-' + escapeHtml(m.kind || 'chat') + '">';
                html += '<span class="chat-time">' + escapeHtml(m.time || '') + '</span>';
                html += '<span class="chat-sender">&lt;' + escapeHtml(m.sender || '') + '&gt;</span>';
                html += '<span class="chat-text">' + highlightSearch(m.text || '', search) + '</span>';
                html += '</div>';
            });
            box.innerHTML = html;
            if (atBottom) box.scrollTop = box.scrollHeight;
        }

        function loadChat() {
            var minutes = document.getElementById('chatRange').value;
            return fetch('/api/chat?minutes=' + encodeURIComponent(minutes) + '&limit=5000',
                         { headers: { 'X-Requested-With': 'fetch' } })
                .then(function(r){ return r.json(); })
                .then(function(d) {
                    allMessages = d.messages || [];
                    render();
                })
                .catch(function(err) {
                    document.getElementById('chatBox').innerHTML = '<div class="empty">Error: ' + escapeHtml(String(err)) + '</div>';
                });
        }

        function debounce(fn, ms) {
            var t = null;
            return function() { clearTimeout(t); t = setTimeout(fn, ms); };
        }

        document.getElementById('chatSearch').addEventListener('input', debounce(render, 200));
        document.getElementById('chatSender').addEventListener('change', render);
        document.getElementById('chatRange').addEventListener('change', loadChat);

        document.getElementById('autoRefresh').addEventListener('change', function() {
            var dot = document.getElementById('liveDot');
            if (this.checked) {
                dot.classList.add('on');
                if (!autoTimer) autoTimer = setInterval(loadChat, 5000);
            } else {
                dot.classList.remove('on');
                if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
            }
        });

        document.getElementById('sendForm').addEventListener('submit', function(e) {
            e.preventDefault();
            var input = document.getElementById('chatInput');
            var text = (input.value || '').trim();
            if (!text) return;
            var fd = new FormData();
            fd.append('csrf_token', CSRF_TOKEN);
            fd.append('text', text);
            fetch('/api/chat/send', {
                method: 'POST', body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
            }).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,data:d}; }); })
              .then(function(res) {
                  if (res.ok && res.data && res.data.ok) {
                      input.value = '';
                      // Pause briefly to let logger pick it up, then refresh
                      setTimeout(loadChat, 6000);
                      showToast('Message sent — will appear after next log scan (~5s)', 'success');
                  } else {
                      showToast((res.data && res.data.message) || 'Error', 'error');
                  }
              }).catch(function(err) { showToast('Network: ' + err, 'error'); });
        });

        // Initial load + start live polling
        loadChat().then(function() {
            var box = document.getElementById('chatBox');
            box.scrollTop = box.scrollHeight;
        });
        autoTimer = setInterval(loadChat, 5000);

        (function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();
    </script>
</body>
</html>
"""

@app.route('/plugins')
@requires_auth
def plugins_page():
    plugins = get_plugins_list()
    msg = request.args.get('msg', '')
    msg_html = f'<div class="msg-box">{esc(msg)}</div>' if msg else ''
    csrf = get_csrf_token()
    plugins_dir = os.path.join(WORLD_DIR, 'plugins')

    # Compute status + size_bytes for each plugin
    has_url_count = 0
    no_url_count = 0
    no_jar_count = 0
    total_size = 0
    for p in plugins:
        fname = p.get('file', '?')
        size_bytes = 0
        if fname and fname != '?':
            jar_path = os.path.join(plugins_dir, fname)
            if os.path.exists(jar_path):
                try:
                    size_bytes = os.path.getsize(jar_path)
                    total_size += size_bytes
                except OSError:
                    log.exception("plugin getsize failed for %s", fname)
            else:
                p['_jar_missing'] = True
        else:
            p['_jar_missing'] = True
        p['_size_bytes'] = size_bytes
        if p.get('_jar_missing'):
            p['_status'] = 'no-jar'
            no_jar_count += 1
        elif p.get('url'):
            p['_status'] = 'has-url'
            has_url_count += 1
        else:
            p['_status'] = 'no-url'
            no_url_count += 1

    # Stats line
    stats_html = (
        f'<span class="pill">Total: <strong>{len(plugins)}</strong></span>'
        f'<span class="pill ok">With URL: <strong>{has_url_count}</strong></span>'
        f'<span class="pill warn">No URL: <strong>{no_url_count}</strong></span>'
    )
    if no_jar_count:
        stats_html += f'<span class="pill bad">JAR missing: <strong>{no_jar_count}</strong></span>'
    stats_html += f'<span class="pill">Disk: <strong>{esc(format_size(total_size))}</strong></span>'

    cards = ''
    for p in sorted(plugins, key=lambda x: x['name'].lower()):
        url_val = p.get('url', '')
        status = p['_status']
        status_label = {'has-url': '&#x2713; URL set', 'no-url': '&#x26A0; no URL', 'no-jar': '&#x2716; no JAR'}[status]
        status_class = {'has-url': 'ok', 'no-url': 'warn', 'no-jar': 'bad'}[status]
        cards += f"""<div class="plugin-card {esc(status)}" data-name="{esc(p['name'].lower())}" data-size="{int(p['_size_bytes'])}" data-status="{esc(status)}">
            <div class="plugin-name">{esc(p['name'])}<span class="plugin-status {status_class}">{status_label}</span></div>
            <span class="plugin-version">v{esc(p['version'])}</span>
            <div class="plugin-meta">{esc(p.get('file', '?'))} &mdash; {esc(p.get('size', '?'))}</div>
            <form method="POST" action="/api/plugins/update" class="plugin-url plugin-url-form">
                <input type="hidden" name="csrf_token" value="{csrf}">
                <input type="hidden" name="file" value="{esc(p.get('file', ''))}">
                <input type="text" name="url" value="{esc(url_val)}" placeholder="Download URL...">
                <button type="submit" class="btn btn-update">Update</button>
            </form>
        </div>"""
    if not cards:
        cards = '<div style="color:var(--text3);text-align:center;padding:40px;">No plugins found</div>'
    html = PLUGINS_TEMPLATE.replace('__FAVICON__', FAVICON)
    html = html.replace('__CSRF__', csrf)
    html = html.replace('__MSG__', msg_html)
    html = html.replace('__STATS__', stats_html)
    html = html.replace('__PLUGIN_CARDS__', cards)
    html = html.replace('__PLUGIN_COUNT__', str(len(plugins)))
    return html

@app.route('/players')
@requires_auth
def players_page():
    events = load_events()
    nicknames = get_nicknames()
    wl_players = get_whitelist()
    wl_names = set(name for _, name in wl_players)

    def is_whitelisted(name):
        """Check whitelist with both dot and non-dot versions"""
        if name in wl_names:
            return True
        if name.startswith('.') and name[1:] in wl_names:
            return True
        if not name.startswith('.') and f'.{name}' in wl_names:
            return True
        return False

    stats = get_player_stats(events, nicknames)
    # Add whitelisted players that haven't joined yet
    seen_names = set(s['name'] for s in stats)
    for ptype, name in wl_players:
        if name not in seen_names:
            stats.append({
                'name': name, 'display': format_player_name(name, nicknames),
                'joins': 0, 'leaves': 0, 'rejected': 0,
                'ips': [], 'rejected_ips': [],
                'first_seen': '', 'last_seen': '', 'last_rejected': '',
                'platform': 'Bedrock' if ptype == 'bedrock' else 'Java',
                'session_count': 0, 'total_seconds': 0, 'avg_seconds': 0, 'longest_seconds': 0,
            })

    def build_player_card(p, is_whitelisted=False):
        platform_class = 'platform-bedrock' if p['platform'] == 'Bedrock' else 'platform-java'
        wl_badge = '<span class="wl-badge">WL</span>' if is_whitelisted else ''
        card_class = 'player-card' if is_whitelisted else 'player-card not-wl'
        first = p['first_seen'].replace('T', ' ')[:16] if p['first_seen'] else 'Never'
        last = p['last_seen'].replace('T', ' ')[:16] if p['last_seen'] else 'Never'
        last_rej = p.get('last_rejected', '').replace('T', ' ')[:16] if p.get('last_rejected') else ''
        skin = skin_url(p['name'], 32)

        # Session stats rows
        session_rows = ''
        if p.get('session_count', 0) > 0:
            session_rows = (
                f'<div class="stat-row"><span class="stat-label">Total play</span>'
                f'<span class="stat-value play">{esc(format_duration(p["total_seconds"]))}</span></div>'
                f'<div class="stat-row"><span class="stat-label">Sessions</span>'
                f'<span class="stat-value">{int(p["session_count"])}</span></div>'
                f'<div class="stat-row"><span class="stat-label">Avg session</span>'
                f'<span class="stat-value">{esc(format_duration(p["avg_seconds"]))}</span></div>'
                f'<div class="stat-row"><span class="stat-label">Longest</span>'
                f'<span class="stat-value">{esc(format_duration(p["longest_seconds"]))}</span></div>'
            )

        rejected_row = ''
        if p.get('rejected', 0) > 0:
            rejected_row = f'<div class="stat-row"><span class="stat-label">Rejected</span><span class="stat-value rej">{int(p["rejected"])}</span></div>'
            if last_rej:
                rejected_row += f'<div class="stat-row"><span class="stat-label">Last reject</span><span class="stat-value rej">{esc(last_rej)}</span></div>'

        # Combine join IPs and reject IPs for display
        all_ips = list(p.get('ips', []))
        for ip in p.get('rejected_ips', []):
            if ip not in all_ips:
                all_ips.append(ip)
        ips_html = ''
        if all_ips:
            ips_html = '<div class="player-ips">IPs: ' + ' '.join(f'<code>{esc(ip)}</code>' for ip in all_ips) + '</div>'

        # Per-player playtime chart link (only if there's data)
        chart_link = ''
        if p.get('session_count', 0) > 0:
            chart_link = (
                f'<a class="player-chart-link" href="/charts?player={esc(p["name"])}" '
                f'title="Playtime chart">&#x1F4CA; chart</a>'
            )

        # Action buttons (teleport, nick) — only for players that have actually joined
        actions_html = ''
        if p.get('joins', 0) > 0:
            name_attr = esc(p['name'])
            actions_html = f"""<div class="player-actions">
                <button class="player-action-btn" data-name="{name_attr}" onclick="openTeleport(this.dataset.name)" title="Teleport this player">&#x1F4CD; Teleport</button>
                <button class="player-action-btn" data-name="{name_attr}" onclick="openNick(this.dataset.name)" title="Set or clear nickname">&#x270F;&#xFE0F; Nick</button>
            </div>"""

        return f"""<div class="{card_class}">
            <div class="player-header">
                <img class="skin-head" src="{skin}" alt="" loading="lazy" onerror="this.style.display='none'">
                <span class="player-name">{esc(p['display'])}{wl_badge}</span>
                <span class="player-platform {platform_class}">{esc(p['platform'])}</span>
            </div>
            <div class="player-stats">
                <div class="stat-row"><span class="stat-label">Joins</span><span class="stat-value">{int(p['joins'])}</span></div>
                <div class="stat-row"><span class="stat-label">Leaves</span><span class="stat-value">{int(p['leaves'])}</span></div>
                {session_rows}
                <div class="stat-row"><span class="stat-label">First seen</span><span class="stat-value">{esc(first)}</span></div>
                <div class="stat-row"><span class="stat-label">Last seen</span><span class="stat-value">{esc(last)}</span></div>
                {rejected_row}
            </div>
            {ips_html}
            {chart_link}
            {actions_html}
        </div>"""

    # Separate: players who joined at least once OR are whitelisted go to top
    # Others (scanners, rejected-only) go to bottom, sorted by rejection count desc
    player_cards = ''
    other_list = []
    player_count = 0
    for p in stats:
        is_wl = is_whitelisted(p['name'])
        has_joined = p['joins'] > 0
        if is_wl or has_joined:
            player_cards += build_player_card(p, is_wl)
            player_count += 1
        else:
            other_list.append(p)
    # Sort "Other Connections" by rejection count, most aggressive first
    other_list.sort(key=lambda x: x.get('rejected', 0), reverse=True)
    other_cards = ''.join(build_player_card(p, False) for p in other_list)

    sections = ''
    if player_cards:
        sections += f'<h2 class="section-title">Players ({player_count})</h2><div class="player-grid">{player_cards}</div>'
    else:
        sections += '<div style="color:var(--text3);text-align:center;padding:20px;">No players found</div>'
    if other_cards:
        sections += f'<h2 class="section-title others">Other Connections</h2><div class="player-grid">{other_cards}</div>'

    html = PLAYERS_TEMPLATE.replace('__FAVICON__', FAVICON)
    html = html.replace('__CSRF__', get_csrf_token())
    html = html.replace('__PLAYER_SECTIONS__', sections)
    html = html.replace('__PLAYER_COUNT__', str(len(wl_names)))
    return html

# --- Main Page ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Access Log</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] {
            --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --bg-hover: #1a2744;
            --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3;
            --border: #1a1a2e; --border2: #333; --border3: #1e3050;
            --red: #e74c3c; --blue: #48bfe3; --yellow: #e7a33c;
            --bar-bg: #0f1829; --row-rejected-bg: #2a1015; --row-rejected-hover: #351520;
            --input-bg: #16213e; --tag-join-bg: #1b4332; --tag-leave-bg: #2d2d44;
            --tag-reject-bg: #3d1111; --tag-geyser-bg: #1b3a4b; --tag-gdiscon-bg: #3d2911;
            --chart-from: #0f3460; --chart-to: #4ecca3;
            --alert-bg: #3d1111; --alert-border: #e74c3c;
            --msg-bg: #1b3a4b;
        }
        :root[data-theme="light"] {
            --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --bg-hover: #e3e8ef;
            --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f;
            --border: #e0e0e0; --border2: #ccc; --border3: #ddd;
            --red: #c0392b; --blue: #2980b9; --yellow: #d4a017;
            --bar-bg: #e8ecf1; --row-rejected-bg: #fde8e8; --row-rejected-hover: #fad4d4;
            --input-bg: #fff; --tag-join-bg: #d4edda; --tag-leave-bg: #e2e3e5;
            --tag-reject-bg: #f8d7da; --tag-geyser-bg: #d1ecf1; --tag-gdiscon-bg: #fff3cd;
            --chart-from: #b0c4de; --chart-to: #2d8f6f;
            --alert-bg: #fde8e8; --alert-border: #c0392b;
            --msg-bg: #d1ecf1;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 24px; padding-bottom: 90px; font-size: 15px; transition: background 0.3s, color 0.3s; }
        h1 { color: var(--accent); margin-bottom: 5px; font-size: 1.6em; }
        h2 { color: var(--accent); font-size: 1.1em; margin-bottom: 10px; }
        .subtitle { color: var(--text2); margin-bottom: 20px; font-size: 1em; }
        .filters { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
        .filters select, .filters input { background: var(--input-bg); color: var(--text); border: 1px solid var(--border2); padding: 9px 14px; border-radius: 6px; font-size: 0.95em; }
        .filters input { width: 180px; }
        .stats { display: flex; gap: 15px; margin-bottom: 18px; flex-wrap: wrap; }
        .stat-box { background: var(--bg2); padding: 12px 18px; border-radius: 8px; border-left: 3px solid var(--accent); }
        .stat-box.rejected { border-left-color: var(--red); }
        .stat-box.players { border-left-color: var(--blue); }
        .stat-num { font-size: 1.5em; font-weight: bold; color: var(--accent); }
        .stat-box.rejected .stat-num { color: var(--red); }
        .stat-box.players .stat-num { color: var(--blue); }
        .stat-label { font-size: 0.85em; color: var(--text2); margin-top: 2px; }
        table { width: 100%; border-collapse: collapse; background: var(--bg2); border-radius: 8px; overflow: hidden; }
        th { background: var(--bg3); padding: 12px 16px; text-align: left; font-size: 0.95em; color: var(--accent); position: sticky; top: 0; }
        td { padding: 10px 16px; border-bottom: 1px solid var(--border); font-size: 0.95em; }
        tr.row-JOIN { border-left: 3px solid var(--accent); }
        tr.row-LEAVE { border-left: 3px solid var(--text3); }
        tr.row-REJECTED { background: var(--row-rejected-bg); border-left: 3px solid var(--red); }
        tr.row-GEYSER_CONNECT { border-left: 3px solid var(--blue); }
        tr.row-GEYSER_DISCONNECT { border-left: 3px solid var(--yellow); }
        tr:hover { background: var(--bg-hover); }
        tr.row-REJECTED:hover { background: var(--row-rejected-hover); }
        .tag { padding: 3px 10px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }
        .tag-JOIN { background: var(--tag-join-bg); color: var(--accent); }
        .tag-LEAVE { background: var(--tag-leave-bg); color: var(--text2); }
        .tag-REJECTED { background: var(--tag-reject-bg); color: var(--red); }
        .tag-GEYSER_CONNECT { background: var(--tag-geyser-bg); color: var(--blue); }
        .tag-GEYSER_DISCONNECT { background: var(--tag-gdiscon-bg); color: var(--yellow); }
        .btn { color: var(--accent); text-decoration: none; font-size: 0.95em; padding: 8px 16px; border: 1px solid var(--accent); border-radius: 6px; cursor: pointer; background: transparent; display: inline-block; }
        .btn:hover { background: var(--accent); color: var(--bg); }
        .btn.disabled { color: var(--text3); border-color: var(--text3); pointer-events: none; }
        .btn-danger { color: var(--red); border-color: var(--red); }
        .btn-danger:hover { background: var(--red); color: #fff; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
        .header-btns { display: flex; gap: 8px; align-items: center; }
        .empty { text-align: center; padding: 20px; color: var(--text3); }
        .ip { color: var(--text); font-family: monospace; }
        .reason { color: var(--red); }
        .pagination { display: flex; gap: 8px; margin-top: 18px; justify-content: center; align-items: center; flex-wrap: wrap; }
        .page-info { color: var(--text2); font-size: 0.95em; }
        .online-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-right: 5px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .theme-toggle { background: var(--bg2); border: 1px solid var(--border2); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 1.1em; line-height: 1; }
        .theme-toggle:hover { background: var(--bg3); }

        .alert-box { position: relative; background: var(--alert-bg); border: 1px solid var(--alert-border); border-radius: 8px; padding: 12px 36px 12px 16px; margin-bottom: 18px; }
        .alert-item { color: var(--red); font-size: 0.95em; padding: 4px 0; }
        .alert-close { position: absolute; top: 8px; right: 8px; background: transparent; border: none; color: var(--red); cursor: pointer; font-size: 1em; padding: 4px 8px; border-radius: 4px; opacity: 0.7; line-height: 1; }
        .alert-close:hover { background: rgba(0,0,0,0.1); opacity: 1; }
        .msg-box { background: var(--msg-bg); border: 1px solid var(--blue); border-radius: 8px; padding: 10px 16px; margin-bottom: 18px; color: var(--blue); font-size: 0.95em; }
        .onboarding-box { background: var(--tag-gdiscon-bg); border: 1px solid var(--yellow); border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; color: var(--yellow); font-size: 0.95em; display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
        .onboarding-box strong { color: var(--yellow); }
        .onboarding-box .countdown { font-family: monospace; font-weight: 700; }

        .panels { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; margin-bottom: 18px; }
        .panel { background: var(--bg2); border-radius: 8px; padding: 16px; }
        .chart { display: flex; align-items: flex-end; gap: 3px; height: 120px; margin-top: 12px; }
        .chart-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
        .chart-bar { background: linear-gradient(to top, var(--chart-from), var(--chart-to)); border-radius: 3px 3px 0 0; width: 100%; min-height: 2px; display: flex; align-items: flex-start; justify-content: center; }
        .chart-bar.daily { background: linear-gradient(to top, #0f3460, #48bfe3); }
        .chart-val { font-size: 0.65em; color: #fff; margin-top: 2px; }
        .chart-label { font-size: 0.7em; color: var(--text3); margin-top: 4px; }

        .top-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); }
        .top-rank { width: 30px; text-align: center; }
        .top-name { width: 160px; font-size: 0.9em; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .top-bar-bg { flex: 1; height: 8px; background: var(--bar-bg); border-radius: 4px; overflow: hidden; }
        .top-bar-fill { height: 100%; background: linear-gradient(to right, var(--chart-from), var(--chart-to)); border-radius: 4px; }
        .top-count { width: 30px; text-align: right; font-size: 0.9em; color: var(--accent); font-weight: 600; }

        .online-list { margin-top: 6px; }
        .online-player { display: inline-flex; align-items: center; gap: 5px; background: var(--tag-geyser-bg); color: var(--blue); padding: 3px 10px 3px 5px; border-radius: 12px; font-size: 0.85em; margin: 3px 4px 3px 0; }

        /* Skin heads (mc-heads.net) */
        .skin-head { width: 32px; height: 32px; image-rendering: pixelated; border-radius: 4px; vertical-align: middle; margin-right: 8px; background: var(--bg3); }
        .skin-head-sm { width: 20px; height: 20px; image-rendering: pixelated; border-radius: 3px; vertical-align: middle; background: var(--bg3); }
        .player-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
        .player-header .player-name { display: flex; align-items: center; gap: 6px; flex: 1; }
        .player-chart-link { display: inline-block; margin-top: 8px; font-size: 0.78em; color: var(--blue); text-decoration: none; padding: 3px 8px; border: 1px solid var(--blue); border-radius: 4px; }
        .player-chart-link:hover { background: var(--tag-geyser-bg); }

        /* (Player action buttons + modal moved to /players page) */

        /* Toast notification system */
        #toastContainer { position: fixed; bottom: 60px; right: 24px; display: flex; flex-direction: column; gap: 10px; z-index: 9999; max-width: 360px; pointer-events: none; }
        .toast { pointer-events: auto; padding: 12px 16px; border-radius: 8px; font-size: 0.9em; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.3); animation: slideIn 0.25s ease-out; display: flex; align-items: flex-start; gap: 10px; }
        .toast.toast-success { background: #2d8f6f; }
        .toast.toast-error { background: #c0392b; }
        .toast.toast-warning { background: #d4a017; color: #1a1a2e; }
        .toast.toast-info { background: #2980b9; }
        .toast .toast-close { background: none; border: none; color: inherit; cursor: pointer; font-size: 1.2em; line-height: 1; opacity: 0.7; padding: 0; margin-left: auto; }
        .toast .toast-close:hover { opacity: 1; }
        .toast.toast-fade-out { animation: fadeOut 0.3s forwards; }
        @keyframes slideIn { from { transform: translateX(120%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes fadeOut { to { transform: translateX(120%); opacity: 0; } }

        /* Backup widget */
        .backup-widget { background: var(--bg2); border: 1px solid var(--border3); border-radius: 12px; padding: 14px 16px; margin-top: 12px; }
        .backup-widget h3 { color: var(--accent); margin-bottom: 10px; font-size: 1em; display: flex; align-items: center; gap: 6px; }
        .backup-widget .backup-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.88em; }
        .backup-widget .backup-row .label { color: var(--text2); }
        .backup-widget .backup-row .value { color: var(--text); font-family: monospace; }
        .backup-widget .backup-row .value.warn { color: var(--yellow); }
        .backup-widget .backup-row .value.bad { color: var(--red); }
        .backup-widget .backup-row .value.good { color: var(--accent); }
        .backup-status-line { margin-top: 8px; padding: 6px 10px; border-radius: 4px; font-size: 0.82em; display: none; }
        .backup-status-line.warn { display: block; background: var(--tag-gdiscon-bg); color: var(--yellow); }
        .backup-status-line.bad { display: block; background: var(--tag-reject-bg); color: var(--red); }

        /* Whitelist panel */
        .wl-add { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
        .wl-add input { background: var(--input-bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 12px; border-radius: 6px; font-size: 0.9em; flex: 1; min-width: 100px; }
        .wl-add select { background: var(--input-bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 8px; border-radius: 6px; font-size: 0.9em; }
        .wl-add button { background: var(--accent); color: var(--bg); border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em; font-weight: 600; }
        .wl-add button:hover { opacity: 0.85; }
        .wl-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 0.9em; }
        .wl-name { color: var(--text); display: inline-flex; align-items: center; gap: 5px; }
        .wl-remove { background: none; border: none; color: var(--red); cursor: pointer; font-size: 1.1em; padding: 2px 6px; border-radius: 4px; }
        .wl-remove:hover { background: var(--tag-reject-bg); }
        .wl-list { max-height: 220px; overflow-y: auto; }
        .platform-hint { font-size: 0.75em; padding: 3px 8px; border-radius: 4px; margin-top: 4px; display: inline-block; }
        .platform-hint.java { background: var(--tag-join-bg); color: var(--accent); }
        .platform-hint.bedrock { background: var(--tag-geyser-bg); color: var(--blue); }
        .platform-hint.unknown { background: var(--tag-leave-bg); color: var(--text3); }
        .platform-hint.checking { background: var(--tag-leave-bg); color: var(--text2); font-style: italic; }

        .status-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--bar-bg); border-top: 1px solid var(--border3); padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px; z-index: 100; }
        .status-items { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
        .status-item { display: flex; align-items: center; gap: 4px; font-size: 0.8em; color: var(--text2); }
        .status-item .label { color: var(--text3); }
        .status-item .value { color: var(--text); font-family: monospace; }
        .status-item .value.good { color: var(--accent); }
        .status-item .value.warn { color: var(--yellow); }
        .status-item .value.bad { color: var(--red); }
        .status-item .value.online { color: var(--accent); }
        .status-item .value.offline { color: var(--red); }
        .status-sep { color: var(--border3); }
        .status-version { color: var(--text3); font-size: 0.75em; }

        @media (max-width: 900px) { .panels { grid-template-columns: 1fr; } }
        @media (max-width: 768px) {
            body { padding: 12px; padding-bottom: 120px; font-size: 14px; }
            .stats { gap: 8px; }
            .stat-box { padding: 8px 12px; flex: 1; }
            .stat-num { font-size: 1.2em; }
            .filters input { width: 140px; }
            th, td { padding: 8px 10px; font-size: 0.85em; }
            h1 { font-size: 1.3em; }
            .top-name { width: 100px; }
            .chart { height: 80px; }
            .status-bar { padding: 6px 12px; }
            .status-item { font-size: 0.7em; }
            .status-sep { display: none; }
            th:nth-child(4), td:nth-child(4), th:nth-child(5), td:nth-child(5) { display: none; }
        }
        @media (max-width: 480px) {
            .stat-box { flex: 1 1 45%; }
            .online-list { display: none; }
        }
    </style>
    <script>
        var CSRF_TOKEN = '__CSRF__';
        function _addCsrf(form) {
            var i = document.createElement('input');
            i.type = 'hidden'; i.name = 'csrf_token'; i.value = CSRF_TOKEN;
            form.appendChild(i);
        }
        function toggleTheme() {
            var html = document.documentElement;
            var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            document.cookie = 'theme=' + next + ';path=/;max-age=31536000';
            document.getElementById('themeIcon').innerHTML = next === 'dark' ? '&#x2600;' : '&#x1F319;';
        }
        function removePlayer(name) {
            if (confirm('Remove ' + name + ' from whitelist?')) {
                var form = document.createElement('form');
                form.method = 'POST';
                form.action = '/api/whitelist/remove';
                _addCsrf(form);
                var input = document.createElement('input');
                input.type = 'hidden'; input.name = 'name'; input.value = name;
                form.appendChild(input);
                document.body.appendChild(form);
                form.submit();
            }
        }
        function restartServer() {
            if (confirm('Are you sure you want to restart the Minecraft server?')) {
                var form = document.createElement('form');
                form.method = 'POST';
                form.action = '/api/restart';
                _addCsrf(form);
                document.body.appendChild(form);
                form.submit();
            }
        }
        function wlToggle(state) {
            if (state === 'off' && !confirm('Turn off whitelist? Anyone can join!')) return;
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = '/api/whitelist/toggle';
            _addCsrf(form);
            var input = document.createElement('input');
            input.type = 'hidden'; input.name = 'state'; input.value = state;
            form.appendChild(input);
            document.body.appendChild(form);
            form.submit();
        }
        function dismissAlert() {
            var box = document.getElementById('alertBox');
            if (!box) return;
            var sig = box.getAttribute('data-sig');
            // 24h cookie tied to current set of flagged IPs
            document.cookie = 'alertDismissed=' + sig + ';path=/;max-age=86400;SameSite=Lax';
            box.style.display = 'none';
        }
        (function() {
            var match = document.cookie.match(/theme=(dark|light)/);
            if (match) document.documentElement.setAttribute('data-theme', match[1]);
            // Hide alert if dismissed and IP signature unchanged
            document.addEventListener('DOMContentLoaded', function() {
                var box = document.getElementById('alertBox');
                if (box) {
                    var sig = box.getAttribute('data-sig');
                    var m = document.cookie.match(/alertDismissed=([^;]+)/);
                    if (m && m[1] === sig) box.style.display = 'none';
                }
                // Live countdown for onboarding banner: ticks every second
                // and forces a page refresh shortly before the deadline so the
                // server-side state machine can finalize.
                var ob = document.getElementById('onboardingBox');
                var span = document.getElementById('obCountdown');
                if (ob && span) {
                    var remaining = parseInt(ob.getAttribute('data-deadline'), 10) || 0;
                    var t = setInterval(function() {
                        remaining -= 1;
                        if (remaining <= 0) {
                            clearInterval(t);
                            location.reload();
                            return;
                        }
                        // Refresh sooner if player is likely to be connecting:
                        // every 15s while waiting, so we don't miss the JOIN.
                        if (remaining % 15 === 0) {
                            location.reload();
                            return;
                        }
                        var mm = Math.floor(remaining / 60);
                        var ss = remaining % 60;
                        span.textContent = mm + ':' + (ss < 10 ? '0' : '') + ss;
                    }, 1000);
                }
            });
        })();
    </script>
</head>
<body>
    <div class="header">
        <div>
            <h1>Minecraft Access Log</h1>
            <div class="subtitle"><span class="online-dot"></span>Family Server &mdash; Live (refresh in <span id="countdown">5</span>s)</div>
        </div>
        <div class="header-btns">
            <button class="btn btn-danger" onclick="restartServer()" title="Restart Minecraft" style="margin-right:8px;">&#x21BB; Restart</button>
            <a href="/charts" class="btn" title="Charts">&#x1F4CA; Charts</a>
            <a href="/plugins" class="btn" title="Plugins">&#x1F9E9; Plugins</a>
            <a href="/players" class="btn" title="Players">&#x1F465; Players</a>
            <a href="/backups" class="btn" title="Backups">&#x1F4BE; Backups</a>
            <a href="/logs" class="btn">&#x1F4DC; Logs</a>
            <a href="/chat" class="btn">&#x1F4AC; Chat</a>
            <a href="__CURRENT_URL__" class="btn">Refresh</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>

    __MSG__
    __ALERTS__
    __ONBOARDING__

    <div class="stats">
        <div class="stat-box players">
            <div class="stat-num"><span id="liveOnline">__PLAYERS_ONLINE__</span> / <span id="liveMax">__PLAYERS_MAX__</span></div>
            <div class="stat-label">Online Now</div>
            <div class="online-list" id="liveOnlineList">__ONLINE_PLAYERS_LIST__</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">__TOTAL_JOINS__</div>
            <div class="stat-label">Total Joins</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">__UNIQUE_PLAYERS__</div>
            <div class="stat-label">Unique Players</div>
        </div>
        <div class="stat-box rejected">
            <div class="stat-num">__TOTAL_REJECTED__</div>
            <div class="stat-label">Rejected</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" id="liveEvents">__TOTAL_EVENTS__</div>
            <div class="stat-label">Total Events</div>
        </div>
    </div>

    <div class="panels">
        <div class="panel">
            <h2>Activity (Last 14 Days)</h2>
            <div class="chart">__DAILY_CHART__</div>
        </div>
        <div class="panel">
            <h2>Top Players</h2>
            <div style="margin-top:12px;">__TOP_PLAYERS__</div>
        </div>
        <div class="panel">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h2>Whitelist (__WL_COUNT__)</h2>
                <div style="display:flex;gap:6px;">
                    <button class="btn" onclick="wlToggle('on')" style="padding:4px 10px;font-size:0.8em;">ON</button>
                    <button class="btn btn-danger" onclick="wlToggle('off')" style="padding:4px 10px;font-size:0.8em;">OFF</button>
                </div>
            </div>
            <div class="wl-add" style="margin-top:10px;">
                <form id="wlAddForm" method="POST" action="/api/whitelist/add" style="display:flex;gap:6px;flex-wrap:wrap;width:100%;">
                    <input type="hidden" name="csrf_token" value="__CSRF__">
                    <input type="text" id="wlAddName" name="name" placeholder="Player name (no dot)..." required>
                    <select name="type" id="wlAddType">
                        <option value="auto">Auto</option>
                        <option value="bedrock">Bedrock</option>
                        <option value="java">Java</option>
                    </select>
                    <button type="submit">+ Add</button>
                </form>
            </div>
            <details style="margin:6px 0 0 0;">
                <summary style="cursor:pointer;color:var(--yellow);font-size:0.82em;padding:4px 0;">+ Onboard new player (auto-disable whitelist, wait, auto-add)</summary>
                <form id="onboardForm" method="POST" action="/api/whitelist/onboard" style="display:flex;gap:6px;flex-wrap:wrap;width:100%;margin-top:6px;">
                    <input type="hidden" name="csrf_token" value="__CSRF__">
                    <input type="text" id="onboardName" name="name" placeholder="Player name (no dot)..." required style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 12px;border-radius:6px;font-size:0.9em;flex:2;min-width:100px;">
                    <select name="platform" id="onboardPlatform" style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 8px;border-radius:6px;font-size:0.9em;">
                        <option value="auto">Auto</option>
                        <option value="bedrock">Bedrock</option>
                        <option value="java">Java</option>
                    </select>
                    <input type="number" name="duration" value="5" min="1" max="30" title="Minutes to keep whitelist OFF" style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 8px;border-radius:6px;font-size:0.9em;width:60px;">
                    <button type="submit" style="background:var(--yellow);color:#000;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:0.9em;font-weight:600;">Open &amp; Wait</button>
                </form>
                <div id="platformHint" class="platform-hint unknown" style="margin-top:6px;display:none;">type a name to detect</div>
                <div style="font-size:0.75em;color:var(--text3);margin-top:4px;padding:0 2px;">Type the name without the dot. Auto detects Java vs Bedrock via the Mojang API. Whitelist stays OFF for the chosen duration; player is auto-whitelisted on first successful connection.</div>
            </details>
            <div class="wl-list">__WHITELIST__</div>
        </div>
    </div>

    <div class="filters">
        <select onchange="window.location.href='/?type='+this.value+'&player=__FILTER_PLAYER__&ip=__FILTER_IP__&page=1'">
            <option value="">All Events</option>
            <option value="JOIN" __SEL_JOIN__>JOIN</option>
            <option value="LEAVE" __SEL_LEAVE__>LEAVE</option>
            <option value="REJECTED" __SEL_REJECTED__>REJECTED</option>
            <option value="GEYSER_CONNECT" __SEL_GEYSER_CONNECT__>GEYSER_CONNECT</option>
            <option value="GEYSER_DISCONNECT" __SEL_GEYSER_DISCONNECT__>GEYSER_DISCONNECT</option>
        </select>
        <input type="text" id="playerFilter" placeholder="Filter by player..." value="__FILTER_PLAYER__"
               onkeyup="if(event.key==='Enter')window.location.href='/?type=__FILTER_TYPE__&player='+this.value+'&ip=__FILTER_IP__&page=1'">
        <input type="text" id="ipFilter" placeholder="Filter by IP..." value="__FILTER_IP__"
               onkeyup="if(event.key==='Enter')window.location.href='/?type=__FILTER_TYPE__&player=__FILTER_PLAYER__&ip='+this.value+'&page=1'">
    </div>

    <table>
        <thead><tr><th>Date &amp; Time</th><th>Event</th><th>Player</th><th>IP</th><th>Details</th></tr></thead>
        <tbody>__ROWS__</tbody>
    </table>
    __EMPTY_MSG__

    <div class="pagination">
        __PREV_BTN__
        <span class="page-info">Page __CURRENT_PAGE__ of __TOTAL_PAGES__ (__TOTAL_FILTERED__ events)</span>
        __NEXT_BTN__
    </div>

    <div class="status-bar">
        <div class="status-items">
            <span class="status-item"><span class="label">MC:</span> <span class="value __MC_STATUS_CLASS__">__MC_STATUS__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">TPS:</span> <span class="value __TPS_CLASS__" id="sbTps">__TPS__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">MC up:</span> <span class="value" id="sbMcUp">__MC_UPTIME__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">VPS up:</span> <span class="value">__VPS_UPTIME__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">CPU:</span> <span class="value __CPU_CLASS__" id="sbCpu">__CPU_PERCENT__%</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">RAM:</span> <span class="value __RAM_CLASS__" id="sbRam">__RAM_USED__/__RAM_TOTAL__G (__RAM_PERCENT__%)</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">MC heap:</span> <span class="value __MC_RAM_CLASS__" id="sbMcRam">__MC_RAM_USED__/__MC_RAM_ALLOC__ MB (__MC_RAM_PERCENT__%)</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Swap:</span> <span class="value __SWAP_CLASS__" id="sbSwap">__SWAP_USED__/__SWAP_TOTAL__G</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Disk:</span> <span class="value __DISK_CLASS__">__DISK_USED__/__DISK_TOTAL__G</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">World:</span> <span class="value" id="sbWorld">__WORLD_SIZE__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Backups:</span> <span class="value" id="sbBackup">__BACKUP_COUNT__ (__BACKUP_LAST_SIZE__, __BACKUP_LAST_DATE__)</span></span>
        </div>
        <span class="status-version">v__VERSION__ &mdash; <span id="sbUpdated">__LAST_UPDATED__</span></span>
    </div>

    <div id="toastContainer" aria-live="polite"></div>

    <script>

        // ----- Toast notifications -----
        function showToast(msg, type) {
            type = type || 'info';
            var c = document.getElementById('toastContainer');
            if (!c) return;
            var t = document.createElement('div');
            t.className = 'toast toast-' + type;
            t.innerHTML = '<span></span><button class="toast-close" type="button">&#x2715;</button>';
            t.firstChild.textContent = msg;
            t.querySelector('.toast-close').addEventListener('click', function() {
                t.classList.add('toast-fade-out');
                setTimeout(function(){ t.remove(); }, 300);
            });
            c.appendChild(t);
            setTimeout(function() {
                if (t.parentNode) {
                    t.classList.add('toast-fade-out');
                    setTimeout(function(){ t.remove(); }, 300);
                }
            }, 6000);
        }

        // Show toast from ?msg= query param then strip it from URL (cleaner UX)
        (function() {
            var params = new URLSearchParams(window.location.search);
            var msg = params.get('msg');
            if (msg) {
                showToast(msg, 'info');
                params.delete('msg');
                var clean = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
                window.history.replaceState({}, '', clean);
            }
        })();

        // ----- AJAX form submission (toast instead of full reload) -----
        function submitFormAjax(form, opts) {
            opts = opts || {};
            var fd = new FormData(form);
            return fetch(form.action, {
                method: form.method || 'POST',
                body: fd,
                headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
            }).then(function(r) {
                return r.json().then(function(data) {
                    return { ok: r.ok, data: data };
                });
            }).then(function(res) {
                if (res.ok && res.data) {
                    showToast(res.data.message || 'OK', res.data.toast || 'success');
                    if (opts.refresh !== false) refreshStatus();
                    if (opts.reset && form.reset) form.reset();
                } else {
                    showToast((res.data && res.data.message) || 'Error', 'error');
                }
            }).catch(function(err) {
                showToast('Network error: ' + err, 'error');
            });
        }

        // Hijack whitelist add + onboard forms to use AJAX
        document.addEventListener('DOMContentLoaded', function() {
            var addForm = document.getElementById('wlAddForm');
            if (addForm) addForm.addEventListener('submit', function(e) {
                e.preventDefault();
                submitFormAjax(addForm, { reset: true });
            });
            var obForm = document.getElementById('onboardForm');
            if (obForm) obForm.addEventListener('submit', function(e) {
                e.preventDefault();
                submitFormAjax(obForm);
            });
        });

        // ----- Live platform detection hint for onboarding form -----
        var hintTimer = null;
        function updatePlatformHint() {
            var nameEl = document.getElementById('onboardName');
            var hint = document.getElementById('platformHint');
            if (!nameEl || !hint) return;
            var name = nameEl.value.trim();
            if (!name) { hint.style.display = 'none'; return; }
            hint.style.display = 'inline-block';
            hint.className = 'platform-hint checking';
            hint.textContent = 'checking...';
            clearTimeout(hintTimer);
            hintTimer = setTimeout(function() {
                fetch('/api/detect-platform?name=' + encodeURIComponent(name), {
                    headers: { 'X-Requested-With': 'fetch' }
                }).then(function(r) { return r.json(); }).then(function(d) {
                    if (d.platform === 'java') {
                        hint.className = 'platform-hint java';
                        hint.textContent = '\u2713 detected as JAVA (' + d.name + ')';
                    } else if (d.platform === 'bedrock') {
                        hint.className = 'platform-hint bedrock';
                        hint.textContent = '\u2713 detected as BEDROCK (no Java account with this name)';
                    } else {
                        hint.className = 'platform-hint unknown';
                        hint.textContent = 'cannot detect platform — using Bedrock as default';
                    }
                }).catch(function() {
                    hint.className = 'platform-hint unknown';
                    hint.textContent = 'detection unavailable (network)';
                });
            }, 350);
        }
        document.addEventListener('DOMContentLoaded', function() {
            var nameEl = document.getElementById('onboardName');
            if (nameEl) nameEl.addEventListener('input', updatePlatformHint);
        });

        // ----- Real-time status poller (5s) -----
        function setText(id, val) {
            var el = document.getElementById(id);
            if (el && val != null) el.textContent = val;
        }
        function setClass(id, cls) {
            var el = document.getElementById(id);
            if (!el) return;
            el.classList.remove('good', 'warn', 'bad');
            if (cls) el.classList.add(cls);
        }
        function buildOnlinePlayer(name) {
            // Inline rendering — must mirror server-side esc + skin URL
            var clean = name.replace(/^[.]+/, '');
            var url = 'https://mc-heads.net/avatar/' + encodeURIComponent(clean) + '/20.png';
            var span = document.createElement('span');
            span.className = 'online-player';
            var img = document.createElement('img');
            img.className = 'skin-head-sm';
            img.src = url; img.alt = ''; img.loading = 'lazy';
            img.onerror = function() { this.style.display = 'none'; };
            span.appendChild(img);
            span.appendChild(document.createTextNode(' ' + name));
            return span;
        }

        function refreshStatus() {
            return fetch('/api/status', { headers: { 'X-Requested-With': 'fetch' } })
                .then(function(r) { return r.json(); })
                .then(function(s) {
                    setText('liveOnline', s.players_online);
                    setText('liveMax', s.players_max);
                    setText('liveEvents', s.event_count);
                    setText('sbTps', s.tps);
                    setClass('sbTps', s.tps_class);
                    setText('sbMcUp', s.mc_uptime);
                    setText('sbCpu', s.cpu_percent + '%');
                    setClass('sbCpu', s.cpu_class);
                    setText('sbRam', s.ram_used + '/' + s.ram_total + 'G (' + s.ram_percent + '%)');
                    setClass('sbRam', s.ram_class);
                    setText('sbMcRam', s.mc_ram_used + '/' + s.mc_ram_alloc + ' MB (' + s.mc_ram_percent + '%)');
                    setClass('sbMcRam', s.mc_ram_class);
                    setText('sbWorld', s.world_size);
                    setText('sbBackup', s.backup_count + ' (' + s.backup_last_size + ', ' + s.backup_last_date + ')');
                    setText('sbUpdated', s.now);

                    // Online players list
                    var ol = document.getElementById('liveOnlineList');
                    if (ol) {
                        ol.innerHTML = '';
                        if (s.player_names && s.player_names.length) {
                            s.player_names.forEach(function(n) { ol.appendChild(buildOnlinePlayer(n)); });
                        } else {
                            var empty = document.createElement('span');
                            empty.style.cssText = 'color:var(--text3);font-size:0.85em;';
                            empty.textContent = 'No players online';
                            ol.appendChild(empty);
                        }
                    }

                    // (Backup widget moved to /backups page — no inline updates here.)

                    // Onboarding banner — if state changed (added/removed/completed),
                    // we still need a full reload for the form/banner DOM. JSON-only
                    // updates would mean re-templating server-side. Keep simple:
                    // when onboarding finalizes (completed/expired), reload once.
                    if (window._lastOnboardingActive && (!s.onboarding || s.onboarding.status !== 'active')) {
                        location.reload();
                    }
                    window._lastOnboardingActive = !!(s.onboarding && s.onboarding.status === 'active');
                })
                .catch(function(err) {
                    console.warn('status refresh failed:', err);
                });
        }

        (function() {
            var match = document.cookie.match(/theme=(dark|light)/);
            var theme = match ? match[1] : 'dark';
            document.getElementById('themeIcon').innerHTML = theme === 'dark' ? '&#x2600;' : '&#x1F319;';

            // Initial state and 5s poller
            window._lastOnboardingActive = !!document.getElementById('onboardingBox');
            setInterval(refreshStatus, 5000);

            // Countdown indicator (visual only — actual refresh is on a 5s timer)
            var seconds = 5;
            var el = document.getElementById('countdown');
            if (el) el.textContent = seconds;
            setInterval(function() {
                seconds--;
                if (seconds < 0) seconds = 5;
                if (el) el.textContent = seconds;
            }, 1000);

            refreshStatus();
        })();
    </script>
</body>
</html>
"""

@app.route('/')
@requires_auth
def index():
    events = load_events()
    sys_status = get_system_status()
    wl_players = get_whitelist()
    onboarding = process_onboarding()
    csrf = get_csrf_token()

    filter_type = request.args.get('type', '')
    filter_player = request.args.get('player', '')
    filter_ip = request.args.get('ip', '')
    msg = request.args.get('msg', '')
    page = max(1, int(request.args.get('page', 1)))

    all_joins = [e for e in events if e.get('type') == 'JOIN']
    unique_players = len(set(e.get('player', '') for e in all_joins))
    total_rejected = len([e for e in events if e.get('type') == 'REJECTED'])
    top_players = get_top_players(events)
    daily = get_daily_activity(events)
    suspicious_ips = get_suspicious_ips(events)
    nicknames = get_nicknames()

    online_list = ''
    for name in sys_status.get('player_names', []):
        display = format_player_name(name, nicknames)
        skin = skin_url(name, 20)
        online_list += (
            f'<span class="online-player">'
            f'<img class="skin-head-sm" src="{skin}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
            f'{esc(display)}</span>'
        )
    if not online_list:
        online_list = '<span style="color:var(--text3);font-size:0.85em;">No players online</span>'

    filtered = events
    if filter_type: filtered = [e for e in filtered if e.get('type') == filter_type]
    if filter_player: filtered = [e for e in filtered if filter_player.lower() in e.get('player', '').lower()]
    if filter_ip: filtered = [e for e in filtered if filter_ip in e.get('ip', '')]
    filtered = list(reversed(filtered))

    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    start = (page - 1) * PER_PAGE
    page_events = filtered[start:start + PER_PAGE]

    rows = []
    for e in page_events:
        ts = e.get('timestamp', '')
        time_str = e.get('time', '')
        display_time = ts.replace('T', ' ') if 'T' in ts else f"{ts} {time_str}"
        event_type = e.get('type', 'UNKNOWN')
        # Whitelist event_type to a known set so the CSS class can't be poisoned.
        safe_event_type = event_type if re.match(r'^[A-Z_]{1,32}$', event_type) else 'UNKNOWN'
        player_display = format_player_name(e.get('player', ''), nicknames)
        rows.append(f"""<tr class="row-{safe_event_type}">
            <td>{esc(display_time)}</td>
            <td><span class="tag tag-{safe_event_type}">{esc(safe_event_type)}</span></td>
            <td>{esc(player_display)}</td>
            <td><span class="ip">{esc(e.get('ip', ''))}</span></td>
            <td><span class="reason">{esc(e.get('reason', ''))}</span></td>
        </tr>""")

    empty_msg = '<div class="empty">No events found</div>' if not rows else ''
    base_url = f"/?type={filter_type}&player={filter_player}&ip={filter_ip}"
    prev_btn = f'<a href="{base_url}&page={page-1}" class="btn">&laquo; Prev</a>' if page > 1 else '<span class="btn disabled">&laquo; Prev</span>'
    next_btn = f'<a href="{base_url}&page={page+1}" class="btn">Next &raquo;</a>' if page < total_pages else '<span class="btn disabled">Next &raquo;</span>'
    current_url = f"{base_url}&page={page}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_html = f'<div class="msg-box">{esc(msg)}</div>' if msg else ''

    onboarding_html = ''
    if onboarding:
        ob_name = esc(onboarding.get('name', '?'))
        status = onboarding.get('status', '')
        if status == 'active':
            secs = int(onboarding.get('seconds_left', 0))
            mm, ss = secs // 60, secs % 60
            hint = ''
            if onboarding.get('last_outcome') == 'rejected':
                hint = (
                    f'<div style="margin-top:6px;padding:6px 10px;background:rgba(231,76,60,0.15);'
                    f'border-radius:4px;color:var(--red);font-size:0.85em;">'
                    f'&#x26A0; Last attempt failed: {esc(onboarding.get("reject_reason", "unknown"))}. '
                    f'Check the username spelling, edition (Java vs Bedrock), and that they\'re using a real Mojang/Microsoft account.'
                    f'</div>'
                )
            onboarding_html = (
                f'<div class="onboarding-box" id="onboardingBox" data-deadline="{secs}">'
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px;width:100%;">'
                f'&#x1F517; <strong>Onboarding {ob_name}</strong> &mdash; whitelist is OFF. '
                f'Tell {ob_name} to connect now! Auto-whitelist on first connection. '
                f'<span class="countdown" id="obCountdown">{mm}:{ss:02d}</span> remaining.'
                f'<form method="POST" action="/api/whitelist/onboard/cancel" style="display:inline;margin-left:auto;">'
                f'<input type="hidden" name="csrf_token" value="{csrf}">'
                f'<button class="btn btn-danger" style="padding:3px 10px;font-size:0.85em;">Cancel</button>'
                f'</form>'
                f'</div>'
                f'{hint}'
                f'</div>'
            )
        elif status == 'completed':
            res = esc(onboarding.get('result', ''))
            onboarding_html = (
                f'<div class="msg-box" style="border-color:var(--accent);color:var(--accent);">'
                f'&#x2705; Onboarded <strong>{ob_name}</strong>. Whitelist is back ON. '
                f'<span style="color:var(--text2);">({res})</span>'
                f'</div>'
            )
        elif status == 'expired':
            extra = ''
            if onboarding.get('last_outcome') == 'rejected':
                extra = f' Last failure reason: {esc(onboarding.get("reject_reason", "unknown"))}.'
            onboarding_html = (
                f'<div class="msg-box" style="border-color:var(--yellow);color:var(--yellow);">'
                f'&#x23F0; Onboarding for <strong>{ob_name}</strong> timed out. Whitelist re-enabled.'
                f'{extra} Check the gamertag/username and try again.'
                f'</div>'
            )

    html = HTML_TEMPLATE
    html = html.replace('__FAVICON__', FAVICON)
    html = html.replace('__CSRF__', csrf)
    html = html.replace('__MSG__', msg_html)
    html = html.replace('__ALERTS__', build_alerts(suspicious_ips))
    html = html.replace('__ONBOARDING__', onboarding_html)
    html = html.replace('__ROWS__', '\n'.join(rows))
    html = html.replace('__EMPTY_MSG__', empty_msg)
    html = html.replace('__TOTAL_JOINS__', str(len(all_joins)))
    html = html.replace('__UNIQUE_PLAYERS__', str(unique_players))
    html = html.replace('__TOTAL_REJECTED__', str(total_rejected))
    html = html.replace('__TOTAL_EVENTS__', str(len(events)))
    html = html.replace('__FILTER_TYPE__', filter_type)
    html = html.replace('__FILTER_PLAYER__', filter_player)
    html = html.replace('__FILTER_IP__', filter_ip)
    html = html.replace('__SEL_JOIN__', 'selected' if filter_type == 'JOIN' else '')
    html = html.replace('__SEL_LEAVE__', 'selected' if filter_type == 'LEAVE' else '')
    html = html.replace('__SEL_REJECTED__', 'selected' if filter_type == 'REJECTED' else '')
    html = html.replace('__SEL_GEYSER_CONNECT__', 'selected' if filter_type == 'GEYSER_CONNECT' else '')
    html = html.replace('__SEL_GEYSER_DISCONNECT__', 'selected' if filter_type == 'GEYSER_DISCONNECT' else '')
    html = html.replace('__PREV_BTN__', prev_btn)
    html = html.replace('__NEXT_BTN__', next_btn)
    html = html.replace('__CURRENT_PAGE__', str(page))
    html = html.replace('__TOTAL_PAGES__', str(total_pages))
    html = html.replace('__TOTAL_FILTERED__', str(total_filtered))
    html = html.replace('__CURRENT_URL__', current_url)
    html = html.replace('__LAST_UPDATED__', now)
    html = html.replace('__VERSION__', VERSION)
    html = html.replace('__DAILY_CHART__', build_daily_chart(daily))
    html = html.replace('__TOP_PLAYERS__', build_top_players(top_players, nicknames))
    html = html.replace('__ONLINE_PLAYERS_LIST__', online_list)
    html = html.replace('__WHITELIST__', build_whitelist_panel(wl_players, nicknames))
    html = html.replace('__WL_COUNT__', str(len(wl_players)))

    html = html.replace('__VPS_UPTIME__', sys_status['vps_uptime'])
    html = html.replace('__MC_UPTIME__', sys_status['mc_uptime'])
    html = html.replace('__MC_STATUS__', sys_status['mc_status'].upper())
    html = html.replace('__MC_STATUS_CLASS__', sys_status['mc_status'])
    html = html.replace('__TPS__', sys_status['tps'])
    html = html.replace('__TPS_CLASS__', sys_status.get('tps_class', ''))
    html = html.replace('__CPU_PERCENT__', sys_status['cpu_percent'])
    html = html.replace('__CPU_CORES__', sys_status['cpu_cores'])
    html = html.replace('__CPU_CLASS__', percent_class(sys_status['cpu_percent']))
    html = html.replace('__RAM_USED__', sys_status['ram_used'])
    html = html.replace('__RAM_TOTAL__', sys_status['ram_total'])
    html = html.replace('__RAM_PERCENT__', sys_status['ram_percent'])
    html = html.replace('__RAM_CLASS__', percent_class(sys_status['ram_percent']))
    html = html.replace('__MC_RAM_USED__', sys_status['mc_ram_used'])
    html = html.replace('__MC_RAM_ALLOC__', sys_status['mc_ram_alloc'])
    html = html.replace('__MC_RAM_PERCENT__', sys_status['mc_ram_percent'])
    html = html.replace('__MC_RAM_CLASS__', percent_class(sys_status['mc_ram_percent']))
    html = html.replace('__SWAP_USED__', sys_status['swap_used'])
    html = html.replace('__SWAP_TOTAL__', sys_status['swap_total'])
    html = html.replace('__SWAP_PERCENT__', sys_status['swap_percent'])
    html = html.replace('__SWAP_CLASS__', percent_class(sys_status['swap_percent']))
    html = html.replace('__DISK_USED__', sys_status['disk_used'])
    html = html.replace('__DISK_TOTAL__', sys_status['disk_total'])
    html = html.replace('__DISK_PERCENT__', sys_status['disk_percent'])
    html = html.replace('__DISK_CLASS__', percent_class(sys_status['disk_percent']))
    html = html.replace('__PLAYERS_ONLINE__', sys_status['players_online'])
    html = html.replace('__PLAYERS_MAX__', sys_status['players_max'])
    html = html.replace('__WORLD_SIZE__', sys_status['world_size'])
    html = html.replace('__BACKUP_COUNT__', sys_status['backup_count'])
    html = html.replace('__BACKUP_LAST_SIZE__', sys_status['backup_last_size'])
    html = html.replace('__BACKUP_LAST_DATE__', sys_status['backup_last_date'])

    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8090)