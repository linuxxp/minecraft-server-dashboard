#!/usr/bin/env python3
"""
Minecraft Server Access Logger + Metrics Collector
Monitors Docker logs for connection attempts and collects system metrics.
Run via cron every 5 minutes: */5 * * * * /usr/bin/python3 /home/pi/mc-access-logger.py

Version: 1.4.0
Changelog:
  v1.4.0 (2026-05-06)
    - Persistent chat history: <Player> messages and [Server] broadcasts are
      now captured to /home/pi/mc-chat-log.json (90-day retention, capped at
      50000 messages). Dedup against last 200 entries to handle the 5-minute
      Docker log overlap. Web app reads this instead of re-parsing logs.
  v1.3.0 (2026-05-01)
    - Atomic JSON writes (write-tmp + os.replace) for events and metrics files
    - Replaced bare except blocks with logging via stderr/file logger
    - Logs to /home/pi/mc-access-logger.log (cron-friendly: stderr captured too)
  v1.2.1 (2026-03-25)
    - Fixed player count regex (Paper changed format to "out of maximum")
  v1.2.0 (2026-03-23)
    - Added system metrics collection (CPU, RAM, MC heap, TPS, player count)
    - Metrics stored in separate JSON file with 6-month retention
  v1.1.0 (2026-03-23)
    - Added ANSI color code stripping
  v1.0.0 (2026-03-22)
    - Initial release
"""

import subprocess
import re
import os
import json
import logging
import psutil
from datetime import datetime, timedelta

LOG_FILE = "/home/pi/mc-access-log.json"
METRICS_FILE = "/home/pi/mc-metrics.json"
CHAT_FILE = "/home/pi/mc-chat-log.json"
STATE_FILE = "/home/pi/.mc-logger-state"
APP_LOG_FILE = "/home/pi/mc-access-logger.log"
METRICS_RETENTION_DAYS = 180  # 6 months
CHAT_RETENTION_DAYS = 90  # 3 months
CHAT_MAX_MESSAGES = 50000  # ceiling regardless of age

# Logging — stderr (captured by cron) + file. No bare except: pass anywhere.
_handlers = [logging.StreamHandler()]
try:
    _handlers.append(logging.FileHandler(APP_LOG_FILE))
except Exception as _e:
    print(f"[startup] could not open log file {APP_LOG_FILE}: {_e}")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=_handlers,
)
log = logging.getLogger('mc-logger')

def atomic_write_json(path, data, **dump_kwargs):
    """Write JSON atomically: tmp file + fsync + os.replace."""
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise

def strip_ansi(text):
    """Remove ANSI escape codes from text"""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

