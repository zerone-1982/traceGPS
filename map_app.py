import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import StringIO

st.set_page_config(page_title="ShipNav TraceGPS", layout="wide")
st.title("🚢 ShipNav GPS Trace")

# ── Get CSV URL from query parameter ─────────────────────────────────────────
# The M5Stack device passes: ?url=http://<device-ip>/download?f=voyage_HHMMSS.csv
query_params = st.query_params
csv_url = query_params.get("url", None)

# ── Column names produced by the ShipNav firmware ────────────────────────────
LAT_COL  = "Lat_deg"
LON_COL  = "Lon_deg"
TIME_COL = "UTC_ISO8601"
SOG_COL  = "SOG_kts"
COG_COL  = "COG_deg"
BRG_COL  = "Bearing_deg"

def render_map(df: pd.DataFrame, source_label: str):
    """Render the plotly mapbox track from a dataframe."""
    required = [LAT_COL, LON_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"CSV is missing required columns: {missing}")
        st.write("Columns found:", list(df.columns))
        return

    st.success(f"Loaded {len(df)} track points  ·  {source_label}")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    if SOG_COL in df.columns:
        col1.metric("Max SOG", f"{df[SOG_COL].max():.1f} kts")
        col2.metric("Avg SOG", f"{df[SOG_COL].mean():.1f} kts")
    if COG_COL in df.columns:
        col3.metric("Track points", len(df))
    if TIME_COL in df.columns:
        col4.metric("Duration", f"{df[TIME_COL].iloc[0]}  →  {df[TIME_COL].iloc[-1]}")

    # Map
    color_col = SOG_COL if SOG_COL in df.columns else None
    fig = px.scatter_mapbox(
        df,
        lat=LAT_COL,
        lon=LON_COL,
        hover_name=TIME_COL if TIME_COL in df.columns else None,
        hover_data={
            SOG_COL: ":.2f" if SOG_COL in df.columns else False,
            COG_COL: ":.1f" if COG_COL in df.columns else False,
            BRG_COL: ":.1f" if BRG_COL in df.columns else False,
        },
        color=color_col,
        color_continuous_scale="Turbo",
        zoom=14,
        height=650,
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="SOG (kts)") if color_col else {},
    )
    # Connect dots with a line
    fig.add_scattermapbox(
        lat=df[LAT_COL],
        lon=df[LON_COL],
        mode="lines",
        line=dict(width=2, color="#00e5ff"),
        name="Track",
        hoverinfo="skip",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Raw data table (expandable)
    with st.expander("📋 Raw track data"):
        st.dataframe(df, use_container_width=True)


# ── Main flow ─────────────────────────────────────────────────────────────────
if csv_url:
    st.info(f"Fetching CSV from device: `{csv_url}`")
    try:
        # Fetch the CSV from the M5Stack device's web server
        resp = requests.get(csv_url, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        # Extract filename from URL for display
        fname = csv_url.split("f=")[-1] if "f=" in csv_url else csv_url
        render_map(df, fname)
    except requests.exceptions.ConnectionError:
        st.error(
            "❌ Could not connect to the ShipNav device. "
            "Make sure your browser is on the **same WiFi network** as the device, "
            "or connected to the device's AP (`ShipNav` / `shipnav1`)."
        )
    except requests.exceptions.Timeout:
        st.error("❌ Connection timed out. The device may be out of range or powered off.")
    except Exception as e:
        st.error(f"❌ Error loading CSV: {e}")

else:
    st.warning("No CSV URL received. Click a **🌍 TraceGPS** link from the ShipNav file manager.")
    st.markdown("""
    ### How to use
    1. Connect your phone/laptop to the same WiFi as ShipNav  
       *(or connect to the `ShipNav` AP and open `http://192.168.4.1`)*
    2. Go to **SD Card Files** in the ShipNav web UI
    3. Click **🌍 TraceGPS** next to any `.csv` file
    4. The track will appear on the map here automatically

    ---
    ### Or upload a CSV manually
    """)
    uploaded = st.file_uploader("Upload a ShipNav CSV file", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        render_map(df, uploaded.name)
