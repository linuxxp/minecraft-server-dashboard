#!/usr/bin/env python3
"""
Minecraft Access Log Web Viewer
Runs on port 8090.

Version: 1.10.0
Changelog:
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

VERSION = "1.10.0"
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
        rows.append(f"""<div class="top-row">
            <span class="top-rank">{medal}</span>
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
        # Use data-name + JSON-escaped attribute so even weird characters are safe.
        # The handler reads it via dataset.name — no string interpolation in HTML.
        name_attr = esc(name)
        rows += f"""<div class="wl-row">
            <span class="wl-name">{badge} {esc(display)}</span>
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

@app.route('/api/whitelist/add', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_add():
    name = request.form.get('name', '').strip()
    ptype = request.form.get('type', 'bedrock')
    if not name:
        return redirect('/?msg=Empty+name')
    clean_name = name.lstrip('.')
    if ptype == 'bedrock':
        result = rcon(f'fwhitelist add {clean_name}')
        if not result:
            result = 'Sent (Bedrock player must have connected once before)'
    else:
        result = rcon(f'whitelist add {clean_name}')
    cache_invalidate('rcon:list')
    log.info("whitelist add: name=%r type=%s result=%r", clean_name, ptype, result)
    return redirect(f'/?msg={ptype.upper()}:+{clean_name}+-+{result}')

@app.route('/api/whitelist/remove', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_remove():
    name = request.form.get('name', '').strip()
    if not name:
        return redirect('/?msg=Empty+name')
    if name.startswith('.'):
        result = rcon(f'fwhitelist remove {name[1:]}')
    else:
        result = rcon(f'whitelist remove {name}')
    cache_invalidate('rcon:list')
    log.info("whitelist remove: name=%r result=%r", name, result)
    return redirect(f'/?msg=Removed+{name}+-+{result}')

@app.route('/api/whitelist/toggle', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_toggle():
    state = request.form.get('state', 'on')
    result = rcon(f'whitelist {state}')
    log.info("whitelist toggle: state=%s result=%r", state, result)
    msg = 'Whitelist ON' if state == 'on' else 'Whitelist OFF - anyone can join!'
    return redirect(f'/?msg={msg}')

@app.route('/api/whitelist/onboard', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_onboard():
    """
    Start onboarding for a new player:
    1. Disable whitelist temporarily
    2. Save pending state with deadline
    3. On subsequent dashboard loads, process_onboarding() detects when the
       player connects and auto-whitelists them.
    """
    name = request.form.get('name', '').strip().lstrip('.')
    platform = request.form.get('platform', 'bedrock')
    try:
        duration = int(request.form.get('duration', ONBOARDING_DEFAULT_MINUTES))
    except ValueError:
        duration = ONBOARDING_DEFAULT_MINUTES
    duration = max(1, min(duration, ONBOARDING_MAX_MINUTES))

    if not name:
        return redirect('/?msg=Empty+name')

    # Don't start a second onboarding if one is already running
    existing = get_onboarding_state()
    if existing:
        return redirect(f'/?msg=Onboarding+already+active+for+{existing.get("name","?")}')

    rcon('whitelist off')
    save_onboarding_state({
        'name': name,
        'platform': platform,
        'duration_minutes': duration,
        'started_at': datetime.now().replace(microsecond=0).isoformat(),
    })
    log.info("onboarding started: name=%r platform=%s duration=%d", name, platform, duration)
    return redirect(f'/?msg=Onboarding+{name}+-+whitelist+OFF+for+{duration}min')

@app.route('/api/whitelist/onboard/cancel', methods=['POST'])
@requires_auth
@requires_csrf
def api_whitelist_onboard_cancel():
    rcon('whitelist on')
    clear_onboarding_state()
    log.info("onboarding cancelled")
    return redirect('/?msg=Onboarding+cancelled+-+whitelist+ON')

@app.route('/api/restart', methods=['POST'])
@requires_auth
@requires_csrf
def api_restart():
    try:
        subprocess.Popen(['docker', 'compose', '-f', '/opt/minecraft/docker-compose.yml', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cache_invalidate()  # everything is suspect after restart
        log.info("server restart triggered")
        return redirect('/?msg=Server+restarting...')
    except Exception as e:
        log.exception("restart trigger failed")
        return redirect(f'/?msg=Error:+{e}')

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
        });
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
    for p in plugins:
        jar_candidates = []
        try:
            for f in os.listdir(plugins_dir):
                if f.endswith('.jar'):
                    fname = f.lower().replace('-', '').replace('_', '')
                    pname = p['name'].lower().replace('-', '').replace('_', '')
                    if pname in fname or fname.startswith(pname[:6]):
                        jar_candidates.append(os.path.join(plugins_dir, f))
        except Exception:
            log.exception("plugin jar match failed for %r", p['name'])
        if jar_candidates:
            try:
                best = jar_candidates[0]
                size = os.path.getsize(best)
                p['file'] = os.path.basename(best)
                p['size'] = format_size(size)
            except Exception:
                log.exception("plugin file stat failed for %r", p['name'])
                p['file'] = '?'
                p['size'] = '?'
        else:
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
    # Convert sets to lists and add nicknames
    result = []
    for name, stats in merged.items():
        stats['name'] = name
        stats['display'] = format_player_name(name, nicknames)
        stats['ips'] = sorted(stats['ips'])
        stats['rejected_ips'] = sorted(stats['rejected_ips'])
        stats['platform'] = 'Bedrock' if stats['geyser'] or name.startswith('.') else 'Java'
        result.append(stats)
    return sorted(result, key=lambda x: x['joins'], reverse=True)

@app.route('/api/plugins/update', methods=['POST'])
@requires_auth
@requires_csrf
def api_plugin_update():
    filename = request.form.get('file', '').strip()
    url = request.form.get('url', '').strip()
    if not filename or not url:
        return redirect('/plugins?msg=Missing+file+or+URL')
    # Basic safety: reject path traversal and disallow non-http(s)
    if '/' in filename or '\\' in filename or filename.startswith('.'):
        log.warning("plugin update rejected: bad filename %r", filename)
        return redirect('/plugins?msg=Bad+filename')
    if not (url.startswith('http://') or url.startswith('https://')):
        return redirect('/plugins?msg=URL+must+be+http(s)')
    # Save URL for future
    urls = load_plugin_urls()
    urls[filename] = url
    save_plugin_urls(urls)
    plugins_dir = os.path.join(WORLD_DIR, 'plugins')
    filepath = os.path.join(plugins_dir, filename)
    old_size = 0
    if os.path.exists(filepath):
        old_size = os.path.getsize(filepath)
    try:
        result = subprocess.run(['curl', '-fL', '-o', filepath, url], capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(filepath):
            new_size = os.path.getsize(filepath)
            log.info("plugin updated: file=%s old=%d new=%d", filename, old_size, new_size)
            msg = f'Updated {filename}: {format_size(old_size)} -> {format_size(new_size)}. Restart needed!'
        else:
            log.warning("plugin update failed: file=%s rc=%d stderr=%s", filename, result.returncode, result.stderr[:200])
            msg = f'Error downloading {filename}: {result.stderr[:100]}'
    except Exception as e:
        log.exception("plugin update exception: file=%s", filename)
        msg = f'Error: {e}'
    return redirect(f'/plugins?msg={msg}')

@app.route('/api/plugins/update-all', methods=['POST'])
@requires_auth
@requires_csrf
def api_plugin_update_all():
    urls = load_plugin_urls()
    if not urls:
        return redirect('/plugins?msg=No+plugin+URLs+configured')
    plugins_dir = os.path.join(WORLD_DIR, 'plugins')
    results = []
    for filename, url in urls.items():
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            log.warning("update-all skipping bad filename %r", filename)
            results.append(f'{filename}: SKIPPED-badname')
            continue
        if not (url.startswith('http://') or url.startswith('https://')):
            results.append(f'{filename}: SKIPPED-badurl')
            continue
        filepath = os.path.join(plugins_dir, filename)
        old_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        try:
            result = subprocess.run(['curl', '-fL', '-o', filepath, url], capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(filepath):
                new_size = os.path.getsize(filepath)
                results.append(f'{filename}: {format_size(old_size)}->{format_size(new_size)}')
            else:
                log.warning("update-all failed: file=%s rc=%d", filename, result.returncode)
                results.append(f'{filename}: FAILED')
        except Exception:
            log.exception("update-all exception: file=%s", filename)
            results.append(f'{filename}: ERROR')
    msg = ' | '.join(results) + ' | Restart needed!'
    return redirect(f'/plugins?msg={msg}')

PLUGINS_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MC Plugins</title>
    <link rel="icon" type="image/png" href="data:image/png;base64,__FAVICON__">
    <style>
        :root[data-theme="dark"] { --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460; --text: #e0e0e0; --text2: #888; --text3: #555; --accent: #4ecca3; --border2: #333; --border3: #1e3050; --blue: #48bfe3; --msg-bg: #1b3a4b; }
        :root[data-theme="light"] { --bg: #f0f2f5; --bg2: #ffffff; --bg3: #e8ecf1; --text: #1a1a2e; --text2: #666; --text3: #999; --accent: #2d8f6f; --border2: #ccc; --border3: #ddd; --blue: #2980b9; --msg-bg: #d1ecf1; }
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
        .plugin-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
        .plugin-card { background: var(--bg2); border: 1px solid var(--border3); border-radius: 12px; padding: 14px; }
        .plugin-name { font-size: 1.1em; font-weight: 700; color: var(--accent); margin-bottom: 4px; }
        .plugin-version { font-family: monospace; background: var(--bg3); color: var(--text); padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
        .plugin-meta { color: var(--text2); font-size: 0.82em; margin-top: 4px; }
        .plugin-url { display: flex; gap: 4px; margin-top: 8px; }
        .plugin-url input { flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--border2); padding: 4px 8px; border-radius: 4px; font-size: 0.8em; min-width: 0; }
        .plugin-count { color: var(--text2); font-size: 0.95em; margin-bottom: 16px; }
        @media (max-width: 600px) { body { padding: 12px; } .plugin-grid { grid-template-columns: 1fr; } }
    </style>
    <script>
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
            <form method="POST" action="/api/plugins/update-all" style="display:inline;"><input type="hidden" name="csrf_token" value="__CSRF__"><button type="submit" class="btn btn-update" onclick="return confirm('Update all plugins with saved URLs?')">&#x21BB; Update All</button></form>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>
    __MSG__
    <div class="plugin-count">__PLUGIN_COUNT__ plugins loaded</div>
    <div class="plugin-grid">__PLUGIN_CARDS__</div>
    <script>(function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();</script>
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
        .player-ips { margin-top: 6px; font-size: 0.8em; color: var(--text2); }
        .player-ips code { background: var(--bg3); padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
        .player-count { color: var(--text2); font-size: 0.95em; margin-bottom: 16px; }
        .section-title { color: var(--accent); font-size: 1.15em; margin: 20px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border3); }
        .section-title.others { color: var(--text3); font-size: 1em; margin-top: 30px; }
        .wl-badge { font-size: 0.7em; padding: 1px 6px; border-radius: 3px; background: #1b4332; color: var(--accent); margin-left: 6px; }
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
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>
    <div class="player-count">__PLAYER_COUNT__ whitelisted players</div>
    __PLAYER_SECTIONS__
    <script>(function(){var m=document.cookie.match(/theme=(dark|light)/);var t=m?m[1]:'dark';document.getElementById('themeIcon').innerHTML=t==='dark'?'&#x2600;':'&#x1F319;';})();</script>
</body></html>
"""

