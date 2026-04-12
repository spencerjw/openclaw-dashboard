#!/usr/bin/env python3
"""
Collect OpenClaw agent data and write to data/snapshot.json.
Run locally on the server, then git push to update Streamlit Cloud.
"""

import datetime
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", "/home/clawuser/.openclaw"))
AGENTS_DIR = OPENCLAW_HOME / "agents"
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

IGNORE_AGENT_DIRS = {"codex", "discord"}
WINDOW_DAYS = 30

AGENT_METADATA = {
    "main": {"name": "Nexus", "emoji": "🔗", "domain": "Lead Agent & Coordinator", "workspace": "workspace"},
    "stratton": {"name": "Stratton", "emoji": "📊", "domain": "Telecom (GVTC)", "workspace": "workspace-stratton"},
    "rosie": {"name": "Rosie", "emoji": "🌹", "domain": "HCFC", "workspace": "workspace-rosie"},
    "sawyer": {"name": "Sawyer", "emoji": "🪚", "domain": "Woodworking", "workspace": "workspace-sawyer"},
    "sterling": {"name": "Sterling", "emoji": "💰", "domain": "Finance & Markets", "workspace": "workspace-sterling"},
    "sage": {"name": "Sage", "emoji": "🦉", "domain": "Family", "workspace": "workspace-sage"},
    "forge": {"name": "Forge", "emoji": "🔥", "domain": "Ventures & Revenue", "workspace": "workspace-forge"},
    "beacon": {"name": "Beacon", "emoji": "📡", "domain": "Rank & Rent", "workspace": "workspace-beacon"},
    "tribune": {"name": "Tribune", "emoji": "⚖️", "domain": "Politics & Religion", "workspace": "workspace-tribune"},
    "pearl": {"name": "Pearl", "emoji": "🦪", "domain": "Elise", "workspace": "workspace-pearl"},
    "archer": {"name": "Archer", "emoji": "🏹", "domain": "QC & Deploy Review", "workspace": "workspace-archer"},
}


def parse_iso(ts):
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc)
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def init_usage_bucket(name=None, **extra):
    bucket = {
        "calls": 0,
        "errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
        "input_cost": 0.0,
        "output_cost": 0.0,
        "cache_read_cost": 0.0,
        "cache_write_cost": 0.0,
        "total_cost": 0.0,
    }
    if name is not None:
        bucket["name"] = name
    bucket.update(extra)
    return bucket


def add_usage(bucket, usage, cost, is_error=False):
    bucket["calls"] += 1
    bucket["errors"] += 1 if is_error else 0
    bucket["input_tokens"] += int(usage.get("input") or 0)
    bucket["output_tokens"] += int(usage.get("output") or 0)
    bucket["cache_read_tokens"] += int(usage.get("cacheRead") or 0)
    bucket["cache_write_tokens"] += int(usage.get("cacheWrite") or 0)
    bucket["total_tokens"] += int(usage.get("totalTokens") or 0)
    bucket["input_cost"] += float(cost.get("input") or 0)
    bucket["output_cost"] += float(cost.get("output") or 0)
    bucket["cache_read_cost"] += float(cost.get("cacheRead") or 0)
    bucket["cache_write_cost"] += float(cost.get("cacheWrite") or 0)
    bucket["total_cost"] += float(cost.get("total") or 0)


def rounded_bucket(bucket):
    out = dict(bucket)
    for key in ("input_cost", "output_cost", "cache_read_cost", "cache_write_cost", "total_cost"):
        out[key] = round(float(out.get(key) or 0), 6)
    return out


def sorted_buckets(mapping, limit=None):
    items = [rounded_bucket(v) for v in mapping.values()]
    items.sort(key=lambda x: (x.get("total_cost", 0), x.get("calls", 0)), reverse=True)
    return items[:limit] if limit else items


def get_openclaw_version():
    for candidate in [Path("/usr/lib/node_modules/openclaw/package.json"), OPENCLAW_HOME / "package.json"]:
        if candidate.exists():
            try:
                with open(candidate) as f:
                    return f"v{json.load(f).get('version', 'unknown')}"
            except Exception:
                pass
    return "unknown"


