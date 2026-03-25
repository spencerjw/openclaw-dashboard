"""
OpenClaw Agent Dashboard — Single Page, Mobile-First
"""

import streamlit as st
import json
import datetime
from pathlib import Path

st.set_page_config(
    page_title="OpenClaw Dashboard",
    page_icon="🔗",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Hide sidebar completely on mobile
st.markdown("""<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
section[data-testid="stMainBlockContainer"] { padding: 1rem 0.5rem; }
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.2rem !important; }
h3 { font-size: 1rem !important; }
</style>""", unsafe_allow_html=True)

SCRIPT_DIR = Path(__file__).parent
SNAPSHOT_PATH = SCRIPT_DIR / "data" / "snapshot.json"


@st.cache_data(ttl=60)
def load_snapshot():
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    return None


def ms_to_dt(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc) if ms else None


def fmt_dur(ms):
    if not ms: return "N/A"
    s = ms / 1000
    return f"{s:.0f}s" if s < 60 else f"{s/60:.1f}m" if s < 3600 else f"{s/3600:.1f}h"


def time_ago(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        delta = datetime.datetime.now(datetime.timezone.utc) - dt
        if delta.days > 0: return f"{delta.days}d ago"
        h = delta.seconds // 3600
        return f"{h}h ago" if h > 0 else f"{delta.seconds // 60}m ago"
    except:
        return "?"


snapshot = load_snapshot()
if not snapshot:
    st.error("No data. Run `python3 collect_data.py` on server.")
    st.stop()

agents = snapshot.get("agents", [])
cron_jobs = snapshot.get("cron_jobs", [])
system = snapshot.get("system", {})
collected_at = snapshot.get("collected_at", "unknown")
disk = system.get("disk", {})
ram = system.get("ram", {})

enabled_jobs = [j for j in cron_jobs if j.get("enabled")]
error_jobs = [j for j in enabled_jobs if j.get("state", {}).get("consecutiveErrors", 0) > 0]
total_mem_kb = sum(a.get("memory_kb", 0) for a in agents)

# ============================
# HEADER
# ============================
st.title("🔗 OpenClaw Dashboard")
st.caption(f"Updated {time_ago(collected_at)} | {system.get('openclaw_version', '?')}")

# ============================
# TOP METRICS
# ============================
c1, c2, c3 = st.columns(3)
c1.metric("Agents", len(agents))
c2.metric("Cron Jobs", len(enabled_jobs))
c3.metric("Errors", len(error_jobs))

c1, c2, c3 = st.columns(3)
c1.metric("Disk", disk.get("percent", "?"))
c2.metric("RAM", ram.get("used", "?"))
c3.metric("Memory", f"{total_mem_kb:.0f}KB")

# ============================
# CRON ERRORS (if any)
# ============================
if error_jobs:
    st.markdown("---")
    st.subheader("🔴 Cron Errors")
    for job in error_jobs:
        state = job.get("state", {})
        st.error(f"**{job.get('name')}** ({job.get('agentId')})\n\n{state.get('lastError', '?')}\n\nConsecutive: {state.get('consecutiveErrors', 0)}")

# ============================
# AGENT ROSTER
# ============================
st.markdown("---")
st.subheader("🤖 Agents")

for agent in agents:
    mem_kb = agent.get("memory_kb", 0)
    ws_mb = agent.get("workspace_size_mb", 0)
    agent_crons = len([j for j in enabled_jobs if j.get("agentId") == agent["id"]])
    has_errors = any(j.get("state", {}).get("consecutiveErrors", 0) > 0 for j in enabled_jobs if j.get("agentId") == agent["id"])
    status = "🔴" if has_errors else "🟢"

    with st.expander(f"{agent.get('emoji','')} {agent.get('name','')} {status} — {agent.get('domain','')}"):
        st.caption(f"Model: {agent.get('model','?')} | {ws_mb}MB workspace | {mem_kb}KB memory | {agent_crons} crons")

        # MEMORY.md health
        for mf in agent.get("memory_files", []):
            if mf.get("name") == "MEMORY.md":
                chars = mf.get("chars", mf.get("bytes", 0))
                pct = chars / 12000
                label = "🔴 OVER" if pct > 1 else "🟡 85%+" if pct > 0.85 else "🟢"
                st.markdown(f"MEMORY.md: {chars:,}/12,000 {label}")
                st.progress(min(pct, 1.0))

        # Agent's cron jobs
        agent_jobs = [j for j in enabled_jobs if j.get("agentId") == agent["id"]]
        if agent_jobs:
            for job in sorted(agent_jobs, key=lambda j: j.get("state", {}).get("nextRunAtMs", 0) or 0):
                state = job.get("state", {})
                schedule = job.get("schedule", {})
                status_icon = "✅" if state.get("lastStatus") == "ok" else "❌" if state.get("lastStatus") == "error" else "⏳"
                next_run = ms_to_dt(state.get("nextRunAtMs"))
                next_str = next_run.strftime("%m/%d %H:%M") if next_run else "—"

                sched = ""
                if schedule.get("kind") == "cron":
                    sched = f"`{schedule.get('expr','?')}`"
                elif schedule.get("kind") == "at":
                    sched = "one-shot"
                elif schedule.get("kind") == "every":
                    sched = f"every {schedule.get('everyMs',0)/1000/60:.0f}m"

                one_shot = " 🗑️" if job.get("deleteAfterRun") else ""
                st.markdown(f"{status_icon} **{job.get('name','')}**{one_shot}\n{sched} → next: {next_str} | last: {fmt_dur(state.get('lastDurationMs'))}")

# ============================
# MEMORY OVERVIEW
# ============================
st.markdown("---")
st.subheader("📁 Memory Health")

LIMIT = 12000
for agent in agents:
    for mf in agent.get("memory_files", []):
        if mf.get("name") == "MEMORY.md":
            chars = mf.get("chars", mf.get("bytes", 0))
            pct = chars / LIMIT
            if pct > 0.7:  # Only show agents approaching limit
                label = "🔴" if pct > 1 else "🟡" if pct > 0.85 else "🟢"
                st.markdown(f"{label} **{agent.get('emoji','')} {agent.get('name','')}** — {chars:,}/{LIMIT:,}")
                st.progress(min(pct, 1.0))

# Show agents without MEMORY.md concern
ok_agents = []
for agent in agents:
    has_mem = False
    for mf in agent.get("memory_files", []):
        if mf.get("name") == "MEMORY.md":
            if mf.get("chars", mf.get("bytes", 0)) / LIMIT <= 0.7:
                ok_agents.append(f"{agent.get('emoji','')} {agent.get('name','')}")
            has_mem = True
    if not has_mem:
        ok_agents.append(f"{agent.get('emoji','')} {agent.get('name','')} (none)")
if ok_agents:
    st.caption(f"🟢 OK: {', '.join(ok_agents)}")

# ============================
# ALL CRON JOBS TIMELINE
# ============================
st.markdown("---")
st.subheader("⏰ Upcoming Cron Jobs")

upcoming = sorted(
    [j for j in enabled_jobs if j.get("state", {}).get("nextRunAtMs")],
    key=lambda j: j["state"]["nextRunAtMs"]
)[:15]

for job in upcoming:
    state = job.get("state", {})
    next_run = ms_to_dt(state["nextRunAtMs"])
    agent_emoji = next((a["emoji"] for a in agents if a["id"] == job.get("agentId")), "❓")
    one_shot = " 🗑️" if job.get("deleteAfterRun") else ""

    st.markdown(f"**{next_run.strftime('%m/%d %H:%M')}** — {agent_emoji} {job.get('name','')}{one_shot}")

# Disabled jobs count
disabled = [j for j in cron_jobs if not j.get("enabled")]
if disabled:
    st.caption(f"+ {len(disabled)} disabled jobs")

# ============================
# SYSTEM
# ============================
st.markdown("---")
st.subheader("🖥️ System")

pct_str = disk.get("percent", "0%")
pct_num = int(pct_str.replace("%", "")) / 100 if "%" in str(pct_str) else 0

st.markdown(f"**Disk:** {disk.get('used','?')} / {disk.get('total','?')} ({pct_str})")
st.progress(pct_num)
if pct_num > 0.9:
    st.error("Disk above 90%!")

st.markdown(f"**RAM:** {ram.get('used','?')} / {ram.get('total','?')} (avail: {ram.get('available','?')})")
st.markdown(f"**Uptime:** {system.get('uptime','?')}")
st.caption(f"{system.get('openclaw_version','?')} | {system.get('instance','?')} | Snapshot: {collected_at[:19]}")
