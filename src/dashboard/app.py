"""
dashboard/app.py
----------------
Streamlit dashboard for visualising gym progress.

Run with:
    streamlit run src/dashboard/app.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.db.schema import DB_PATH, get_connection

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Gym Tracker",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling — dark industrial theme
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Bebas Neue', sans-serif;
        letter-spacing: 0.05em;
    }
    .metric-card {
        background: #1a1a1a;
        border: 1px solid #2d2d2d;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .metric-value {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 2.4rem;
        color: #f5f5f5;
        line-height: 1;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.3rem;
    }
    .stSelectbox label, .stMultiSelect label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #aaa;
    }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_sets() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            s.id,
            w.started_at,
            w.name        AS workout_name,
            w.duration_mins,
            s.exercise,
            s.set_order,
            s.weight_kg,
            s.reps,
            s.one_rm_kg,
            s.rpe,
            s.notes
        FROM sets s
        JOIN workouts w ON w.id = s.workout_id
        ORDER BY w.started_at, s.exercise, s.set_order
    """, conn)
    conn.close()
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["date"] = df["started_at"].dt.date
    return df


@st.cache_data(ttl=60)
def load_workouts() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, started_at, name, duration_mins
        FROM workouts
        ORDER BY started_at
    """, conn)
    conn.close()
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["date"] = df["started_at"].dt.date
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACCENT = "#e8ff47"   # sharp yellow-green accent
BG_DARK = "#111111"
BG_CARD = "#1a1a1a"
GRID_COL = "#2d2d2d"

PLOTLY_TEMPLATE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#cccccc"),
    xaxis=dict(gridcolor=GRID_COL, linecolor=GRID_COL, zerolinecolor=GRID_COL),
    yaxis=dict(gridcolor=GRID_COL, linecolor=GRID_COL, zerolinecolor=GRID_COL),
)


def metric_card(label: str, value: str) -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """


def best_set_per_session(df: pd.DataFrame) -> pd.DataFrame:
    """For a given exercise dataframe, return the best set (highest 1RM) per session date."""
    return (
        df.sort_values("one_rm_kg", ascending=False)
          .groupby("date", as_index=False)
          .first()
          .sort_values("date")
    )


def volume_per_session(df: pd.DataFrame) -> pd.DataFrame:
    """Total volume (sets × reps × weight) per session date."""
    df = df.copy()
    df["volume"] = df["weight_kg"] * df["reps"]
    return df.groupby("date", as_index=False)["volume"].sum().sort_values("date")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

sets_df = load_sets()
workouts_df = load_workouts()