def discover_agents():
    agents = []
    if not AGENTS_DIR.exists():
        return agents

    for path in sorted(AGENTS_DIR.iterdir(), key=lambda p: p.name):
        if not path.is_dir() or path.name in IGNORE_AGENT_DIRS:
            continue
        meta = AGENT_METADATA.get(path.name, {})
        workspace = meta.get("workspace") or ("workspace" if path.name == "main" else f"workspace-{path.name}")
        agents.append({
            "id": path.name,
            "name": meta.get("name") or path.name.replace("-", " ").title(),
            "emoji": meta.get("emoji", "🤖"),
            "domain": meta.get("domain") or path.name.replace("-", " ").title(),
            "workspace": workspace,
        })

    return agents


def get_workspace_path(ws_name):
    return OPENCLAW_HOME / ws_name


def get_workspace_size(ws_path):
    try:
        result = subprocess.run(["du", "-sm", str(ws_path)], capture_output=True, text=True, timeout=10)
        return int(result.stdout.split()[0]) if result.stdout.strip() else 0
    except Exception:
        return 0


def get_memory_stats(ws_path):
    memory_dir = ws_path / "memory"
    memory_md = ws_path / "MEMORY.md"
    files = []
    total_bytes = 0

    if memory_md.exists():
        size = memory_md.stat().st_size
        try:
            chars = len(memory_md.read_text())
        except Exception:
            chars = size
        files.append({"name": "MEMORY.md", "bytes": size, "chars": chars})
        total_bytes += size

    if memory_dir.is_dir():
        for f in sorted(memory_dir.iterdir()):
            if f.suffix == ".md":
                size = f.stat().st_size
                files.append({"name": f"memory/{f.name}", "bytes": size})
                total_bytes += size

    return files, total_bytes


def get_cron_jobs():
    cron_path = DATA_DIR / "cron_export.json"
    if cron_path.exists():
        try:
            with open(cron_path) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_disk_usage():
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "available": parts[3], "percent": parts[4]}
    except Exception:
        pass
    return {"total": "?", "used": "?", "available": "?", "percent": "?"}


def get_ram_usage():
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return {"total": parts[1], "used": parts[2], "available": parts[6] if len(parts) > 6 else "?"}
    except Exception:
        pass
    return {"total": "?", "used": "?", "available": "?"}


def get_uptime():
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return "unknown"


def iter_session_paths(agent_id):
    base = AGENTS_DIR / agent_id / "sessions"
    if not base.exists():
        return
    for path in sorted(base.rglob("*.jsonl")):
        if ".checkpoint." in path.name:
            continue
        yield path