def rcon(cmd):
    """Execute RCON command and return cleaned output"""
    try:
        result = subprocess.run(
            ['docker', 'exec', 'minecraft', 'rcon-cli', cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return strip_ansi(result.stdout.strip())
        log.warning("rcon non-zero: cmd=%r rc=%d stderr=%s", cmd, result.returncode, result.stderr.strip()[:200])
        return ''
    except subprocess.TimeoutExpired:
        log.warning("rcon timeout: cmd=%r", cmd)
        return ''
    except Exception:
        log.exception("rcon exception: cmd=%r", cmd)
        return ''

# --- Access Log Patterns ---
PATTERNS = {
    "join": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: (\S+)\[/(\d+\.\d+\.\d+\.\d+):\d+\] logged in'),
    "leave": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: (\S+) left the game'),
    "kicked": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: (\S+) lost connection: (.+)'),
    "unknown_connect": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: (\S+) \(/(\d+\.\d+\.\d+\.\d+):\d+\) lost connection: (.+)'),
    "geyser_connect": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: \[Geyser-Spigot\] Player connected with username (\S+)'),
    "geyser_disconnect": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: \[Geyser-Spigot\] (\S+) has disconnected.*because of (.+)'),
    # Chat patterns — captured into a separate persistent file
    "chat": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: <([^>]+)> (.+)$'),
    "chat_server": re.compile(r'\[(\d{2}:\d{2}:\d{2}) INFO\]: \[(?:Server|Not Secure\] \[Server)\] (.+)$'),
}

# --- Access Log Functions ---

def get_last_position():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            log.warning("state file unreadable, restarting from 0")
            return 0
    return 0

def save_position(pos):
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(str(pos))
    except OSError:
        log.exception("could not save state file")

def get_docker_logs():
    try:
        result = subprocess.run(
            ['docker', 'logs', 'minecraft', '--timestamps'],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        log.warning("docker logs timeout")
        return []
    except Exception:
        log.exception("docker logs failed")
        return []

def append_event(event):
    events = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                events = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            log.warning("events file unreadable; starting fresh")
            events = []

    events.append(event)

    if len(events) > 10000:
        events = events[-10000:]

    try:
        atomic_write_json(LOG_FILE, events, indent=2, ensure_ascii=False)
    except Exception:
        log.exception("could not write events file")

def append_chat_messages(new_msgs):
    """Append a batch of chat messages, dedup against the last message
    (Docker logs include a tail overlap each tick), enforce retention."""
    if not new_msgs:
        return
    msgs = []
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, 'r') as f:
                msgs = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            log.warning("chat file unreadable; starting fresh")
            msgs = []

    # Dedup: skip messages already at the tail of the existing file
    seen_keys = set()
    if msgs:
        # Build keys for the last 200 messages (cheap, covers most overlap)
        for m in msgs[-200:]:
            seen_keys.add((m.get('timestamp', ''), m.get('time', ''),
                          m.get('sender', ''), m.get('text', '')))

    added = 0
    for m in new_msgs:
        k = (m.get('timestamp', ''), m.get('time', ''), m.get('sender', ''), m.get('text', ''))
        if k in seen_keys:
            continue
        seen_keys.add(k)
        msgs.append(m)
        added += 1

    if added == 0:
        return

    # Retention: drop messages older than CHAT_RETENTION_DAYS
    cutoff = (datetime.now() - timedelta(days=CHAT_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    msgs = [m for m in msgs if m.get('timestamp', '') >= cutoff]
    # And cap at CHAT_MAX_MESSAGES regardless
    if len(msgs) > CHAT_MAX_MESSAGES:
        msgs = msgs[-CHAT_MAX_MESSAGES:]

    try:
        atomic_write_json(CHAT_FILE, msgs, ensure_ascii=False, separators=(',', ':'))
        log.info("chat: appended %d new messages (file has %d total)", added, len(msgs))
    except Exception:
        log.exception("could not write chat file")

def process_logs():
    lines = get_docker_logs()
    last_pos = get_last_position()
    new_lines = lines[last_pos:]

    today = datetime.now().strftime("%Y-%m-%d")
    events_found = 0
    chat_batch = []  # batched chat writes — single file write per tick

    for line in new_lines:
        line = strip_ansi(line)

        timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
        ts = timestamp_match.group(1) if timestamp_match else today

        m = PATTERNS["join"].search(line)
        if m:
            append_event({"timestamp": ts, "time": m.group(1), "type": "JOIN", "player": m.group(2), "ip": m.group(3)})
            log.info("[JOIN] %s %s from %s", ts, m.group(2), m.group(3))
            events_found += 1
            continue

        m = PATTERNS["leave"].search(line)
        if m:
            append_event({"timestamp": ts, "time": m.group(1), "type": "LEAVE", "player": m.group(2), "ip": ""})
            events_found += 1
            continue

        m = PATTERNS["unknown_connect"].search(line)
        if m:
            append_event({"timestamp": ts, "time": m.group(1), "type": "REJECTED", "player": m.group(2), "ip": m.group(3), "reason": m.group(4)})
            log.info("[REJECTED] %s %s from %s - %s", ts, m.group(2), m.group(3), m.group(4))
            events_found += 1
            continue

        m = PATTERNS["geyser_connect"].search(line)
        if m:
            append_event({"timestamp": ts, "time": m.group(1), "type": "GEYSER_CONNECT", "player": m.group(2), "ip": ""})
            events_found += 1
            continue

        m = PATTERNS["geyser_disconnect"].search(line)
        if m:
            append_event({"timestamp": ts, "time": m.group(1), "type": "GEYSER_DISCONNECT", "player": m.group(2), "ip": "", "reason": m.group(3)})
            events_found += 1
            continue

        # Chat — collected and persisted to a separate file
        m = PATTERNS["chat"].search(line)
        if m:
            chat_batch.append({
                "timestamp": ts, "time": m.group(1), "kind": "chat",
                "sender": m.group(2), "text": m.group(3),
            })
            continue
        m = PATTERNS["chat_server"].search(line)
        if m:
            chat_batch.append({
                "timestamp": ts, "time": m.group(1), "kind": "server",
                "sender": "Server", "text": m.group(2),
            })
            continue

    save_position(len(lines))
    if chat_batch:
        append_chat_messages(chat_batch)
    log.info("Processed %d new lines, found %d events, %d chat messages",
             len(new_lines), events_found, len(chat_batch))

# --- Metrics Collection ---

def collect_metrics():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    metrics = {"ts": now}

    # CPU
    metrics["cpu"] = psutil.cpu_percent(interval=1)

    # System RAM percent
    metrics["ram"] = psutil.virtual_memory().percent

    # Swap percent
    metrics["swap"] = psutil.swap_memory().percent

    # MC heap and TPS and players from RCON
    mem_output = rcon('memory')
    if mem_output:
        alloc_match = re.search(r'Allocated memory:\s*([\d,]+)\s*MB', mem_output)
        free_match = re.search(r'Free memory:\s*([\d,]+)\s*MB', mem_output)
        if alloc_match and free_match:
            allocated = int(alloc_match.group(1).replace(',', ''))
            free = int(free_match.group(1).replace(',', ''))
            used = allocated - free
            metrics["mc_heap"] = round(used / allocated * 100, 1) if allocated > 0 else 0
        else:
            metrics["mc_heap"] = 0
    else:
        metrics["mc_heap"] = 0

    tps_output = rcon('tps')
    if tps_output and ':' in tps_output:
        tps_part = tps_output.split(':', 1)[1]
        tps_match = re.findall(r'\*?(\d+\.?\d*)', tps_part)
        metrics["tps"] = float(tps_match[0]) if tps_match else 0
    else:
        metrics["tps"] = 0

    list_output = rcon('list')
    if list_output:
        match = re.search(r'There are (\d+)', list_output)
        metrics["players"] = int(match.group(1)) if match else 0
    else:
        metrics["players"] = 0

    return metrics

def save_metrics(metrics):
    data = []
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            log.warning("metrics file unreadable; starting fresh")
            data = []

    data.append(metrics)

    # Trim to retention period
    cutoff = (datetime.now() - timedelta(days=METRICS_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    data = [d for d in data if d.get('ts', '') >= cutoff]

    try:
        atomic_write_json(METRICS_FILE, data, separators=(',', ':'))
    except Exception:
        log.exception("could not write metrics file")
        return

    log.info(
        "Metrics saved: CPU=%s%% RAM=%s%% MC_heap=%s%% TPS=%s Players=%s",
        metrics['cpu'], metrics['ram'], metrics['mc_heap'], metrics['tps'], metrics['players'],
    )

# --- Main ---

if __name__ == "__main__":
    process_logs()
    metrics = collect_metrics()
    save_metrics(metrics)