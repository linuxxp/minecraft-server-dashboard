#!/usr/bin/env python3
"""
Minecraft Access Log Web Viewer
Runs on port 8090.

Version: 1.7.3
Changelog:
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

from flask import Flask, request, Response, redirect, url_for
import json
import os
import re
import glob
import functools
import subprocess
import psutil
from datetime import datetime, timedelta, timezone
from collections import Counter

app = Flask(__name__)
LOG_FILE = "/home/pi/mc-access-log.json"
METRICS_FILE = "/home/pi/mc-metrics.json"
BACKUP_DIR = "/opt/minecraft/backups"
WORLD_DIR = "/opt/minecraft/data"

VERSION = "1.7.3"

USERNAME = "linuxxp"
PASSWORD = "mechopuhemeche"

PER_PAGE = 50
SUSPICIOUS_THRESHOLD = 5

FAVICON = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAA3klEQVQ4y2NgoBAw0tWA/////2dk/M/AwMDIwMTEyMDMzMzAysrKwM7OzsDJyclAE8DMzMTAyMjE8J+RiYGJiYnh/39GBmZmJgYWFhYGNjY2Bk5OTgZubm4GPj4+BgEBAQZhYWEGcQkJBikpKQYZGRkGOTk5BkVFRQYlJSUGFRUVBjU1NQYNdQ0GLQ0tBm0dbQZdXV0GPX09BgMDAwZDQ0MGY2NjBlNTUwZzc3MGS0tLBmsbawY7OzsGBwcHBicnJwYXV1cGNzc3Bg8PDwZvb28GHx8fBj8/fwZ6AwC8VEu5FfMJMgAAAABJRU5ErkJggg=="

def strip_ansi(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

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

def rcon(cmd):
    try:
        result = subprocess.run(['docker', 'exec', 'minecraft', 'rcon-cli', cmd], capture_output=True, text=True, timeout=10)
        return strip_ansi(result.stdout.strip()) if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"

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
                continue
    except Exception:
        pass
    return nicknames

def format_player_name(name, nicknames):
    """Format player name with nickname if available"""
    nick = nicknames.get(name, '')
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

    # MC container uptime
    try:
        result = subprocess.run(['docker', 'inspect', '--format', '{{.State.StartedAt}}', 'minecraft'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            started_dt = datetime.fromisoformat(result.stdout.strip()[:19])
            mc_delta = datetime.now(timezone.utc).replace(tzinfo=None) - started_dt
            mc_days, mc_hours, mc_minutes = mc_delta.days, mc_delta.seconds // 3600, (mc_delta.seconds % 3600) // 60
            status['mc_uptime'] = f"{mc_days}d {mc_hours}h {mc_minutes}m" if mc_days > 0 else f"{mc_hours}h {mc_minutes}m"
            status['mc_status'] = 'online'
        else:
            status['mc_uptime'] = 'N/A'
            status['mc_status'] = 'offline'
    except Exception:
        status['mc_uptime'] = 'N/A'
        status['mc_status'] = 'offline'

    # Online players
    try:
        result = subprocess.run(['docker', 'exec', 'minecraft', 'rcon-cli', 'list'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            full_output = strip_ansi(result.stdout.strip())
            lines = full_output.split('\n')
            first_line = lines[0] if lines else ''
            count_match = re.search(r'There are (\d+)', first_line)
            max_match = re.search(r'(?:maximum|max of)\s+(\d+)', first_line)
            if count_match:
                status['players_online'] = count_match.group(1)
                status['players_max'] = max_match.group(1) if max_match else '20'
                # Extract player names - could be on same line after ":" or on next lines
                player_names = []
                # Check first line for names after colon
                if ':' in first_line:
                    names_part = first_line.split(':', 1)[1].strip()
                    if names_part and 'player' not in names_part.lower():
                        player_names = [n.strip() for n in names_part.split(',') if n.strip()]
                # Check subsequent lines (Paper format: "default: player1, player2")
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
        status['players_online'] = '?'
        status['players_max'] = '?'
        status['player_names'] = []

    # TPS
    try:
        result = subprocess.run(['docker', 'exec', 'minecraft', 'rcon-cli', 'tps'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            line = strip_ansi(result.stdout.strip())
            # Extract TPS values after the colon
            if ':' in line:
                tps_part = line.split(':', 1)[1]
                tps_match = re.findall(r'\*?(\d+\.?\d*)', tps_part)
            else:
                tps_match = []
            if tps_match:
                status['tps'] = tps_match[0]  # 1-minute TPS
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
        else:
            status['tps'] = '?'
            status['tps_class'] = ''
    except Exception:
        status['tps'] = '?'
        status['tps_class'] = ''

    # World size
    try:
        world_size = 0
        for w in ['world', 'world_nether', 'world_the_end']:
            wp = os.path.join(WORLD_DIR, w)
            if os.path.exists(wp):
                world_size += get_dir_size(wp)
        status['world_size'] = format_size(world_size)
    except Exception:
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
        status['backup_count'] = '?'
        status['backup_last_size'] = '?'
        status['backup_last_date'] = '?'

    # MC memory (real usage from Java heap)
    try:
        result = subprocess.run(['docker', 'exec', 'minecraft', 'rcon-cli', 'memory'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            line = strip_ansi(result.stdout)
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
        pass
    return players

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
            <span class="top-name">{display}</span>
            <div class="top-bar-bg"><div class="top-bar-fill" style="width:{pct}%"></div></div>
            <span class="top-count">{count}</span>
        </div>""")
    return '\n'.join(rows)

