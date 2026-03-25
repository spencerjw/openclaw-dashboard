"""
OpenClaw Agent Dashboard
Reads from data/snapshot.json (collected by collect_data.py on the server).
Deploy to Streamlit Cloud from GitHub.
"""

import streamlit as st
import json
import datetime
from pathlib import Path

st.set_page_config(
    page_title="OpenClaw Dashboard",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Load snapshot data ---
SCRIPT_DIR = Path(__file__).parent
SNAPSHOT_PATH = SCRIPT_DIR / "data" / "snapshot.json"


@st.cache_data(ttl=60)
def load_snapshot():
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    return None


def ms_to_datetime(ms):
    if ms:
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    return None


def format_duration(ms):
    if not ms:
        return "N/A"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes / 60:.1f}h"


def time_ago(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    except:
        return "?"


# ============================
# Load data
# ============================
snapshot = load_snapshot()

if not snapshot:
    st.error("No snapshot data found. Run `python3 collect_data.py` on the server first.")
    st.stop()

agents = snapshot.get("agents", [])
cron_jobs = snapshot.get("cron_jobs", [])
system = snapshot.get("system", {})
collected_at = snapshot.get("collected_at", "unknown")

# ============================
# SIDEBAR
# ============================
st.sidebar.title("🔗 OpenClaw Dashboard")
st.sidebar.caption(f"Data: {time_ago(collected_at)}")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Overview", "🤖 Agent Roster", "📁 Memory & Workspaces", "⏰ Cron Jobs", "🖥️ System Health"],
)

st.sidebar.markdown("---")
disk = system.get("disk", {})
st.sidebar.metric("Disk Usage", disk.get("percent", "?"), f"{disk.get('available', '?')} free")
st.sidebar.caption(f"{system.get('openclaw_version', '?')} | {system.get('instance', '?')}")


# ============================
# PAGE: OVERVIEW
# ============================
if page == "🏠 Overview":
    st.title("🔗 OpenClaw Agent Network")
    st.markdown("**Winegarden Command** -- 10 agents, 1 Discord server, multiple domains")

    enabled_jobs = [j for j in cron_jobs if j.get("enabled")]
    error_jobs = [j for j in enabled_jobs if j.get("state", {}).get("consecutiveErrors", 0) > 0]
    total_memory_kb = sum(a.get("memory_kb", 0) for a in agents)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Agents", len(agents))
    col2.metric("Active Cron Jobs", len(enabled_jobs))
    col3.metric("Cron Errors", len(error_jobs), delta=f"-{len(error_jobs)}" if error_jobs else None, delta_color="inverse")
    col4.metric("Total Memory", f"{total_memory_kb:.0f} KB")
    col5.metric("Disk", disk.get("percent", "?"))

    st.caption(f"Last updated: {collected_at}")
    st.markdown("---")

    # Org chart
    st.subheader("Agent Organization")

    nexus = agents[0] if agents else {}
    st.markdown(f"### {nexus.get('emoji', '')} {nexus.get('name', 'Nexus')} -- *{nexus.get('domain', '')}*")
    st.caption(f"Model: {nexus.get('model', '?')} | Workspace: {nexus.get('workspace_size_mb', 0)}MB | Memory: {nexus.get('memory_kb', 0)}KB")

    st.markdown("---")

    cols = st.columns(3)
    for i, agent in enumerate(agents[1:]):
        with cols[i % 3]:
            agent_crons = [j for j in enabled_jobs if j.get("agentId") == agent["id"]]
            agent_errors = [j for j in agent_crons if j.get("state", {}).get("consecutiveErrors", 0) > 0]
            status_icon = "🔴" if agent_errors else "🟢"

            st.markdown(f"**{agent.get('emoji', '')} {agent.get('name', '')}** {status_icon}")
            st.caption(f"{agent.get('domain', '')}")
            st.caption(f"{agent.get('model', '?')} | {agent.get('workspace_size_mb', 0)}MB | {agent.get('memory_kb', 0)}KB mem | {len(agent_crons)} crons")