with st.sidebar:
    st.markdown("# 🏋️ GYM TRACKER")
    st.markdown("---")

    if sets_df.empty:
        st.warning("No data yet. Run the ingestion script first.")
        st.code("python src/ingestion/ingest.py")
        st.stop()

    page = st.radio(
        "View",
        ["📈 Lift Progress", "📅 Session Browser", "📊 Overview"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Date range filter
    min_date = sets_df["date"].min()
    max_date = sets_df["date"].max()
    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (sets_df["date"] >= start_date) & (sets_df["date"] <= end_date)
        filtered_df = sets_df[mask]
    else:
        filtered_df = sets_df

    st.markdown("---")
    st.markdown(
        f"<div style='font-size:0.75rem;color:#555;'>{len(workouts_df)} sessions · "
        f"{sets_df['exercise'].nunique()} exercises · {len(sets_df)} sets</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------

if page == "📊 Overview":
    st.markdown("# OVERVIEW")

    total_sessions = len(workouts_df)
    total_sets = len(sets_df)
    total_volume = (sets_df["weight_kg"] * sets_df["reps"]).sum()
    avg_duration = workouts_df["duration_mins"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Sessions", str(total_sessions)), unsafe_allow_html=True)
    c2.markdown(metric_card("Total Sets", str(total_sets)), unsafe_allow_html=True)
    c3.markdown(metric_card("Total Volume", f"{total_volume/1000:.1f}t"), unsafe_allow_html=True)
    c4.markdown(metric_card("Avg Duration", f"{avg_duration:.0f}m"), unsafe_allow_html=True)

    st.markdown("### Sessions per month")
    workouts_df["month"] = pd.to_datetime(workouts_df["started_at"]).dt.to_period("M").astype(str)
    monthly = workouts_df.groupby("month").size().reset_index(name="count")
    fig = px.bar(monthly, x="month", y="count", color_discrete_sequence=[ACCENT])
    fig.update_layout(**PLOTLY_TEMPLATE, showlegend=False, height=280,
                      margin=dict(l=0, r=0, t=10, b=0))
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top exercises by total volume")
    vol_by_ex = sets_df.copy()
    vol_by_ex["volume"] = vol_by_ex["weight_kg"] * vol_by_ex["reps"]
    top_ex = (
        vol_by_ex.groupby("exercise")["volume"]
        .sum()
        .sort_values(ascending=True)
        .tail(15)
        .reset_index()
    )
    fig2 = px.bar(top_ex, x="volume", y="exercise", orientation="h",
                  color_discrete_sequence=[ACCENT])
    fig2.update_layout(**PLOTLY_TEMPLATE, showlegend=False, height=400,
                       margin=dict(l=0, r=0, t=10, b=0))
    fig2.update_traces(marker_line_width=0)
    st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Lift Progress
# ---------------------------------------------------------------------------

elif page == "📈 Lift Progress":
    st.markdown("# LIFT PROGRESS")

    all_exercises = sorted(filtered_df["exercise"].unique())
    selected_exercise = st.selectbox("Select exercise", all_exercises)

    ex_df = filtered_df[filtered_df["exercise"] == selected_exercise].copy()

    if ex_df.empty:
        st.info("No data for this exercise in the selected date range.")
        st.stop()

    # Summary metrics for this exercise
    best_1rm = ex_df["one_rm_kg"].max()
    best_weight = ex_df[ex_df["reps"] >= 1]["weight_kg"].max()
    total_sessions_ex = ex_df["date"].nunique()
    total_sets_ex = len(ex_df)
    latest_1rm = (
        ex_df[ex_df["one_rm_kg"].notna()]
        .sort_values("date")
        .groupby("date", as_index=False)["one_rm_kg"]
        .max()
        .iloc[-1]["one_rm_kg"]
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(metric_card("Best Est. 1RM", f"{best_1rm:.1f} kg"), unsafe_allow_html=True)
    c2.markdown(metric_card("Current Est. 1RM", f"{latest_1rm:.1f} kg"), unsafe_allow_html=True)
    c3.markdown(metric_card("Best Weight", f"{best_weight:.1f} kg"), unsafe_allow_html=True)
    c4.markdown(metric_card("Sessions", str(total_sessions_ex)), unsafe_allow_html=True)
    c5.markdown(metric_card("Total Sets", str(total_sets_ex)), unsafe_allow_html=True)

    st.markdown("### Estimated 1RM over time")
    st.caption("Best set per session · Brzycki formula: weight x (36 / (37-reps)")

    best_per_session = best_set_per_session(ex_df)

    fig = go.Figure()
    # Trend line (rolling average)
    if len(best_per_session) >= 3:
        best_per_session["rolling"] = best_per_session["one_rm_kg"].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=best_per_session["date"],
            y=best_per_session["rolling"],
            mode="lines",
            line=dict(color=ACCENT, width=2, dash="dash"),
            name="3-session avg",
            opacity=0.6,
        ))

    fig.add_trace(go.Scatter(
        x=best_per_session["date"],
        y=best_per_session["one_rm_kg"],
        mode="lines+markers",
        line=dict(color=ACCENT, width=2.5),
        marker=dict(size=7, color=ACCENT, line=dict(color=BG_DARK, width=1.5)),
        name="Est. 1RM",
        hovertemplate="<b>%{x}</b><br>Est. 1RM: %{y:.1f} kg<extra></extra>",
    ))

    fig.update_layout(**PLOTLY_TEMPLATE, height=340, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Volume per session")
        vol = volume_per_session(ex_df)
        fig2 = px.bar(vol, x="date", y="volume", color_discrete_sequence=[ACCENT])
        fig2.update_layout(**PLOTLY_TEMPLATE, height=260, margin=dict(l=0, r=0, t=10, b=0),
                           showlegend=False)
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        st.markdown("### Weight & reps breakdown")
        fig3 = px.scatter(
            ex_df, x="date", y="weight_kg",
            size="reps", color="reps",
            color_continuous_scale=["#333", ACCENT],
            hover_data={"reps": True, "weight_kg": True, "set_order": True},
        )
        fig3.update_layout(**PLOTLY_TEMPLATE, height=260, margin=dict(l=0, r=0, t=10, b=0),
                           showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### All sets")
    display_cols = ["date", "workout_name", "set_order", "weight_kg", "reps", "one_rm_kg", "rpe", "notes"]
    st.dataframe(
        ex_df[display_cols].sort_values(["date", "set_order"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Page: Session Browser
# ---------------------------------------------------------------------------

elif page == "📅 Session Browser":
    st.markdown("# SESSION BROWSER")

    session_options = (
        workouts_df.assign(label=lambda d: d["started_at"].dt.strftime("%d %b %Y") + "  —  " + d["name"])
        .sort_values("started_at", ascending=False)
    )

    selected_label = st.selectbox("Select session", session_options["label"].tolist())
    selected_row = session_options[session_options["label"] == selected_label].iloc[0]

    session_sets = sets_df[sets_df["started_at"] == selected_row["started_at"]]

    c1, c2, c3 = st.columns(3)
    c1.markdown(metric_card("Workout", selected_row["name"]), unsafe_allow_html=True)
    c2.markdown(metric_card("Duration", f"{int(selected_row['duration_mins'])}m" if pd.notna(selected_row["duration_mins"]) else "—"), unsafe_allow_html=True)
    c3.markdown(metric_card("Total Sets", str(len(session_sets))), unsafe_allow_html=True)

    st.markdown("### Sets logged")
    for exercise, ex_sets in session_sets.groupby("exercise"):
        st.markdown(f"**{exercise}**")
        display = ex_sets[["set_order", "weight_kg", "reps", "one_rm_kg", "rpe", "notes"]].copy()
        display.columns = ["Set", "Weight (kg)", "Reps", "Est. 1RM", "RPE", "Notes"]
        st.dataframe(display, use_container_width=True, hide_index=True)