def build_alerts(suspicious_ips):
    if not suspicious_ips: return ''
    items = []
    for ip, count in sorted(suspicious_ips.items(), key=lambda x: -x[1]):
        items.append(f'<div class="alert-item">&#x26A0; IP <strong>{ip}</strong> &mdash; {count} rejected attempts</div>')
    return f'<div class="alert-box">{"".join(items)}</div>'

def build_whitelist_panel(wl_players, nicknames=None):
    if nicknames is None: nicknames = {}
    rows = ''
    for ptype, name in sorted(wl_players, key=lambda x: x[1]):
        badge = '<span style="color:var(--blue);font-size:0.75em;">BE</span>' if ptype == 'bedrock' else '<span style="color:var(--accent);font-size:0.75em;">JE</span>'
        display = format_player_name(name, nicknames)
        rows += f"""<div class="wl-row">
            <span class="wl-name">{badge} {display}</span>
            <button class="wl-remove" onclick="removePlayer('{name}')" title="Remove">&#x2715;</button>
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
    except (json.JSONDecodeError, FileNotFoundError): return []

# --- API Endpoints ---

@app.route('/api/whitelist/add', methods=['POST'])
@requires_auth
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
    return redirect(f'/?msg={ptype.upper()}:+{clean_name}+-+{result}')

@app.route('/api/whitelist/remove', methods=['POST'])
@requires_auth
def api_whitelist_remove():
    name = request.form.get('name', '').strip()
    if not name:
        return redirect('/?msg=Empty+name')
    if name.startswith('.'):
        rcon(f'fwhitelist remove {name[1:]}')
    rcon(f'whitelist remove {name}')
    return redirect(f'/?msg=Removed+{name}')

@app.route('/api/whitelist/toggle', methods=['POST'])
@requires_auth
def api_whitelist_toggle():
    state = request.form.get('state', 'on')
    result = rcon(f'whitelist {state}')
    msg = 'Whitelist ON' if state == 'on' else 'Whitelist OFF - anyone can join!'
    return redirect(f'/?msg={msg}')

@app.route('/api/restart', methods=['POST'])
@requires_auth
def api_restart():
    try:
        subprocess.Popen(['docker', 'compose', '-f', '/opt/minecraft/docker-compose.yml', 'restart'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return redirect('/?msg=Server+restarting...')
    except Exception as e:
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

        .alert-box { background: var(--alert-bg); border: 1px solid var(--alert-border); border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; }
        .alert-item { color: var(--red); font-size: 0.95em; padding: 4px 0; }
        .msg-box { background: var(--msg-bg); border: 1px solid var(--blue); border-radius: 8px; padding: 10px 16px; margin-bottom: 18px; color: var(--blue); font-size: 0.95em; }

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
                document.body.appendChild(form);
                form.submit();
            }
        }
        function wlToggle(state) {
            if (state === 'off' && !confirm('Turn off whitelist? Anyone can join!')) return;
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = '/api/whitelist/toggle';
            var input = document.createElement('input');
            input.type = 'hidden'; input.name = 'state'; input.value = state;
            form.appendChild(input);
            document.body.appendChild(form);
            form.submit();
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
            <h1>Minecraft Access Log</h1>
            <div class="subtitle"><span class="online-dot"></span>Family Server &mdash; Refresh in <span id="countdown">60</span>s &mdash; Updated: __LAST_UPDATED__</div>
        </div>
        <div class="header-btns">
            <button class="btn btn-danger" onclick="restartServer()" title="Restart Minecraft">&#x21BB; Restart</button>
            <a href="/charts" class="btn" title="Charts">&#x1F4CA; Charts</a>
            <button class="theme-toggle" onclick="toggleTheme()"><span id="themeIcon">&#x2600;</span></button>
            <a href="__CURRENT_URL__" class="btn">Refresh</a>
        </div>
    </div>

    __MSG__
    __ALERTS__

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
                    <input type="text" name="name" placeholder="Player name..." required>
                    <select name="type">
                        <option value="bedrock">Bedrock</option>
                        <option value="java">Java</option>
                    </select>
                    <button type="submit">+ Add</button>
                </form>
            </div>
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
        online_list += f'<span class="online-player">{display}</span>'
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
        player_display = format_player_name(e.get('player', ''), nicknames)
        rows.append(f"""<tr class="row-{event_type}">
            <td>{display_time}</td>
            <td><span class="tag tag-{event_type}">{event_type}</span></td>
            <td>{player_display}</td>
            <td><span class="ip">{e.get('ip', '')}</span></td>
            <td><span class="reason">{e.get('reason', '')}</span></td>
        </tr>""")

    empty_msg = '<div class="empty">No events found</div>' if not rows else ''
    base_url = f"/?type={filter_type}&player={filter_player}&ip={filter_ip}"
    prev_btn = f'<a href="{base_url}&page={page-1}" class="btn">&laquo; Prev</a>' if page > 1 else '<span class="btn disabled">&laquo; Prev</span>'
    next_btn = f'<a href="{base_url}&page={page+1}" class="btn">Next &raquo;</a>' if page < total_pages else '<span class="btn disabled">Next &raquo;</span>'
    current_url = f"{base_url}&page={page}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_html = f'<div class="msg-box">{msg}</div>' if msg else ''

    html = HTML_TEMPLATE
    html = html.replace('__FAVICON__', FAVICON)
    html = html.replace('__MSG__', msg_html)
    html = html.replace('__ALERTS__', build_alerts(suspicious_ips))
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
