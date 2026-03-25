#!/usr/bin/env python3
"""
Collect OpenClaw agent data and write to data/snapshot.json.
Run locally on the server, then git push to update Streamlit Cloud.
"""

import json
import os
import subprocess
import datetime
from pathlib import Path

OPENCLAW_HOME = os.environ.get("OPENCLAW_HOME", "/home/clawuser/.openclaw")
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

AGENTS = [
    {"id": "main", "name": "Nexus", "emoji": "🔗", "domain": "Lead Agent & Coordinator", "model": "claude-opus-4-6", "workspace": "workspace"},
    {"id": "stratton", "name": "Stratton", "emoji": "📊", "domain": "Telecom (GVTC)", "model": "claude-sonnet-4", "workspace": "workspace-stratton"},
    {"id": "rosie", "name": "Rosie", "emoji": "🌹", "domain": "HCFC (Wife's Biz)", "model": "claude-sonnet-4", "workspace": "workspace-rosie"},
    {"id": "sawyer", "name": "Sawyer", "emoji": "🪚", "domain": "Woodworking", "model": "claude-sonnet-4", "workspace": "workspace-sawyer"},
    {"id": "sterling", "name": "Sterling", "emoji": "💰", "domain": "Finance & Markets", "model": "claude-sonnet-4", "workspace": "workspace-sterling"},
    {"id": "sage", "name": "Sage", "emoji": "🦉", "domain": "Family & Les", "model": "claude-sonnet-4", "workspace": "workspace-sage"},
    {"id": "forge", "name": "Forge", "emoji": "🔥", "domain": "Ventures & Revenue", "model": "claude-opus-4-6", "workspace": "workspace-forge"},
    {"id": "beacon", "name": "Beacon", "emoji": "📡", "domain": "Rank & Rent", "model": "claude-sonnet-4", "workspace": "workspace-beacon"},
    {"id": "tribune", "name": "Tribune", "emoji": "⚖️", "domain": "Politics & Religion", "model": "claude-sonnet-4", "workspace": "workspace-tribune"},
    {"id": "pearl", "name": "Pearl", "emoji": "🦪", "domain": "Elise (Personal)", "model": "claude-sonnet-4", "workspace": "workspace-pearl"},
]


def get_workspace_path(ws_name):
    return os.path.join(OPENCLAW_HOME, ws_name)


def get_workspace_size(ws_path):
    try:
        result = subprocess.run(["du", "-sm", ws_path], capture_output=True, text=True, timeout=10)
        return int(result.stdout.split()[0])
    except:
        return 0


def get_memory_stats(ws_path):
    memory_dir = os.path.join(ws_path, "memory")
    memory_md = os.path.join(ws_path, "MEMORY.md")
    files = []
    total_bytes = 0

    if os.path.exists(memory_md):
        size = os.path.getsize(memory_md)
        chars = 0
        try:
            with open(memory_md, "r") as f:
                chars = len(f.read())
        except:
            chars = size
        files.append({"name": "MEMORY.md", "bytes": size, "chars": chars})
        total_bytes += size

    if os.path.isdir(memory_dir):
        for f in sorted(os.listdir(memory_dir)):
            if f.endswith(".md"):
                fp = os.path.join(memory_dir, f)
                size = os.path.getsize(fp)
                files.append({"name": f"memory/{f}", "bytes": size})
                total_bytes += size

    return files, total_bytes


def get_cron_jobs():
    """Load cron jobs from pre-exported file (data/cron_export.json).
    The cron API is internal to OpenClaw and not HTTP-accessible.
    Export via: cron tool (list action) from within an agent session,
    or the update_crons.sh helper script.
    """
    cron_path = DATA_DIR / "cron_export.json"
    if cron_path.exists():
        try:
            with open(cron_path) as f:
                return json.load(f)
        except:
            pass
    return []


def get_disk_usage():
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "available": parts[3], "percent": parts[4]}
    except:
        pass
    return {"total": "?", "used": "?", "available": "?", "percent": "?"}


def get_ram_usage():
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "available": parts[6] if len(parts) > 6 else "?"}
    except:
        pass
    return {"total": "?", "used": "?", "available": "?"}


def get_uptime():
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return "unknown"


def main():
    snapshot = {
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "system": {
            "disk": get_disk_usage(),
            "ram": get_ram_usage(),
            "uptime": get_uptime(),
            "openclaw_version": "v2026.3.13",
            "instance": "AWS t3.small (2GB RAM)",
        },
        "agents": [],
        "cron_jobs": get_cron_jobs(),
    }

    for agent in AGENTS:
        ws_path = get_workspace_path(agent["workspace"])
        ws_size = get_workspace_size(ws_path)
        mem_files, mem_bytes = get_memory_stats(ws_path)

        snapshot["agents"].append({
            **agent,
            "workspace_size_mb": ws_size,
            "memory_bytes": mem_bytes,
            "memory_kb": round(mem_bytes / 1024, 1),
            "memory_files": mem_files,
            "memory_file_count": len(mem_files),
        })

    out_path = DATA_DIR / "snapshot.json"
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print(f"Snapshot written to {out_path}")
    print(f"  Agents: {len(snapshot['agents'])}")
    print(f"  Cron jobs: {len(snapshot['cron_jobs'])}")
    print(f"  Collected at: {snapshot['collected_at']}")


if __name__ == "__main__":
    main()