# ============================
# PAGE: AGENT ROSTER
# ============================
elif page == "🤖 Agent Roster":
    st.title("🤖 Agent Roster")

    for agent in agents:
        mem_files = agent.get("memory_files", [])

        with st.expander(f"{agent.get('emoji', '')} {agent.get('name', '')} -- {agent.get('domain', '')}", expanded=False):
            col1, col2, col3 = st.columns(3)
            col1.metric("Model", agent.get("model", "?"))
            col2.metric("Workspace", f"{agent.get('workspace_size_mb', 0)} MB")
            col3.metric("Memory", f"{agent.get('memory_kb', 0)} KB")

            if mem_files:
                st.markdown("**Memory Files:**")
                MEMORY_LIMIT = 12000
                for mf in mem_files:
                    fname = mf.get("name", "?")
                    fsize = mf.get("bytes", 0)
                    size_str = f"{fsize/1024:.1f}KB" if fsize > 1024 else f"{fsize}B"

                    if fname == "MEMORY.md":
                        chars = mf.get("chars", fsize)
                        pct = chars / MEMORY_LIMIT
                        status = "🔴 OVER" if pct > 1 else "🟡 Full" if pct > 0.85 else "🟢"
                        st.markdown(f"- `{fname}` -- {chars:,} / {MEMORY_LIMIT:,} chars {status}")
                        st.progress(min(pct, 1.0))
                    else:
                        st.markdown(f"- `{fname}` -- {size_str}")
            else:
                st.info("No memory files")


# ============================
# PAGE: MEMORY & WORKSPACES
# ============================
elif page == "📁 Memory & Workspaces":
    st.title("📁 Memory & Workspace Analysis")

    import pandas as pd

    data = []
    for a in agents:
        data.append({
            "Agent": f"{a.get('emoji', '')} {a.get('name', '')}",
            "Memory (KB)": a.get("memory_kb", 0),
            "Memory Files": a.get("memory_file_count", 0),
            "Workspace (MB)": a.get("workspace_size_mb", 0),
        })

    df = pd.DataFrame(data)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Memory Size by Agent")
        st.bar_chart(df.set_index("Agent")["Memory (KB)"])
    with col2:
        st.subheader("Workspace Size by Agent")
        st.bar_chart(df.set_index("Agent")["Workspace (MB)"])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # MEMORY.md health
    st.subheader("MEMORY.md Health Check")
    MEMORY_LIMIT = 12000
    for agent in agents:
        for mf in agent.get("memory_files", []):
            if mf.get("name") == "MEMORY.md":
                chars = mf.get("chars", mf.get("bytes", 0))
                pct = chars / MEMORY_LIMIT
                status = "🔴 OVER LIMIT" if pct > 1 else "🟡 Getting full" if pct > 0.85 else "🟢 OK"
                st.markdown(f"**{agent.get('emoji', '')} {agent.get('name', '')}** -- {chars:,} / {MEMORY_LIMIT:,} chars -- {status}")
                st.progress(min(pct, 1.0))


