"""
OpenClaw Agent Dashboard — Mobile-first ops + model cost view
"""

import datetime
import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OpenClaw Dashboard",
    page_icon="🔗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
section[data-testid="stMainBlockContainer"] { padding: 1rem 0.5rem; }
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.2rem !important; }
h3 { font-size: 1rem !important; }
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
</style>""",
    unsafe_allow_html=True,
)

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
    if not ms:
        return "N/A"
    s = ms / 1000
    return f"{s:.0f}s" if s < 60 else f"{s/60:.1f}m" if s < 3600 else f"{s/3600:.1f}h"


def time_ago(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.datetime.now(datetime.timezone.utc) - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        h = delta.seconds // 3600
        return f"{h}h ago" if h > 0 else f"{delta.seconds // 60}m ago"
    except Exception:
        return "?"


def money(value):
    return f"${float(value or 0):,.2f}"


def compact_tokens(value):
    value = int(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def df_from_rows(rows, columns):
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns]


snapshot = load_snapshot()
if not snapshot:
    st.error("No data. Run `python3 collect_data.py` on server.")
    st.stop()

agents = snapshot.get("agents", [])
cron_jobs = snapshot.get("cron_jobs", [])
system = snapshot.get("system", {})
model_costs = snapshot.get("model_costs", {})
collected_at = snapshot.get("collected_at", "unknown")
disk = system.get("disk", {})
ram = system.get("ram", {})

enabled_jobs = [j for j in cron_jobs if j.get("enabled")]
error_jobs = [j for j in enabled_jobs if j.get("state", {}).get("consecutiveErrors", 0) > 0]
total_mem_kb = sum(a.get("memory_kb", 0) for a in agents)
cost_totals = model_costs.get("totals", {})

st.markdown(
    """
<div style="text-align:center; padding: 0.5rem 0 0.2rem 0;">
<span style="font-size:2.5rem;">🔗</span><br>
<span style="font-size:1.6rem; font-weight:700; letter-spacing:2px;">WINEGARDEN COMMAND</span><br>
<span style="font-size:0.75rem; color:#888; letter-spacing:3px;">AGENT NETWORK OPERATIONS</span>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<style>
div[data-testid="stVerticalBlock"] > div:has(> div > div > button#fab_refresh) {
    position: fixed; bottom: 24px; right: 24px; z-index: 999;
}
button#fab_refresh {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    border: 1px solid rgba(96,165,250,0.4) !important;
    border-radius: 50% !important; width: 48px !important; height: 48px !important;
    padding: 0 !important; font-size: 20px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5) !important;
    min-height: 0 !important;
}
button#fab_refresh:hover {
    border-color: rgba(96,165,250,0.8) !important;
    box-shadow: 0 4px 25px rgba(96,165,250,0.3) !important;
}
</style>
""",
    unsafe_allow_html=True,
)

if st.button("🔄", key="fab_refresh", help="Refresh data"):
    st.cache_data.clear()
    st.toast("🔄 Refreshing dashboard...", icon="🔗")
    st.rerun()

error_color = "#ff4b4b" if error_jobs else "#00c853"
error_label = f"🔴 {len(error_jobs)} ERROR{'S' if len(error_jobs) != 1 else ''}" if error_jobs else "🟢 ALL SYSTEMS GO"
disk_pct_val = int(str(disk.get("percent", "0%")).replace("%", "") or 0)
disk_color = "#ff4b4b" if disk_pct_val > 90 else "#ff9800" if disk_pct_val > 80 else "#00c853"

st.markdown(
    f"""
<div style="text-align:center; padding:0.4rem; margin:0.3rem 0; border-radius:8px; background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border:1px solid #333;">
<span style="color:{error_color}; font-weight:700; font-size:0.9rem;">{error_label}</span>
<span style="color:#666; margin:0 0.5rem;">|</span>
<span style="color:{disk_color}; font-size:0.85rem;">💾 {disk.get('percent','?')}</span>
<span style="color:#666; margin:0 0.5rem;">|</span>
<span style="color:#4fc3f7; font-size:0.85rem;">⏰ {len(enabled_jobs)} jobs</span>
</div>
""",
    unsafe_allow_html=True,
)

st.caption(f"📡 Updated {time_ago(collected_at)} | {system.get('openclaw_version', '?')} | {system.get('uptime', '?')}")

agent_icons = ""
for agent in agents:
    has_err = any(j.get("state", {}).get("consecutiveErrors", 0) > 0 for j in enabled_jobs if j.get("agentId") == agent["id"])
    border = "2px solid #ff4b4b" if has_err else "2px solid #333"
    agent_icons += f"""<div style="display:inline-block; text-align:center; margin:4px; padding:6px 8px; border-radius:10px; border:{border}; background:#1a1a2e; min-width:55px;">
<div style="font-size:1.4rem;">{agent.get('emoji','')}</div>
<div style="font-size:0.6rem; color:#aaa; margin-top:2px;">{agent.get('name','')}</div>
</div>"""

st.markdown(f"""<div style="text-align:center; padding:0.3rem 0; overflow-x:auto; white-space:nowrap;">{agent_icons}</div>""", unsafe_allow_html=True)

st.markdown(
    f"""