def build_model_costs(agents):
    now = datetime.datetime.now(datetime.timezone.utc)
    day_1 = now - datetime.timedelta(days=1)
    day_7 = now - datetime.timedelta(days=7)
    day_30 = now - datetime.timedelta(days=WINDOW_DAYS)

    provider_30d = defaultdict(lambda: init_usage_bucket())
    model_30d = defaultdict(lambda: init_usage_bucket())
    agent_30d = defaultdict(lambda: init_usage_bucket())
    daily_30d = defaultdict(float)
    latest_models = {}
    latest_model_ts = {}
    top_sessions = []

    totals = {
        "last_24h": init_usage_bucket(name="last_24h"),
        "last_7d": init_usage_bucket(name="last_7d"),
        "last_30d": init_usage_bucket(name="last_30d"),
    }

    agent_names = {a["id"]: a["name"] for a in agents}

    for agent in agents:
        agent_id = agent["id"]
        agent_bucket = agent_30d[agent_id]
        agent_bucket["agent_id"] = agent_id
        agent_bucket["agent_name"] = agent["name"]

        for path in iter_session_paths(agent_id):
            session_bucket = init_usage_bucket(
                session_id=path.name.replace(".jsonl", ""),
                agent_id=agent_id,
                agent_name=agent["name"],
                file=str(path.relative_to(OPENCLAW_HOME)),
                last_timestamp=None,
                provider="?",
                model="?",
            )

            try:
                with open(path) as f:
                    for raw in f:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            entry = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        ts = parse_iso(entry.get("timestamp"))

                        if entry.get("type") == "model_change":
                            if ts and (agent_id not in latest_model_ts or ts > latest_model_ts[agent_id]):
                                latest_model_ts[agent_id] = ts
                                latest_models[agent_id] = entry.get("modelId") or latest_models.get(agent_id)
                            continue

                        if entry.get("type") == "custom" and entry.get("customType") == "model-snapshot":
                            data = entry.get("data") or {}
                            data_ts = parse_iso(data.get("timestamp")) or ts
                            if data_ts and (agent_id not in latest_model_ts or data_ts > latest_model_ts[agent_id]):
                                latest_model_ts[agent_id] = data_ts
                                latest_models[agent_id] = data.get("modelId") or latest_models.get(agent_id)
                            continue

                        if entry.get("type") != "message":
                            continue

                        message = entry.get("message") or {}
                        if message.get("role") != "assistant":
                            continue

                        provider = message.get("provider") or "unknown"
                        model = message.get("model") or "unknown"
                        usage = message.get("usage") or {}
                        cost = usage.get("cost") or {}
                        is_error = message.get("stopReason") == "error"

                        if ts and (agent_id not in latest_model_ts or ts > latest_model_ts[agent_id]):
                            latest_model_ts[agent_id] = ts
                            latest_models[agent_id] = model

                        if not ts or ts < day_30:
                            continue

                        if ts >= day_1:
                            add_usage(totals["last_24h"], usage, cost, is_error=is_error)
                        if ts >= day_7:
                            add_usage(totals["last_7d"], usage, cost, is_error=is_error)
                        add_usage(totals["last_30d"], usage, cost, is_error=is_error)

                        add_usage(agent_bucket, usage, cost, is_error=is_error)
                        provider_bucket = provider_30d[provider]
                        provider_bucket["provider"] = provider
                        add_usage(provider_bucket, usage, cost, is_error=is_error)

                        model_key = f"{provider}:{model}"
                        model_bucket = model_30d[model_key]
                        model_bucket["provider"] = provider
                        model_bucket["model"] = model
                        add_usage(model_bucket, usage, cost, is_error=is_error)

                        add_usage(session_bucket, usage, cost, is_error=is_error)
                        session_bucket["provider"] = provider
                        session_bucket["model"] = model
                        session_bucket["last_timestamp"] = ts.isoformat()
                        daily_30d[ts.date().isoformat()] += float(cost.get("total") or 0)
            except Exception:
                continue

            if session_bucket["calls"] > 0:
                top_sessions.append(rounded_bucket(session_bucket))

    daily_rows = []
    for i in range(WINDOW_DAYS - 1, -1, -1):
        day = (now - datetime.timedelta(days=i)).date().isoformat()
        daily_rows.append({"date": day, "total_cost": round(daily_30d.get(day, 0.0), 6)})

    top_sessions.sort(key=lambda x: x.get("total_cost", 0), reverse=True)

    return {
        "source": "openclaw-session-logs",
        "window_days": WINDOW_DAYS,
        "generated_at": now.isoformat(),
        "totals": {k: rounded_bucket(v) for k, v in totals.items()},
        "by_provider_30d": sorted_buckets(provider_30d),
        "by_model_30d": sorted_buckets(model_30d, limit=20),
        "by_agent_30d": sorted_buckets(agent_30d),
        "daily_30d": daily_rows,
        "top_sessions_30d": top_sessions[:15],
        "latest_models": {
            agent_id: {
                "model": latest_models.get(agent_id, "unknown"),
                "timestamp": latest_model_ts.get(agent_id).isoformat() if latest_model_ts.get(agent_id) else None,
                "agent_name": agent_names.get(agent_id, agent_id),
            }
            for agent_id in agent_names
        },
    }


def main():
    agents = discover_agents()
    model_costs = build_model_costs(agents)

    snapshot = {
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "system": {
            "disk": get_disk_usage(),
            "ram": get_ram_usage(),
            "uptime": get_uptime(),
            "openclaw_version": get_openclaw_version(),
            "instance": "AWS t3.small (2GB RAM)",
        },
        "agents": [],
        "cron_jobs": get_cron_jobs(),
        "model_costs": model_costs,
    }

    latest_models = model_costs.get("latest_models", {})

    for agent in agents:
        ws_path = get_workspace_path(agent["workspace"])
        ws_size = get_workspace_size(ws_path)
        mem_files, mem_bytes = get_memory_stats(ws_path)
        latest_model = (latest_models.get(agent["id"]) or {}).get("model")

        snapshot["agents"].append({
            **agent,
            "model": latest_model or "unknown",
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
    print(f"  Model cost calls (30d): {snapshot['model_costs']['totals']['last_30d']['calls']}")
    print(f"  Model spend (30d): ${snapshot['model_costs']['totals']['last_30d']['total_cost']:.2f}")
    print(f"  Collected at: {snapshot['collected_at']}")


if __name__ == "__main__":
    main()
