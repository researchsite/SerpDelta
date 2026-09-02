import re
import os
import json
import html as html_lib
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from serp import get_live_context, is_disk_cached
from llm import get_llm_answer, compute_delta

load_dotenv()

st.set_page_config(
    page_title="SERP Delta — LLM Knowledge Gap Detector",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .stApp { background: #080b14; color: #e8eaf0; }

  [data-testid="stSidebar"] {
    background: #0d1120 !important;
    border-right: 1px solid rgba(99,102,241,0.15);
  }
  [data-testid="stSidebar"] * { color: #c8cce0 !important; }
  [data-testid="stDecoration"] { display: none; }

  .hero-title {
    font-size: 3rem; font-weight: 800; line-height: 1.1; margin-bottom: 0.25rem;
    background: linear-gradient(135deg, #6366f1 0%, #a78bfa 40%, #38bdf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }
  .hero-sub { font-size: 1.1rem; color: #7c82a0; font-weight: 400; margin-bottom: 1.5rem; }

  .stTextInput > div > div > input {
    background: #111827 !important; border: 1.5px solid rgba(99,102,241,0.35) !important;
    border-radius: 12px !important; color: #e8eaf0 !important;
    font-size: 1rem !important; padding: 0.75rem 1rem !important; transition: border-color 0.2s;
  }
  .stTextInput > div > div > input:focus {
    border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
  }

  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important; border: none !important;
    border-radius: 10px !important; color: white !important; font-weight: 600 !important;
    font-size: 0.95rem !important; padding: 0.6rem 1.5rem !important; transition: all 0.2s !important;
    box-shadow: 0 4px 15px rgba(99,102,241,0.35) !important;
  }
  .stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important; box-shadow: 0 6px 20px rgba(99,102,241,0.5) !important;
  }

  [data-testid="stSidebar"] .stButton > button {
    background: rgba(99,102,241,0.08) !important; border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 8px !important; color: #a5b4fc !important; font-size: 0.82rem !important;
    text-align: left !important; transition: all 0.15s !important; margin-bottom: 3px !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(99,102,241,0.2) !important; border-color: rgba(99,102,241,0.5) !important;
    color: white !important;
  }

  .score-card {
    background: linear-gradient(135deg, #111827 0%, #1a1f35 100%); border-radius: 16px;
    padding: 1.5rem 2rem; border: 1px solid rgba(99,102,241,0.2);
    margin-bottom: 1.5rem; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .score-number { font-size: 4rem; font-weight: 800; line-height: 1; }
  .score-label {
    font-size: 0.8rem; color: #6b7280; text-transform: uppercase;
    letter-spacing: 0.1em; font-weight: 600; margin-top: 0.25rem;
  }
  .verdict-badge {
    display: inline-block; padding: 0.35rem 1rem; border-radius: 999px;
    font-size: 0.9rem; font-weight: 700; letter-spacing: 0.02em; margin-bottom: 0.75rem;
  }
  .badge-fresh      { background: rgba(34,197,94,0.15);   color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
  .badge-slight     { background: rgba(234,179,8,0.15);   color: #facc15; border: 1px solid rgba(234,179,8,0.3); }
  .badge-outdated   { background: rgba(249,115,22,0.15);  color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
  .badge-contradict { background: rgba(239,68,68,0.15);   color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
  .badge-unknown    { background: rgba(107,114,128,0.15); color: #9ca3af; border: 1px solid rgba(107,114,128,0.3); }

  /* ── Live / Cached badge ── */
  .data-badge-live {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3);
    border-radius: 999px; padding: 0.2rem 0.65rem; font-size: 0.75rem;
    font-weight: 700; color: #4ade80; letter-spacing: 0.04em;
  }
  .data-badge-cached {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: rgba(107,114,128,0.12); border: 1px solid rgba(107,114,128,0.3);
    border-radius: 999px; padding: 0.2rem 0.65rem; font-size: 0.75rem;
    font-weight: 700; color: #9ca3af; letter-spacing: 0.04em;
  }
  @keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .live-dot { display:inline-block; width:7px; height:7px; background:#4ade80;
              border-radius:50%; animation:pulse-dot 1.4s ease-in-out infinite; }

  .panel-card {
    background: #111827; border-radius: 14px; padding: 1.25rem 1.5rem;
    border: 1px solid rgba(255,255,255,0.06); height: 100%; min-height: 320px;
  }
  .panel-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
                 letter-spacing: 0.12em; color: #6b7280; margin-bottom: 0.75rem; }
  .panel-title-ai  { border-left: 3px solid #6366f1; padding-left: 0.6rem; color: #a78bfa; }
  .panel-title-web { border-left: 3px solid #38bdf8; padding-left: 0.6rem; color: #7dd3fc; }
  .ai-answer-text  { font-size: 0.95rem; line-height: 1.7; color: #c8cce0; }

  .web-snippet {
    background: rgba(56,189,248,0.05); border: 1px solid rgba(56,189,248,0.12);
    border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 0.75rem;
  }
  .web-snippet a { color: #38bdf8; text-decoration: none; font-weight: 600; font-size: 0.9rem; }
  .web-snippet a:hover { text-decoration: underline; }
  .web-snippet-text { font-size: 0.87rem; color: #9ca3af; margin-top: 0.3rem; line-height: 1.5; }
  .web-snippet-date { font-size: 0.75rem; color: #4b5563; margin-top: 0.2rem; }

  .disc-card {
    background: rgba(239,68,68,0.07); border: 1px solid rgba(239,68,68,0.2);
    border-radius: 10px; padding: 0.7rem 1rem; margin-bottom: 0.5rem;
    font-size: 0.9rem; color: #fca5a5; display: flex; gap: 0.6rem; align-items: flex-start;
  }

  .headline-card {
    background: #111827; border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem; transition: border-color 0.2s;
  }
  .headline-card:hover { border-color: rgba(99,102,241,0.3); }
  .headline-card a { color: #e8eaf0; text-decoration: none; font-weight: 600;
                     font-size: 0.9rem; line-height: 1.4; }
  .headline-card a:hover { color: #a78bfa; }
  .headline-meta { font-size: 0.75rem; color: #4b5563; margin-top: 0.4rem; }

  .what-changed {
    background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.25);
    border-radius: 12px; padding: 1rem 1.25rem; margin: 1rem 0;
    font-size: 0.95rem; color: #c7d2fe; line-height: 1.6;
  }
  .what-changed-label {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #6366f1; margin-bottom: 0.4rem;
  }
  .cutoff-hint { font-size: 0.8rem; color: #4b5563; margin-top: 0.5rem; }

  .gauge-bg { background: #1f2937; border-radius: 999px; height: 8px; overflow: hidden; margin: 0.75rem 0; }
  .gauge-fill-fresh      { background: linear-gradient(90deg,#16a34a,#4ade80); border-radius:999px; height:8px; }
  .gauge-fill-slight     { background: linear-gradient(90deg,#ca8a04,#facc15); border-radius:999px; height:8px; }
  .gauge-fill-outdated   { background: linear-gradient(90deg,#c2410c,#fb923c); border-radius:999px; height:8px; }
  .gauge-fill-contradict { background: linear-gradient(90deg,#b91c1c,#f87171); border-radius:999px; height:8px; }

  /* ── Knowledge Timeline ── */
  .timeline-wrap {
    background: #111827; border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px; padding: 1.25rem 1.5rem; margin: 1rem 0;
  }
  .timeline-title {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #4b5563; margin-bottom: 1rem;
  }
  .timeline-track {
    position: relative; height: 6px; background: #1f2937;
    border-radius: 999px; margin: 0.5rem 0 1.75rem;
  }
  .timeline-fill {
    position: absolute; left: 0; top: 0; height: 6px;
    background: linear-gradient(90deg, #6366f1, #a78bfa); border-radius: 999px;
  }
  .timeline-pin {
    position: absolute; top: 50%; transform: translate(-50%, -50%);
    width: 14px; height: 14px; border-radius: 50%; border: 2px solid #080b14;
  }
  .timeline-pin-cutoff { background: #f87171; }
  .timeline-pin-today  { background: #4ade80; }
  .timeline-label {
    position: absolute; top: 14px; transform: translateX(-50%);
    font-size: 0.68rem; font-weight: 600; white-space: nowrap;
  }
  .timeline-years {
    display: flex; justify-content: space-between;
    font-size: 0.65rem; color: #374151; margin-top: 0.25rem;
  }
  .timeline-legend {
    display: flex; gap: 1.25rem; margin-top: 0.5rem; flex-wrap: wrap;
  }
  .legend-item { display: flex; align-items: center; gap: 0.4rem;
                 font-size: 0.72rem; color: #6b7280; }
  .legend-dot  { width: 10px; height: 10px; border-radius: 50%; }

  /* ── Lie Leaderboard ── */
  .leaderboard-wrap {
    background: #0d1120; border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px; padding: 1.5rem; margin-top: 2rem;
  }
  .leaderboard-title {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #6366f1; margin-bottom: 1.1rem;
    display: flex; align-items: center; gap: 0.5rem;
  }
  .lb-row {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.6rem 0.75rem; border-radius: 10px;
    background: rgba(255,255,255,0.02); margin-bottom: 6px;
    border: 1px solid rgba(255,255,255,0.04); transition: border-color 0.15s;
  }
  .lb-row:hover { border-color: rgba(99,102,241,0.25); }
  .lb-rank { font-size: 0.75rem; font-weight: 800; color: #374151;
             min-width: 1.5rem; text-align: right; }
  .lb-query { font-size: 0.87rem; color: #c8cce0; flex: 1; line-height: 1.3; }
  .lb-bar-bg { width: 80px; height: 6px; background: #1f2937;
               border-radius: 999px; overflow: hidden; flex-shrink: 0; }
  .lb-score-num { font-size: 0.87rem; font-weight: 700; min-width: 2.5rem;
                  text-align: right; flex-shrink: 0; }

  .section-header {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #4b5563; margin: 1.5rem 0 0.75rem;
    display: flex; align-items: center; gap: 0.5rem;
  }
  .section-header::after { content:''; flex:1; height:1px; background:rgba(255,255,255,0.05); }

  .how-card {
    background: #111827; border: 1px solid rgba(99,102,241,0.15);
    border-radius: 14px; padding: 1.25rem; text-align: center;
  }
  .how-card-num {
    font-size: 1.5rem; font-weight: 800;
    background: linear-gradient(135deg,#6366f1,#38bdf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }
  .how-card-text { font-size: 0.87rem; color: #6b7280; margin-top: 0.4rem; line-height: 1.5; }

  .hist-item {
    display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0.5rem;
    border-radius: 8px; background: rgba(255,255,255,0.03); margin-bottom: 4px;
    font-size: 0.82rem; color: #9ca3af;
  }
  .hist-dot-green  { color: #4ade80; font-size: 0.6rem; }
  .hist-dot-yellow { color: #facc15; font-size: 0.6rem; }
  .hist-dot-orange { color: #fb923c; font-size: 0.6rem; }
  .hist-dot-red    { color: #f87171; font-size: 0.6rem; }

  details { border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 10px !important; background: #111827 !important; }
  details > summary { color: #a78bfa !important; font-size: 0.9rem !important; }
  hr { border-color: rgba(255,255,255,0.05) !important; }
  .stSpinner > div { border-top-color: #6366f1 !important; }
  .stDownloadButton > button {
    background: rgba(99,102,241,0.1) !important; border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 8px !important; color: #a78bfa !important; font-size: 0.85rem !important;
  }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_query" not in st.session_state:
    st.session_state.selected_query = ""
if "seen_queries" not in st.session_state:
    st.session_state.seen_queries = set()
if "serp_calls_used" not in st.session_state:
    st.session_state.serp_calls_used = 0
if "serp_cache_hits" not in st.session_state:
    st.session_state.serp_cache_hits = 0


# ── Cached pipeline ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def run_pipeline(query: str):
    with ThreadPoolExecutor(max_workers=2) as pool:
        llm_future = pool.submit(get_llm_answer, query)
        serp_future = pool.submit(get_live_context, query)
        llm_answer = llm_future.result()
        live_data = serp_future.result()
    delta = compute_delta(query, llm_answer, live_data)
    return llm_answer, live_data, delta


# ── Helpers ───────────────────────────────────────────────────────────────────
def staleness_color(score: int) -> str:
    if score <= 20: return "green"
    if score <= 50: return "yellow"
    if score <= 75: return "orange"
    return "red"

def gauge_class(score: int) -> str:
    if score <= 20: return "gauge-fill-fresh"
    if score <= 50: return "gauge-fill-slight"
    if score <= 75: return "gauge-fill-outdated"
    return "gauge-fill-contradict"

def badge_class(verdict: str) -> str:
    return {
        "Fresh": "badge-fresh",
        "Slightly Outdated": "badge-slight",
        "Outdated": "badge-outdated",
        "Contradicted": "badge-contradict",
    }.get(verdict, "badge-unknown")

def score_color(score: int) -> str:
    if score <= 20: return "#4ade80"
    if score <= 50: return "#facc15"
    if score <= 75: return "#fb923c"
    return "#f87171"

def verdict_emoji(verdict: str) -> str:
    return {
        "Fresh": "✅", "Slightly Outdated": "🟡",
        "Outdated": "🟠", "Contradicted": "🔴", "Unverifiable": "⚪",
    }.get(verdict, "❓")

def hist_dot(score: int) -> str:
    cls = "hist-dot-green" if score <= 20 else "hist-dot-yellow" if score <= 50 else "hist-dot-orange" if score <= 75 else "hist-dot-red"
    return f'<span class="{cls}">●</span>'

def parse_cutoff_year(hint: str) -> float:
    """Convert cutoff hint text to a float year for timeline rendering."""
    hint = hint.lower()
    m = re.search(r'20(\d\d)', hint)
    if not m:
        return 2024.0
    year = int("20" + m.group(1))
    if any(w in hint for w in ("early", "q1", "january", "february", "march")):
        offset = 0.1
    elif any(w in hint for w in ("mid", "q2", "q3", "april", "may", "june", "july", "august")):
        offset = 0.5
    elif any(w in hint for w in ("late", "q4", "october", "november", "december")):
        offset = 0.9
    else:
        offset = 0.5
    return year + offset

def render_timeline(cutoff_hint: str) -> str:
    """Return HTML for the knowledge decay timeline."""
    TIMELINE_START = 2020.0
    TIMELINE_END   = 2026.9  # roughly "today"
    span = TIMELINE_END - TIMELINE_START

    cutoff_year = parse_cutoff_year(cutoff_hint)
    cutoff_year = max(TIMELINE_START, min(cutoff_year, TIMELINE_END))

    fill_pct   = round((cutoff_year - TIMELINE_START) / span * 100, 1)
    cutoff_pct = fill_pct
    today_pct  = round((TIMELINE_END - TIMELINE_START) / span * 100, 1)

    # Year labels along the bottom
    year_labels = "".join(
        f'<span>{y}</span>' for y in range(2020, 2027)
    )

    gap_months = round((TIMELINE_END - cutoff_year) * 12)

    return f"""
    <div class="timeline-wrap">
      <div class="timeline-title">
        🕰 Knowledge Decay Timeline
        <span style="color:#9ca3af;font-weight:400;font-size:0.68rem;margin-left:0.5rem;">
          — AI knowledge on this topic is ~{gap_months} months behind today
        </span>
      </div>
      <div class="timeline-track">
        <div class="timeline-fill" style="width:{fill_pct}%"></div>
        <div class="timeline-pin timeline-pin-cutoff" style="left:{cutoff_pct}%">
          <div class="timeline-label" style="color:#f87171;">
            ✂ AI cutoff<br>
            <span style="font-size:0.6rem;color:#6b7280;">{cutoff_hint}</span>
          </div>
        </div>
        <div class="timeline-pin timeline-pin-today" style="left:{today_pct}%">
          <div class="timeline-label" style="color:#4ade80;">TODAY</div>
        </div>
      </div>
      <div class="timeline-years">{year_labels}</div>
      <div class="timeline-legend">
        <div class="legend-item">
          <div class="legend-dot" style="background:#6366f1"></div>
          <span>AI training coverage</span>
        </div>
        <div class="legend-item">
          <div class="legend-dot" style="background:#f87171"></div>
          <span>AI knowledge ends here</span>
        </div>
        <div class="legend-item">
          <div class="legend-dot" style="background:#4ade80"></div>
          <span>Today (web data)</span>
        </div>
        <div class="legend-item" style="color:#4b5563;">
          Gap = <span style="color:#f87171;margin-left:0.25rem;font-weight:700;">{gap_months} months of missing knowledge</span>
        </div>
      </div>
    </div>
    """

def render_leaderboard(history: list) -> None:
    """Render the lie leaderboard using native Streamlit components (avoids raw HTML injection)."""
    sorted_h = sorted(history, key=lambda x: x["staleness_score"], reverse=True)[:10]

    st.markdown("""
    <div style="background:#0d1120;border:1px solid rgba(99,102,241,0.2);
         border-radius:16px;padding:1.25rem 1.5rem;margin-top:1.5rem;">
      <div style="font-size:0.8rem;font-weight:700;text-transform:uppercase;
           letter-spacing:0.1em;color:#6366f1;margin-bottom:1rem;">
        🏆 Lie Leaderboard — Biggest AI Knowledge Gaps This Session
      </div>
    </div>
    """, unsafe_allow_html=True)

    for i, item in enumerate(sorted_h):
        sc     = item["staleness_score"]
        col    = score_color(sc)
        gc     = gauge_class(sc)
        emoji  = verdict_emoji(item["verdict"])
        verdict = item["verdict"]
        q      = item["query"][:60] + ("…" if len(item["query"]) > 60 else "")
        src    = item.get("source", "")
        medal  = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"

        if src == "live":
            src_badge = '<span style="background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.3);border-radius:999px;padding:0.15rem 0.5rem;font-size:0.7rem;font-weight:700;color:#4ade80;">● LIVE</span>'
        elif src == "cached":
            src_badge = '<span style="background:rgba(107,114,128,0.12);border:1px solid rgba(107,114,128,0.3);border-radius:999px;padding:0.15rem 0.5rem;font-size:0.7rem;font-weight:700;color:#9ca3af;">⏱ CACHED</span>'
        else:
            src_badge = ""

        badge_colors = {
            "Fresh":            ("rgba(34,197,94,0.15)",  "#4ade80", "rgba(34,197,94,0.3)"),
            "Slightly Outdated":("rgba(234,179,8,0.15)",  "#facc15", "rgba(234,179,8,0.3)"),
            "Outdated":         ("rgba(249,115,22,0.15)", "#fb923c", "rgba(249,115,22,0.3)"),
            "Contradicted":     ("rgba(239,68,68,0.15)",  "#f87171", "rgba(239,68,68,0.3)"),
        }
        bg, fg, border = badge_colors.get(verdict, ("rgba(107,114,128,0.15)", "#9ca3af", "rgba(107,114,128,0.3)"))
        verdict_html = f'<span style="background:{bg};color:{fg};border:1px solid {border};border-radius:999px;padding:0.15rem 0.55rem;font-size:0.72rem;font-weight:700;">{emoji} {html_lib.escape(verdict)}</span>'

        bar_colors = {"gauge-fill-fresh": "linear-gradient(90deg,#16a34a,#4ade80)", "gauge-fill-slight": "linear-gradient(90deg,#ca8a04,#facc15)", "gauge-fill-outdated": "linear-gradient(90deg,#c2410c,#fb923c)", "gauge-fill-contradict": "linear-gradient(90deg,#b91c1c,#f87171)"}
        bar_grad = bar_colors.get(gc, "linear-gradient(90deg,#6366f1,#a78bfa)")

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.6rem;padding:0.55rem 0.75rem;
             border-radius:10px;background:rgba(255,255,255,0.02);margin-bottom:5px;
             border:1px solid rgba(255,255,255,0.04);">
          <div style="font-size:0.9rem;min-width:1.8rem;text-align:right;">{medal}</div>
          <div style="flex:1;font-size:0.87rem;color:#c8cce0;line-height:1.3;">{html_lib.escape(q)}</div>
          {src_badge}
          {verdict_html}
          <div style="width:72px;height:6px;background:#1f2937;border-radius:999px;overflow:hidden;flex-shrink:0;">
            <div style="width:{sc}%;height:6px;background:{bar_grad};border-radius:999px;"></div>
          </div>
          <div style="font-size:0.87rem;font-weight:700;color:{col};min-width:2.2rem;text-align:right;">{sc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.7rem;color:#374151;margin-top:0.5rem;padding-left:0.5rem;">Sorted by Staleness Score · Higher = AI was more wrong · Run more queries to fill the board</div>', unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:0.5rem 0 0.25rem'>
      <div style='font-size:1.4rem;font-weight:800;background:linear-gradient(135deg,#6366f1,#38bdf8);
           -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;'>
        ⚡ SERP Delta
      </div>
      <div style='font-size:0.78rem;color:#4b5563;margin-top:0.1rem;'>LLM Knowledge Gap Detector</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4b5563;margin-bottom:0.5rem;">🔥 Hot Queries — Expect Big Gaps</div>', unsafe_allow_html=True)

    DEMO_QUERIES = {
        "🤖 AI Race": [
            "What is the latest Claude model from Anthropic?",
            "What is the latest GPT model from OpenAI?",
            "What is Google Gemini's latest model?",
        ],
        "💸 Markets & Crypto": [
            "What is the current US Federal Reserve interest rate?",
            "What is Bitcoin's current price?",
            "What is NVIDIA's current market cap?",
        ],
        "🌍 Geopolitics": [
            "What is the current status of TikTok in the United States?",
            "Who is the current US Secretary of State?",
            "What is the current status of the Russia-Ukraine war?",
        ],
        "🏆 Sports": [
            "Who won the 2025 NBA Championship?",
            "Who is the current Formula 1 World Champion?",
        ],
        "👤 Leadership Changes": [
            "Who is the CEO of OpenAI?",
            "Who is the CEO of Boeing?",
            "Who is the current UK Prime Minister?",
        ],
    }

    selected_query = st.session_state.selected_query
    for category, queries in DEMO_QUERIES.items():
        with st.expander(category, expanded=False):
            for q in queries:
                if st.button(q, key=f"btn_{q}", use_container_width=True):
                    st.session_state.selected_query = q
                    st.session_state["query_input"] = q  # force text_input to update
                    selected_query = q

    st.divider()

    if st.session_state.history:
        st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4b5563;margin-bottom:0.5rem;">Recent Queries</div>', unsafe_allow_html=True)
        for item in reversed(st.session_state.history[-5:]):
            dot = hist_dot(item["staleness_score"])
            truncated = item["query"][:38] + ("…" if len(item["query"]) > 38 else "")
            st.markdown(
                f'<div class="hist-item">{dot}<span>{truncated}</span>'
                f'<span style="margin-left:auto;font-size:0.75rem;color:#374151;">{item["staleness_score"]}</span></div>',
                unsafe_allow_html=True
            )
        st.divider()

    # ── SerpApi usage meter ───────────────────────────────────────────────────
    used         = st.session_state.get("serp_calls_used", 0)
    cache_hits   = st.session_state.get("serp_cache_hits", 0)
    limit        = int(os.getenv("SERPAPI_SESSION_LIMIT", "40"))
    pct          = min(used / limit, 1.0) if limit else 0.0
    queries_left = (limit - used) // 2
    meter_color  = "#4ade80" if pct < 0.6 else "#facc15" if pct < 0.85 else "#f87171"
    st.markdown(f"""
    <div style='margin-bottom:0.75rem;'>
      <div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;
                  color:#4b5563;margin-bottom:0.3rem;'>SerpApi Usage (this session)</div>
      <div style='background:#1f2937;border-radius:999px;height:5px;overflow:hidden;'>
        <div style='width:{pct*100:.0f}%;height:5px;background:{meter_color};border-radius:999px;'></div>
      </div>
      <div style='font-size:0.68rem;color:#4b5563;margin-top:0.3rem;'>
        {used}/{limit} live calls &nbsp;·&nbsp;
        <span style='color:{meter_color};font-weight:600;'>~{queries_left} queries left</span>
      </div>
      {f'<div style="font-size:0.67rem;color:#4ade80;margin-top:0.15rem;">💾 {cache_hits} served from disk cache</div>' if cache_hits else ''}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:0.72rem;color:#374151;line-height:1.8;'>
      SerpApi · Nebius (Llama 3.3) · Streamlit<br>
      Google Search + News · LLM Delta<br>
      <span style='color:#6366f1;'>hackathon.serpapi.com</span>
    </div>
    """, unsafe_allow_html=True)


# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">⚡ SERP Delta</div>', unsafe_allow_html=True)
st.markdown(
    "<div class='hero-sub'>Your AI assistant isn't lying — it's just frozen in time. "
    "<em>This shows you exactly where, and by how much.</em></div>",
    unsafe_allow_html=True
)

# Don't pass value= when using key= — control widget via st.session_state["query_input"] only
if "query_input" not in st.session_state:
    st.session_state["query_input"] = ""

query = st.text_input(
    label="query",
    label_visibility="collapsed",
    placeholder="Ask anything time-sensitive — e.g. Who is the CEO of OpenAI?",
    key="query_input",
)

col_run, col_export_slot, col_spacer = st.columns([1, 2, 6])
with col_run:
    run_btn = st.button("Analyze Gap →", type="primary", use_container_width=True)


# ── Pipeline execution ────────────────────────────────────────────────────────
if run_btn and query.strip():
    q_clean = query.strip()

    # Determine source BEFORE pipeline runs (all on main thread, no session state in threads)
    is_st_cached   = q_clean in st.session_state.seen_queries
    is_disk_hit    = is_disk_cached(q_clean)
    will_hit_api   = not is_st_cached and not is_disk_hit

    # Quota guard — only for live API calls
    if will_hit_api:
        limit = int(os.getenv("SERPAPI_SESSION_LIMIT", "40"))
        if st.session_state.serp_calls_used + 2 > limit:
            st.error(f"SerpApi session limit reached ({limit} calls). Reload to start a new session or increase SERPAPI_SESSION_LIMIT in .env.")
            st.stop()

    with st.spinner("Querying AI + live web simultaneously…"):
        try:
            llm_answer, live_data, delta = run_pipeline(q_clean)
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # Update tracking on main thread (never inside cached/threaded functions)
    if will_hit_api:
        st.session_state.serp_calls_used += 2
    elif not is_st_cached:
        st.session_state.serp_cache_hits += 1

    st.session_state.seen_queries.add(q_clean)

    is_cached = is_st_cached or is_disk_hit

    st.session_state.history.append({
        "query": query,
        "staleness_score": delta["staleness_score"],
        "verdict": delta["verdict"],
        "source": "cached" if is_cached else "live",
    })

    score   = delta["staleness_score"]
    verdict = delta["verdict"]
    emoji   = verdict_emoji(verdict)
    bc      = badge_class(verdict)
    gc      = gauge_class(score)
    sc_col  = score_color(score)

    # ── Live / Cached badge HTML ──────────────────────────────────────────────
    if is_cached:
        data_badge = '<span class="data-badge-cached">⏱ CACHED — served from 5-min cache</span>'
    else:
        data_badge = '<span class="data-badge-live"><span class="live-dot"></span> LIVE — fetched right now</span>'

    # ── Score banner ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="score-card">
      <div style="display:flex;align-items:flex-start;gap:2rem;flex-wrap:wrap;">
        <div>
          <div class="score-number" style="color:{sc_col}">
            {score}<span style="font-size:1.5rem;color:#374151">/100</span>
          </div>
          <div class="score-label">Staleness Score</div>
        </div>
        <div style="flex:1;min-width:200px;">
          <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;flex-wrap:wrap;">
            <span class="verdict-badge {bc}">{emoji} {verdict}</span>
            {data_badge}
          </div>
          <div class="gauge-bg"><div class="{gc}" style="width:{score}%"></div></div>
          <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#374151;margin-top:2px;">
            <span>Fresh</span><span>Outdated</span><span>Contradicted</span>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── What Changed ──────────────────────────────────────────────────────────
    what_changed = delta.get("what_changed", "No significant change detected.")
    cutoff_hint  = delta.get("ai_likely_cutoff_hint", "unknown")
    st.markdown(f"""
    <div class="what-changed">
      <div class="what-changed-label">⚡ What Changed</div>
      {what_changed}
      <div class="cutoff-hint">🕐 AI knowledge on this topic likely ends: <em>{cutoff_hint}</em></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Knowledge Decay Timeline ──────────────────────────────────────────────
    st.markdown(render_timeline(cutoff_hint), unsafe_allow_html=True)

    # ── Two-panel comparison ──────────────────────────────────────────────────
    left, right = st.columns(2, gap="medium")

    with left:
        st.markdown("""
        <div class="panel-card">
          <div class="panel-title panel-title-ai">🧠 What AI Believes</div>
          <div style="font-size:0.75rem;color:#374151;margin-bottom:0.75rem;">
            Based on training data · may be months or years old
          </div>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="ai-answer-text">{llm_answer.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("""
        <div class="panel-card">
          <div class="panel-title panel-title-web">🌐 What the Web Says Today</div>
          <div style="font-size:0.75rem;color:#374151;margin-bottom:0.75rem;">
            Live via SerpApi — Google Search + News · retrieved right now
          </div>
        """, unsafe_allow_html=True)
        for s in live_data["snippets"][:3]:
            date_html = f'<div class="web-snippet-date">📅 {s["date"]}</div>' if s.get("date") else ""
            st.markdown(f"""
            <div class="web-snippet">
              <a href="{s['link']}" target="_blank">{s['title']}</a>
              <div class="web-snippet-text">{s['snippet']}</div>
              {date_html}
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Discrepancies ─────────────────────────────────────────────────────────
    if delta.get("discrepancies"):
        st.markdown('<div class="section-header">⚠️ Discrepancies Found</div>', unsafe_allow_html=True)
        for d in delta["discrepancies"]:
            st.markdown(f'<div class="disc-card"><span>⚠</span><span>{d}</span></div>', unsafe_allow_html=True)

    # ── Recent Headlines ──────────────────────────────────────────────────────
    if live_data.get("headlines"):
        st.markdown('<div class="section-header">📰 Recent Headlines</div>', unsafe_allow_html=True)
        hcols = st.columns(2, gap="medium")
        for i, h in enumerate(live_data["headlines"][:4]):
            with hcols[i % 2]:
                sep = " · " if h.get("source") and h.get("date") else ""
                st.markdown(f"""
                <div class="headline-card">
                  <a href="{h['link']}" target="_blank">{h['title']}</a>
                  <div class="headline-meta">{h.get('source','')}{sep}{h.get('date','')}</div>
                </div>
                """, unsafe_allow_html=True)

    # ── People Also Ask + Sources ─────────────────────────────────────────────
    paa_col, src_col = st.columns(2, gap="medium")
    with paa_col:
        if live_data.get("paa"):
            with st.expander("💬 People Also Ask"):
                for pq in live_data["paa"]:
                    st.markdown(f"- {pq}")
    with src_col:
        if delta.get("sources"):
            with st.expander("🔗 Sources from Delta Analysis"):
                for src in delta["sources"]:
                    st.markdown(f"- [{src}]({src})")

    # ── Export ────────────────────────────────────────────────────────────────
    st.divider()
    export_data = {
        "query": query,
        "llm_answer": llm_answer,
        "delta": delta,
        "live_snippets": live_data["snippets"],
        "headlines": live_data["headlines"],
        "data_freshness": "cached" if is_cached else "live",
    }
    with col_export_slot:
        st.download_button(
            label="⬇ Export JSON Report",
            data=json.dumps(export_data, indent=2),
            file_name=f"serp_delta_{q_clean[:30].replace(' ', '_')}.json",
            mime="application/json",
        )

    # ── Lie Leaderboard (appears after first query, grows with each run) ──────
    if len(st.session_state.history) >= 1:
        render_leaderboard(st.session_state.history)

elif run_btn and not query.strip():
    st.warning("Please enter a query first.")

else:
    # ── Landing state ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:1rem;">How It Works</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    steps = [
        ("01", "Ask", "Type any time-sensitive question about people, prices, events, or policy."),
        ("02", "Dual Fetch", "LLM answers from training data. SerpApi pulls live Google results. Both happen in parallel."),
        ("03", "AI Delta", "A second LLM call audits the gap — surfacing what's outdated, wrong, or missing."),
        ("04", "Score", "You get a Staleness Score (0–100), verdict, discrepancies, timeline, and live sources."),
    ]
    for col, (num, title, text) in zip([c1, c2, c3, c4], steps):
        with col:
            st.markdown(f"""
            <div class="how-card">
              <div class="how-card-num">{num}</div>
              <div style="font-weight:700;font-size:0.9rem;color:#e8eaf0;margin-top:0.3rem;">{title}</div>
              <div class="how-card-text">{text}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Why This Matters</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#111827;border:1px solid rgba(99,102,241,0.15);border-radius:14px;padding:1.5rem 2rem;max-width:700px;">
      <div style="font-size:1rem;color:#c7d2fe;line-height:1.8;">
        LLM hallucination is the <strong style="color:#a78bfa;">#1 blocker to enterprise AI adoption</strong>.
        RAG pipelines take weeks to set up. <strong style="color:#38bdf8;">SERP Delta</strong> is a zero-infrastructure,
        real-time grounding layer — one API call, any question, any model.
      </div>
      <div style="display:flex;gap:2rem;margin-top:1.25rem;flex-wrap:wrap;">
        <div style="text-align:center;">
          <div style="font-size:1.5rem;font-weight:800;color:#6366f1;">~3s</div>
          <div style="font-size:0.72rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">Avg Response</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:1.5rem;font-weight:800;color:#6366f1;">2</div>
          <div style="font-size:0.72rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">Parallel APIs</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:1.5rem;font-weight:800;color:#6366f1;">0</div>
          <div style="font-size:0.72rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">Infrastructure</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:1.5rem;font-weight:800;color:#6366f1;">3</div>
          <div style="font-size:0.72rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">New Features</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:1.5rem;font-size:0.87rem;color:#374151;">
      👈 Pick a <strong style="color:#a78bfa;">Hot Query</strong> from the sidebar,
      or type your own above and hit <strong style="color:#6366f1;">Analyze Gap →</strong>
    </div>
    """, unsafe_allow_html=True)

    # Show leaderboard on landing too if history exists (persists across queries in session)
    if len(st.session_state.history) >= 2:
        render_leaderboard(st.session_state.history)
