from __future__ import annotations

import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Store Intelligence Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
        .hero {
            padding: 1.2rem 1.3rem;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(24,24,32,0.96), rgba(40,40,54,0.96));
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 10px 30px rgba(0,0,0,0.18);
            margin-bottom: 1rem;
        }
        .hero h1 { margin: 0; font-size: 2.2rem; }
        .hero p { margin: 0.35rem 0 0 0; opacity: 0.82; }
        .metric-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.75;
            margin-bottom: 0.35rem;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.1;
        }
        .metric-sub {
            margin-top: 0.25rem;
            font-size: 0.82rem;
            opacity: 0.7;
        }
        .section-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin: 0.4rem 0 0.75rem 0;
        }
        .anomaly-card {
            padding: 1rem 1rem;
            border-radius: 16px;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .sev-critical { background: rgba(145, 44, 52, 0.32); }
        .sev-warn { background: rgba(148, 116, 18, 0.30); }
        .sev-info { background: rgba(52, 98, 145, 0.26); }
        .small-muted { opacity: 0.72; font-size: 0.9rem; }
        .upload-box {
            padding: 1rem 1rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 1rem;
        }
        .empty-state {
            padding: 1.2rem 1.1rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.035);
            border: 1px dashed rgba(255,255,255,0.18);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers
# -----------------------------
BASE_URL_DEFAULT = "http://localhost:8000"
DEFAULT_STORE_ID = "STORE_BLR_002"
DEFAULT_CAMERA_ID = "CAM_ENTRY_01"

if "analytics_loaded" not in st.session_state:
    st.session_state["analytics_loaded"] = False


@st.cache_data(ttl=10)
def fetch_json(base_url: str, path: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=10)
def fetch_metrics(base_url: str, store_id: str) -> dict[str, Any]:
    return fetch_json(base_url, f"/stores/{store_id}/metrics")


@st.cache_data(ttl=10)
def fetch_funnel(base_url: str, store_id: str) -> dict[str, Any]:
    return fetch_json(base_url, f"/stores/{store_id}/funnel")


@st.cache_data(ttl=10)
def fetch_heatmap(base_url: str, store_id: str) -> dict[str, Any]:
    return fetch_json(base_url, f"/stores/{store_id}/heatmap")


@st.cache_data(ttl=10)
def fetch_anomalies(base_url: str, store_id: str) -> dict[str, Any]:
    return fetch_json(base_url, f"/stores/{store_id}/anomalies")


def metric_card(label: str, value: str, sub: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def severity_class(severity: str) -> str:
    s = (severity or "").upper()
    if s == "CRITICAL":
        return "sev-critical"
    if s == "WARN":
        return "sev-warn"
    return "sev-info"


def save_uploaded_file(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    temp_file = NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(uploaded_file.getbuffer())
    temp_file.flush()
    temp_file.close()
    return Path(temp_file.name)


def run_detection(
    video_path: Path,
    store_id: str,
    camera_id: str,
    stride: int,
    conf: float,
    dwell_seconds: int,
    max_missed_frames: int,
    confirm_hits: int,
) -> tuple[int, str, Path]:
    events_path = Path(video_path.parent) / f"{video_path.stem}_events.jsonl"
    cmd = [
        sys.executable,
        "-m",
        "pipeline.detect",
        "--video",
        str(video_path),
        "--store-id",
        store_id,
        "--camera-id",
        camera_id,
        "--out",
        str(events_path),
        "--stride",
        str(stride),
        "--conf",
        str(conf),
        "--dwell-seconds",
        str(dwell_seconds),
        "--max-missed-frames",
        str(max_missed_frames),
        "--confirm-hits",
        str(confirm_hits),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    combined = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
    return proc.returncode, combined.strip(), events_path


def ingest_events(base_url: str, events_path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with events_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    resp = requests.post(
        f"{base_url.rstrip('/')}/events/ingest",
        json={"events": events},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.title("Controls")
base_url = st.sidebar.text_input("API Base URL", BASE_URL_DEFAULT)
store_id = st.sidebar.text_input("Store ID", DEFAULT_STORE_ID)

st.sidebar.markdown("---")
st.sidebar.subheader("CCTV Ingestion")
uploaded_video = st.sidebar.file_uploader("Upload CCTV footage", type=["mp4", "mov", "avi", "mkv"])
camera_id = st.sidebar.text_input("Camera ID", DEFAULT_CAMERA_ID)
stride = st.sidebar.slider("Frame stride", min_value=1, max_value=30, value=10, step=1)
conf = st.sidebar.slider("Detection confidence", min_value=0.10, max_value=0.90, value=0.50, step=0.05)
dwell_seconds = st.sidebar.slider("Dwell threshold (sec)", min_value=5, max_value=120, value=30, step=5)
max_missed_frames = st.sidebar.slider("Max missed frames", min_value=5, max_value=60, value=15, step=1)
confirm_hits = st.sidebar.slider("Confirm hits", min_value=1, max_value=5, value=3, step=1)
process_clicked = st.sidebar.button("Process and ingest footage")

st.sidebar.markdown("---")
load_current_clicked = st.sidebar.button("Load current store analytics")
refresh = st.sidebar.button("Refresh data")

layout_path_candidates = [
    Path("dashboard/assets/store_layout.png"),
    Path("dashboard/assets/store_layout.jpg"),
    Path("assets/store_layout.png"),
    Path("assets/store_layout.jpg"),
    Path("store_layout.png"),
    Path("store_layout.jpg"),
]
layout_path = next((p for p in layout_path_candidates if p.exists()), None)

if refresh:
    st.cache_data.clear()
    st.rerun()

if load_current_clicked:
    st.session_state["analytics_loaded"] = True
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# CCTV upload & process
# -----------------------------
st.markdown(
    """
    <div class="upload-box">
        <div class="section-title">Upload CCTV Footage</div>
        <div class="small-muted">Upload a video, run the detection pipeline, and ingest the generated events directly into the backend.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if process_clicked:
    if not uploaded_video:
        st.error("Please upload a CCTV video first.")
    else:
        with st.spinner("Processing video and ingesting events..."):
            temp_video_path = save_uploaded_file(uploaded_video)
            try:
                code, output, events_path = run_detection(
                    temp_video_path,
                    store_id=store_id,
                    camera_id=camera_id,
                    stride=stride,
                    conf=conf,
                    dwell_seconds=dwell_seconds,
                    max_missed_frames=max_missed_frames,
                    confirm_hits=confirm_hits,
                )
                if code != 0:
                    st.error("Detection pipeline failed.")
                    st.code(output or "No output produced.", language="text")
                else:
                    ingest_result = ingest_events(base_url, events_path)
                    st.session_state["analytics_loaded"] = True
                    st.session_state["process_status"] = "success"
                    st.session_state["process_details"] = {
                        "detection_output": output,
                        "ingest_result": ingest_result,
                        "events_path": str(events_path),
                    }
                    st.cache_data.clear()
                    st.success(
                        f"Processed footage and ingested {ingest_result.get('inserted', 0)} events successfully."
                    )
                    st.code(output or "Pipeline completed.", language="text")
                    st.rerun()
            finally:
                try:
                    temp_video_path.unlink(missing_ok=True)
                except Exception:
                    pass

if st.session_state.get("process_status") == "success":
    details = st.session_state.get("process_details", {})
    st.success(
        f"Last footage run was successful. Ingested {details.get('ingest_result', {}).get('inserted', 0)} events."
    )
    if details.get("detection_output"):
        with st.expander("Last pipeline output", expanded=False):
            st.code(details["detection_output"], language="text")

# -----------------------------
# Header
# -----------------------------
st.markdown(
    f"""
    <div class="hero">
        <h1>🏪 Store Intelligence Dashboard</h1>
        <p>Live retail analytics from CCTV events, billing activity, and POS conversion data.</p>
        <p class="small-muted">Store: <b>{store_id}</b> · API: <b>{base_url}</b></p>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Empty state or analytics data
# -----------------------------
if not st.session_state.get("analytics_loaded"):
    st.info("No footage processed yet. Upload a CCTV video to generate analytics, or load the current store data from the backend.")

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Unique Visitors", "—", "Awaiting footage")
    with c2:
        metric_card("Entries", "—", "Awaiting footage")
    with c3:
        metric_card("Purchases", "—", "Awaiting footage")
    with c4:
        metric_card("Conversion Rate", "—", "Awaiting footage")
    with c5:
        metric_card("Queue Depth", "—", "Awaiting footage")

    st.markdown('<div class="section-title">Conversion Funnel</div>', unsafe_allow_html=True)
    st.empty()

    st.markdown('<div class="section-title">Store Layout / Heatmap</div>', unsafe_allow_html=True)
    if layout_path:
        st.image(str(layout_path), caption="Store layout used for zone reasoning", use_container_width=True)
    else:
        st.info("Store layout image not found. Place it at dashboard/assets/store_layout.png for a floorplan view.")

    st.markdown('<div class="section-title">Anomalies</div>', unsafe_allow_html=True)
    st.caption("No events processed yet.")
    st.stop()

# -----------------------------
# Load data
# -----------------------------
try:
    metrics = fetch_metrics(base_url, store_id)
    funnel = fetch_funnel(base_url, store_id)
    heatmap = fetch_heatmap(base_url, store_id)
    anomalies = fetch_anomalies(base_url, store_id)
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
except Exception as exc:
    st.error(f"Could not load data from the API: {exc}")
    st.stop()

# -----------------------------
# Summary cards
# -----------------------------
st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Unique Visitors", str(metrics.get("unique_visitors", 0)), "Distinct visitor IDs")
with c2:
    metric_card("Entries", str(metrics.get("entry_count", 0)), "People who entered")
with c3:
    metric_card("Purchases", str(metrics.get("purchase_count", 0)), "POS-linked conversions")
with c4:
    metric_card("Conversion Rate", f"{metrics.get('conversion_rate', 0):.2%}", "Purchases / Visitors")
with c5:
    metric_card("Queue Depth", str(metrics.get("current_queue_depth", 0)), "Latest billing queue")

st.caption(f"Last refreshed: {last_updated}")

st.divider()

# -----------------------------
# Funnel and heatmap
# -----------------------------
left, right = st.columns([1.25, 1])

with left:
    st.markdown('<div class="section-title">Conversion Funnel</div>', unsafe_allow_html=True)
    funnel_df = pd.DataFrame(
        {
            "Stage": ["Entry", "Zone Visit", "Billing Queue", "Purchase"],
            "Count": [
                funnel.get("entry", 0),
                funnel.get("zone_visit", 0),
                funnel.get("billing_queue", 0),
                funnel.get("purchase", 0),
            ],
        }
    )
    fig = px.funnel(
        funnel_df,
        x="Count",
        y="Stage",
        color_discrete_sequence=["#77bdfb"],
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f2f2f2"),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    drop = funnel.get("dropoff", {})
    d1, d2, d3 = st.columns(3)
    d1.metric("Entry → Zone Drop-off", f"{drop.get('entry_to_zone_visit', 0):.2f}%")
    d2.metric("Zone → Billing Drop-off", f"{drop.get('zone_visit_to_billing_queue', 0):.2f}%")
    d3.metric("Billing → Purchase Drop-off", f"{drop.get('billing_queue_to_purchase', 0):.2f}%")

with right:
    st.markdown('<div class="section-title">Store Layout / Heatmap</div>', unsafe_allow_html=True)
    if layout_path:
        st.image(str(layout_path), caption="Store layout used for zone reasoning", use_container_width=True)
    else:
        st.info("Store layout image not found. Place it at dashboard/assets/store_layout.png for a floorplan view.")

    heatmap_df = pd.DataFrame(heatmap.get("zones", []))
    if not heatmap_df.empty:
        heatmap_df = heatmap_df.sort_values("visit_count", ascending=False)
        bar = px.bar(
            heatmap_df,
            x="zone_id",
            y="visit_count",
            hover_data=["avg_dwell_ms"],
            color="visit_count",
            color_continuous_scale="Blues",
        )
        bar.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f2f2f2"),
            height=320,
            xaxis_title="Zone",
            yaxis_title="Visits",
        )
        st.plotly_chart(bar, use_container_width=True)
    else:
        st.warning("No zone data available yet.")

st.divider()

# -----------------------------
# Detailed tables
# -----------------------------
col_a, col_b = st.columns([1.2, 1])

with col_a:
    st.markdown('<div class="section-title">Zone Heatmap Table</div>', unsafe_allow_html=True)
    if not heatmap_df.empty:
        display_df = heatmap_df[["zone_id", "visit_count", "avg_dwell_ms"]].copy()
        display_df["avg_dwell_ms"] = display_df["avg_dwell_ms"].map(lambda x: f"{x:,.0f}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No heatmap rows to display.")

with col_b:
    st.markdown('<div class="section-title">Anomalies</div>', unsafe_allow_html=True)
    anomaly_list = anomalies.get("anomalies", [])
    if anomaly_list:
        for anomaly in anomaly_list:
            cls = severity_class(anomaly.get("severity", "INFO"))
            st.markdown(
                f"""
                <div class="anomaly-card {cls}">
                    <div style="font-weight:700; font-size:1.05rem;">{anomaly.get('type', 'UNKNOWN')}</div>
                    <div style="margin-top:0.2rem; opacity:0.85;">Severity: {anomaly.get('severity', 'INFO')}</div>
                    <div style="margin-top:0.55rem; opacity:0.9;">{anomaly.get('suggested_action', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("No anomalies detected for this store right now.")

st.divider()

# -----------------------------
# Footer
# -----------------------------
st.caption(
    "Built from live API data: /metrics, /funnel, /heatmap, and /anomalies. "
    "Refresh the page after new ingestion or POS import runs."
)