@app.route('/plugins')
@requires_auth
def plugins_page():
    plugins = get_plugins_list()
    msg = request.args.get('msg', '')
    msg_html = f'<div class="msg-box">{esc(msg)}</div>' if msg else ''
    csrf = get_csrf_token()
    cards = ''
    for p in sorted(plugins, key=lambda x: x['name'].lower()):
        url_val = p.get('url', '')
        cards += f"""<div class="plugin-card">
            <div class="plugin-name">{esc(p['name'])}</div>
            <span class="plugin-version">v{esc(p['version'])}</span>
            <div class="plugin-meta">{esc(p.get('file', '?'))} &mdash; {esc(p.get('size', '?'))}</div>
            <form method="POST" action="/api/plugins/update" class="plugin-url">
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
                'platform': 'Bedrock' if ptype == 'bedrock' else 'Java'
            })

    def build_player_card(p, is_whitelisted=False):
        platform_class = 'platform-bedrock' if p['platform'] == 'Bedrock' else 'platform-java'
        wl_badge = '<span class="wl-badge">WL</span>' if is_whitelisted else ''
        card_class = 'player-card' if is_whitelisted else 'player-card not-wl'
        first = p['first_seen'].replace('T', ' ')[:16] if p['first_seen'] else 'Never'
        last = p['last_seen'].replace('T', ' ')[:16] if p['last_seen'] else 'Never'
        last_rej = p.get('last_rejected', '').replace('T', ' ')[:16] if p.get('last_rejected') else ''

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
        return f"""<div class="{card_class}">
            <div class="player-header">
                <span class="player-name">{esc(p['display'])}{wl_badge}</span>
                <span class="player-platform {platform_class}">{esc(p['platform'])}</span>
            </div>
            <div class="player-stats">
                <div class="stat-row"><span class="stat-label">Joins</span><span class="stat-value">{int(p['joins'])}</span></div>
                <div class="stat-row"><span class="stat-label">Leaves</span><span class="stat-value">{int(p['leaves'])}</span></div>
                <div class="stat-row"><span class="stat-label">First seen</span><span class="stat-value">{esc(first)}</span></div>
                <div class="stat-row"><span class="stat-label">Last seen</span><span class="stat-value">{esc(last)}</span></div>
                {rejected_row}
            </div>
            {ips_html}
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
    <meta http-equiv="refresh" content="60">
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
        .online-player { display: inline-block; background: var(--tag-geyser-bg); color: var(--blue); padding: 3px 10px; border-radius: 12px; font-size: 0.85em; margin: 3px 4px 3px 0; }

        /* Whitelist panel */
        .wl-add { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
        .wl-add input { background: var(--input-bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 12px; border-radius: 6px; font-size: 0.9em; flex: 1; min-width: 100px; }
        .wl-add select { background: var(--input-bg); color: var(--text); border: 1px solid var(--border2); padding: 7px 8px; border-radius: 6px; font-size: 0.9em; }
        .wl-add button { background: var(--accent); color: var(--bg); border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em; font-weight: 600; }
        .wl-add button:hover { opacity: 0.85; }
        .wl-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 0.9em; }
        .wl-name { color: var(--text); }
        .wl-remove { background: none; border: none; color: var(--red); cursor: pointer; font-size: 1.1em; padding: 2px 6px; border-radius: 4px; }
        .wl-remove:hover { background: var(--tag-reject-bg); }
        .wl-list { max-height: 200px; overflow-y: auto; }

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
            <div class="subtitle"><span class="online-dot"></span>Family Server &mdash; Refresh in <span id="countdown">60</span>s &mdash; Updated: __LAST_UPDATED__</div>
        </div>
        <div class="header-btns">
            <button class="btn btn-danger" onclick="restartServer()" title="Restart Minecraft" style="margin-right:8px;">&#x21BB; Restart</button>
            <a href="/charts" class="btn" title="Charts">&#x1F4CA; Charts</a>
            <a href="/plugins" class="btn" title="Plugins">&#x1F9E9; Plugins</a>
            <a href="/players" class="btn" title="Players">&#x1F465; Players</a>
            <a href="__CURRENT_URL__" class="btn">Refresh</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
        </div>
    </div>

    __MSG__
    __ALERTS__
    __ONBOARDING__

    <div class="stats">
        <div class="stat-box players">
            <div class="stat-num">__PLAYERS_ONLINE__ / __PLAYERS_MAX__</div>
            <div class="stat-label">Online Now</div>
            <div class="online-list">__ONLINE_PLAYERS_LIST__</div>
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
            <div class="stat-num">__TOTAL_EVENTS__</div>
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
                <form method="POST" action="/api/whitelist/add" style="display:flex;gap:6px;flex-wrap:wrap;width:100%;">
                    <input type="hidden" name="csrf_token" value="__CSRF__">
                    <input type="text" name="name" placeholder="Player name..." required>
                    <select name="type">
                        <option value="bedrock">Bedrock</option>
                        <option value="java">Java</option>
                    </select>
                    <button type="submit">+ Add</button>
                </form>
            </div>
            <details style="margin:6px 0 0 0;">
                <summary style="cursor:pointer;color:var(--yellow);font-size:0.82em;padding:4px 0;">+ Onboard new player (auto-disable whitelist, wait, auto-add)</summary>
                <form method="POST" action="/api/whitelist/onboard" style="display:flex;gap:6px;flex-wrap:wrap;width:100%;margin-top:6px;">
                    <input type="hidden" name="csrf_token" value="__CSRF__">
                    <input type="text" name="name" placeholder="Player gamertag..." required style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 12px;border-radius:6px;font-size:0.9em;flex:2;min-width:100px;">
                    <select name="platform" style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 8px;border-radius:6px;font-size:0.9em;">
                        <option value="bedrock">Bedrock</option>
                        <option value="java">Java</option>
                    </select>
                    <input type="number" name="duration" value="5" min="1" max="30" title="Minutes to keep whitelist OFF" style="background:var(--input-bg);color:var(--text);border:1px solid var(--border2);padding:7px 8px;border-radius:6px;font-size:0.9em;width:60px;">
                    <button type="submit" style="background:var(--yellow);color:#000;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:0.9em;font-weight:600;">Open & Wait</button>
                </form>
                <div style="font-size:0.75em;color:var(--text3);margin-top:4px;padding:0 2px;">Whitelist will be OFF for the chosen duration. As soon as the player connects, they are auto-whitelisted and the gate closes again.</div>
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
            <span class="status-item"><span class="label">TPS:</span> <span class="value __TPS_CLASS__">__TPS__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">MC up:</span> <span class="value">__MC_UPTIME__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">VPS up:</span> <span class="value">__VPS_UPTIME__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">CPU:</span> <span class="value __CPU_CLASS__">__CPU_PERCENT__%</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">RAM:</span> <span class="value __RAM_CLASS__">__RAM_USED__/__RAM_TOTAL__G (__RAM_PERCENT__%)</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">MC heap:</span> <span class="value __MC_RAM_CLASS__">__MC_RAM_USED__/__MC_RAM_ALLOC__ MB (__MC_RAM_PERCENT__%)</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Swap:</span> <span class="value __SWAP_CLASS__">__SWAP_USED__/__SWAP_TOTAL__G</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Disk:</span> <span class="value __DISK_CLASS__">__DISK_USED__/__DISK_TOTAL__G</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">World:</span> <span class="value">__WORLD_SIZE__</span></span>
            <span class="status-sep">|</span>
            <span class="status-item"><span class="label">Backups:</span> <span class="value">__BACKUP_COUNT__ (__BACKUP_LAST_SIZE__, __BACKUP_LAST_DATE__)</span></span>
        </div>
        <span class="status-version">v__VERSION__ &mdash; __LAST_UPDATED__</span>
    </div>

    <script>
        (function() {
            var match = document.cookie.match(/theme=(dark|light)/);
            var theme = match ? match[1] : 'dark';
            document.getElementById('themeIcon').innerHTML = theme === 'dark' ? '&#x2600;' : '&#x1F319;';

            // Countdown timer
            var seconds = 60;
            var el = document.getElementById('countdown');
            setInterval(function() {
                seconds--;
                if (seconds < 0) seconds = 60;
                if (el) el.textContent = seconds;
            }, 1000);
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
        online_list += f'<span class="online-player">{esc(display)}</span>'
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