<div style="display:flex; justify-content:space-around; padding:0.5rem 0; text-align:center;">
<div><span style="font-size:1.5rem; font-weight:700; color:#4fc3f7;">{len(agents)}</span><br><span style="font-size:0.65rem; color:#888;">AGENTS</span></div>
<div><span style="font-size:1.5rem; font-weight:700; color:#ce93d8;">{len(enabled_jobs)}</span><br><span style="font-size:0.65rem; color:#888;">CRON JOBS</span></div>
<div><span style="font-size:1.5rem; font-weight:700; color:#{'ff4b4b' if error_jobs else '00c853'};">{len(error_jobs)}</span><br><span style="font-size:0.65rem; color:#888;">ERRORS</span></div>
<div><span style="font-size:1.5rem; font-weight:700; color:#ffb74d;">{total_mem_kb:.0f}</span><br><span style="font-size:0.65rem; color:#888;">KB MEMORY</span></div>
</div>
""",
    unsafe_allow_html=True,
)

if cost_totals:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("24h", money(cost_totals.get("last_24h", {}).get("total_cost")))
    c2.metric("7d", money(cost_totals.get("last_7d", {}).get("total_cost")))
    c3.metric("30d", money(cost_totals.get("last_30d", {}).get("total_cost")))
    c4.metric("30d calls", f"{cost_totals.get('last_30d', {}).get('calls', 0):,}")

ops_tab, cost_tab = st.tabs(["Ops", "Model Cost"])

with ops_tab:
    if error_jobs:
        st.markdown("---")
        st.subheader("🔴 Cron Errors")
        for job in error_jobs:
            state = job.get("state", {})
            st.error(f"**{job.get('name')}** ({job.get('agentId')})\n\n{state.get('lastError', '?')}\n\nConsecutive: {state.get('consecutiveErrors', 0)}")

    st.markdown("---")
    st.subheader("🤖 Agents")

    for agent in agents:
        ws_mb = agent.get("workspace_size_mb", 0)
        mem_kb = agent.get("memory_kb", 0)
        agent_crons = len([j for j in enabled_jobs if j.get("agentId") == agent["id"]])
        has_errors = any(j.get("state", {}).get("consecutiveErrors", 0) > 0 for j in enabled_jobs if j.get("agentId") == agent["id"])
        status = "🔴" if has_errors else "🟢"

        with st.expander(f"{agent.get('emoji','')} {agent.get('name','')} {status} — {agent.get('domain','')}"):
            st.caption(f"Model: {agent.get('model','?')} | {ws_mb}MB workspace | {mem_kb}KB memory | {agent_crons} crons")

            for mf in agent.get("memory_files", []):
                if mf.get("name") == "MEMORY.md":
                    chars = mf.get("chars", mf.get("bytes", 0))
                    pct = chars / 12000
                    label = "🔴 OVER" if pct > 1 else "🟡 85%+" if pct > 0.85 else "🟢"
                    st.markdown(f"MEMORY.md: {chars:,}/12,000 {label}")
                    st.progress(min(pct, 1.0))

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

    st.markdown("---")
    st.subheader("📁 Memory Health")

    LIMIT = 12000
    for agent in agents:
        for mf in agent.get("memory_files", []):
            if mf.get("name") == "MEMORY.md":
                chars = mf.get("chars", mf.get("bytes", 0))
                pct = chars / LIMIT
                if pct > 0.7:
                    label = "🔴" if pct > 1 else "🟡" if pct > 0.85 else "🟢"
                    st.markdown(f"{label} **{agent.get('emoji','')} {agent.get('name','')}** — {chars:,}/{LIMIT:,}")
                    st.progress(min(pct, 1.0))

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

    st.markdown("---")
    st.subheader("⏰ Upcoming Cron Jobs")

    upcoming = sorted(
        [j for j in enabled_jobs if j.get("state", {}).get("nextRunAtMs")],
        key=lambda j: j["state"]["nextRunAtMs"],
    )[:15]

    for job in upcoming:
        state = job.get("state", {})
        next_run = ms_to_dt(state["nextRunAtMs"])
        agent_emoji = next((a["emoji"] for a in agents if a["id"] == job.get("agentId")), "❓")
        one_shot = " 🗑️" if job.get("deleteAfterRun") else ""
        st.markdown(f"**{next_run.strftime('%m/%d %H:%M')}** — {agent_emoji} {job.get('name','')}{one_shot}")

    disabled = [j for j in cron_jobs if not j.get("enabled")]
    if disabled:
        st.caption(f"+ {len(disabled)} disabled jobs")

    st.markdown("---")
    st.subheader("🖥️ System")

    pct_str = disk.get("percent", "0%")
    pct_num = int(str(pct_str).replace("%", "") or 0) / 100 if "%" in str(pct_str) else 0

    st.markdown(f"**Disk:** {disk.get('used','?')} / {disk.get('total','?')} ({pct_str})")
    st.progress(pct_num)
    if pct_num > 0.9:
        st.error("Disk above 90%!")

    st.markdown(f"**RAM:** {ram.get('used','?')} / {ram.get('total','?')} (avail: {ram.get('available','?')})")
    st.markdown(f"**Uptime:** {system.get('uptime','?')}")
    st.caption(f"{system.get('openclaw_version','?')} | {system.get('instance','?')} | Snapshot: {collected_at[:19]}")

with cost_tab:
    st.markdown("---")
    st.subheader("💸 Model Cost")
    st.caption(f"Source: {model_costs.get('source', 'unknown')} | Window: last {model_costs.get('window_days', 30)} days | Generated {time_ago(model_costs.get('generated_at', collected_at))}")

    totals_24h = cost_totals.get("last_24h", {})
    totals_7d = cost_totals.get("last_7d", {})
    totals_30d = cost_totals.get("last_30d", {})

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    c1.metric("Spend, 24h", money(totals_24h.get("total_cost")), delta=f"{totals_24h.get('calls', 0):,} calls")
    c2.metric("Spend, 7d", money(totals_7d.get("total_cost")), delta=f"{compact_tokens(totals_7d.get('total_tokens', 0))} tokens")
    c3.metric("Spend, 30d", money(totals_30d.get("total_cost")), delta=f"{totals_30d.get('errors', 0):,} error turns")
    c4.metric("Cache write, 30d", money(totals_30d.get("cache_write_cost")), delta=f"{compact_tokens(totals_30d.get('cache_write_tokens', 0))} cache write")

    provider_rows = model_costs.get("by_provider_30d", [])
    if provider_rows:
        st.markdown("#### Providers")
        provider_df = df_from_rows(
            [
                {
                    "Provider": row.get("provider", "?"),
                    "Cost": round(row.get("total_cost", 0), 2),
                    "Calls": row.get("calls", 0),
                    "Errors": row.get("errors", 0),
                    "Tokens": row.get("total_tokens", 0),
                }
                for row in provider_rows
            ],
            ["Provider", "Cost", "Calls", "Errors", "Tokens"],
        )
        st.dataframe(provider_df, use_container_width=True, hide_index=True)

    daily_rows = model_costs.get("daily_30d", [])
    if daily_rows:
        st.markdown("#### Daily Spend, 30d")
        daily_df = pd.DataFrame(daily_rows)
        daily_df["date"] = pd.to_datetime(daily_df["date"])
        daily_df = daily_df.set_index("date")
        st.bar_chart(daily_df)

    model_rows = model_costs.get("by_model_30d", [])
    if model_rows:
        st.markdown("#### Top Models")
        model_df = df_from_rows(
            [
                {
                    "Model": row.get("model", "?"),
                    "Provider": row.get("provider", "?"),
                    "Cost": round(row.get("total_cost", 0), 2),
                    "Calls": row.get("calls", 0),
                    "Tokens": row.get("total_tokens", 0),
                    "Input Cost": round(row.get("input_cost", 0), 2),
                    "Output Cost": round(row.get("output_cost", 0), 2),
                    "Cache Write": round(row.get("cache_write_cost", 0), 2),
                }
                for row in model_rows
            ],
            ["Model", "Provider", "Cost", "Calls", "Tokens", "Input Cost", "Output Cost", "Cache Write"],
        )
        st.dataframe(model_df, use_container_width=True, hide_index=True)

    agent_rows = model_costs.get("by_agent_30d", [])
    if agent_rows:
        st.markdown("#### Spend by Agent")
        agent_df = df_from_rows(
            [
                {
                    "Agent": f"{next((a.get('emoji', '') for a in agents if a.get('id') == row.get('agent_id')), '')} {row.get('agent_name', row.get('agent_id', '?'))}".strip(),
                    "Cost": round(row.get("total_cost", 0), 2),
                    "Calls": row.get("calls", 0),
                    "Errors": row.get("errors", 0),
                    "Tokens": row.get("total_tokens", 0),
                }
                for row in agent_rows
            ],
            ["Agent", "Cost", "Calls", "Errors", "Tokens"],
        )
        st.dataframe(agent_df, use_container_width=True, hide_index=True)

    session_rows = model_costs.get("top_sessions_30d", [])
    if session_rows:
        st.markdown("#### Most Expensive Sessions")
        session_df = df_from_rows(
            [
                {
                    "Agent": row.get("agent_name", row.get("agent_id", "?")),
                    "Model": row.get("model", "?"),
                    "Provider": row.get("provider", "?"),
                    "Cost": round(row.get("total_cost", 0), 2),
                    "Calls": row.get("calls", 0),
                    "Last Seen": row.get("last_timestamp", "")[:19].replace("T", " "),
                }
                for row in session_rows
            ],
            ["Agent", "Model", "Provider", "Cost", "Calls", "Last Seen"],
        )
        st.dataframe(session_df, use_container_width=True, hide_index=True)