# ============================
# PAGE: CRON JOBS
# ============================
elif page == "⏰ Cron Jobs":
    st.title("⏰ Cron Jobs")

    enabled = [j for j in cron_jobs if j.get("enabled")]
    disabled = [j for j in cron_jobs if not j.get("enabled")]
    errors = [j for j in enabled if j.get("state", {}).get("consecutiveErrors", 0) > 0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", len(cron_jobs))
    col2.metric("Enabled", len(enabled))
    col3.metric("Disabled", len(disabled))
    col4.metric("In Error", len(errors))

    # Errors first
    if errors:
        st.subheader("🔴 Jobs with Errors")
        for job in errors:
            state = job.get("state", {})
            with st.expander(f"❌ {job.get('name', 'Unnamed')} ({job.get('agentId', '?')})", expanded=True):
                st.error(f"**Error:** {state.get('lastError', 'Unknown')}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Consecutive Errors", state.get("consecutiveErrors", 0))
                last_run = ms_to_datetime(state.get("lastRunAtMs"))
                col2.metric("Last Run", last_run.strftime("%m/%d %H:%M UTC") if last_run else "Never")
                col3.metric("Duration", format_duration(state.get("lastDurationMs")))

    # Active jobs grouped by agent
    st.subheader("✅ Active Jobs")

    agent_lookup = {a.get("id"): a for a in agents}
    agent_jobs = {}
    for job in enabled:
        aid = job.get("agentId", "unknown")
        agent_jobs.setdefault(aid, []).append(job)

    for aid in sorted(agent_jobs.keys()):
        a = agent_lookup.get(aid, {})
        st.markdown(f"### {a.get('emoji', '❓')} {a.get('name', aid)} ({len(agent_jobs[aid])} jobs)")

        for job in sorted(agent_jobs[aid], key=lambda j: j.get("state", {}).get("nextRunAtMs", 0) or 0):
            state = job.get("state", {})
            schedule = job.get("schedule", {})
            next_run = ms_to_datetime(state.get("nextRunAtMs"))
            last_run = ms_to_datetime(state.get("lastRunAtMs"))
            last_status = state.get("lastStatus", "unknown")
            status_icon = "✅" if last_status == "ok" else "❌" if last_status == "error" else "⏳"

            if schedule.get("kind") == "cron":
                sched_str = f"cron: `{schedule.get('expr', '?')}` ({schedule.get('tz', 'UTC')})"
            elif schedule.get("kind") == "at":
                at_time = schedule.get("at", "?")
                sched_str = f"one-shot: {at_time[:16] if len(at_time) > 16 else at_time}"
            elif schedule.get("kind") == "every":
                sched_str = f"every {schedule.get('everyMs', 0)/1000/60:.0f}min"
            else:
                sched_str = "unknown"

            with st.expander(f"{status_icon} {job.get('name', 'Unnamed')} -- {sched_str}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Status", last_status)
                col2.metric("Duration", format_duration(state.get("lastDurationMs")))
                col3.metric("Last Run", last_run.strftime("%m/%d %H:%M") if last_run else "Never")
                col4.metric("Next Run", next_run.strftime("%m/%d %H:%M") if next_run else "N/A")

                if job.get("deleteAfterRun"):
                    st.info("🗑️ One-shot: deletes after run")

                delivery = job.get("delivery", {})
                if delivery.get("mode") and delivery["mode"] != "none":
                    st.caption(f"Delivery: {delivery['mode']} -> {delivery.get('to', delivery.get('channel', 'default'))}")

    if disabled:
        st.subheader("🔘 Disabled Jobs")
        for job in disabled:
            st.markdown(f"- ~~{job.get('name', 'Unnamed')}~~ ({job.get('agentId', '?')})")


# ============================
# PAGE: SYSTEM HEALTH
# ============================
elif page == "🖥️ System Health":
    st.title("🖥️ System Health")

    # Disk
    st.subheader("Disk Usage")
    disk = system.get("disk", {})
    pct_str = disk.get("percent", "0%")
    pct_num = int(pct_str.replace("%", "")) / 100 if "%" in str(pct_str) else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", disk.get("total", "?"))
    col2.metric("Used", disk.get("used", "?"))
    col3.metric("Available", disk.get("available", "?"))
    st.progress(pct_num)

    if pct_num > 0.9:
        st.error("⚠️ Disk above 90% -- cleanup needed!")
    elif pct_num > 0.8:
        st.warning("⚠️ Disk above 80% -- monitor closely")

    # RAM
    st.subheader("System Memory")
    ram = system.get("ram", {})
    col1, col2, col3 = st.columns(3)
    col1.metric("Total RAM", ram.get("total", "?"))
    col2.metric("Used", ram.get("used", "?"))
    col3.metric("Available", ram.get("available", "?"))

    # Uptime + Config
    st.subheader("System Info")
    st.info(f"Uptime: {system.get('uptime', '?')}")

    st.markdown(f"""
    | Setting | Value |
    |---------|-------|
    | Version | {system.get('openclaw_version', '?')} |
    | Instance | {system.get('instance', '?')} |
    | Channels | Discord + Slack |
    | Total Agents | {len(agents)} |
    | Active Cron Jobs | {len([j for j in cron_jobs if j.get('enabled')])} |
    | Discord Bindings | 29 channel-to-agent |
    | Compaction | claude-sonnet-4 (safeguard mode) |
    | Max Concurrent | 4 agents / 8 subagents |
    """)

    st.caption(f"Snapshot collected: {collected_at}")
