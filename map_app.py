import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="ShipNav TraceGPS", layout="wide")

# ── Get CSV URL from query parameter ─────────────────────────────────────────
# The M5Stack web UI passes:  ?url=http://<device-ip>/download?f=voyage_143200.csv
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
    required = [LAT_COL, LON_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"CSV is missing required columns: {missing}")
        st.write("Columns found:", list(df.columns))
        return

    st.success(f"✅ Loaded **{len(df)}** track points  ·  `{source_label}`")

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    if SOG_COL in df.columns:
        c1.metric("Max SOG",  f"{df[SOG_COL].max():.1f} kts")
        c2.metric("Avg SOG",  f"{df[SOG_COL].mean():.1f} kts")
    c3.metric("Track points", len(df))
    if TIME_COL in df.columns and len(df) > 1:
        c4.metric("Period", f"{df[TIME_COL].iloc[0][-8:]} → {df[TIME_COL].iloc[-1][-8:]}")

    color_col = SOG_COL if SOG_COL in df.columns else None
    fig = px.scatter_mapbox(
        df, lat=LAT_COL, lon=LON_COL,
        hover_name=TIME_COL if TIME_COL in df.columns else None,
        hover_data={
            SOG_COL: ":.2f" if SOG_COL in df.columns else False,
            COG_COL: ":.1f" if COG_COL in df.columns else False,
            BRG_COL: ":.1f" if BRG_COL in df.columns else False,
        },
        color=color_col,
        color_continuous_scale="Turbo",
        zoom=14, height=620,
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="SOG (kts)") if color_col else {},
    )
    fig.add_scattermapbox(
        lat=df[LAT_COL], lon=df[LON_COL],
        mode="lines",
        line=dict(width=2, color="#00e5ff"),
        name="Track", hoverinfo="skip",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Raw track data"):
        st.dataframe(df, use_container_width=True)


# ── Main flow ─────────────────────────────────────────────────────────────────
st.title("🚢 ShipNav GPS Trace")

if csv_url:
    # ── The Streamlit cloud server cannot reach your local device IP.
    # ── Solution: inject JS that runs IN THE BROWSER (which IS on the local
    # ── network) to fetch the CSV, then post it back to this Streamlit page
    # ── via st.query_params so we can parse and render it.
    #
    # Two-phase approach:
    #   Phase 1: browser has ?url=... → show JS fetch widget
    #   Phase 2: browser posts CSV text as ?csvdata=... → render map

    csv_data_raw = query_params.get("csvdata", None)

    if csv_data_raw is None:
        # ── Phase 1: inject JS to fetch CSV from device and redirect with data
        st.info(f"📡 Fetching track from device: `{csv_url}`")
        st.markdown("_Your browser is fetching the file from the ShipNav device…_")

        # Use st.components to inject the fetch script
        import streamlit.components.v1 as components
        fetch_script = f"""
        <script>
        (async function() {{
          const statusEl = document.getElementById('fetch-status');
          try {{
            statusEl.textContent = 'Connecting to device…';
            const resp = await fetch("{csv_url}", {{mode: 'cors'}});
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const text = await resp.text();
            statusEl.textContent = 'Got ' + text.split('\\n').length + ' lines. Loading map…';
            // Encode CSV as base64 to safely pass in URL
            const b64 = btoa(unescape(encodeURIComponent(text)));
            // Redirect back to this page with csvdata= param
            const newUrl = window.location.origin + window.location.pathname
                         + '?url={csv_url}&csvdata=' + encodeURIComponent(b64);
            window.location.href = newUrl;
          }} catch(e) {{
            statusEl.innerHTML =
              '<span style="color:#fca5a5">❌ Could not fetch from device: ' + e.message + '<br>' +
              'Make sure your browser is on the same WiFi/AP as ShipNav.<br>' +
              'Try opening the CSV URL directly first: ' +
              '<a style="color:#7fdbff" href="{csv_url}" target="_blank">{csv_url}</a></span>';
          }}
        }})();
        </script>
        <p id="fetch-status" style="font-family:monospace;color:#7fdbff">Starting fetch…</p>
        """
        components.html(fetch_script, height=80)

    else:
        # ── Phase 2: we have the base64-encoded CSV — decode and render
        import base64
        try:
            csv_text = base64.b64decode(csv_data_raw).decode("utf-8")
            df = pd.read_csv(StringIO(csv_text))
            fname = csv_url.split("f=")[-1] if "f=" in csv_url else csv_url
            render_map(df, fname)
        except Exception as e:
            st.error(f"❌ Error parsing CSV data: {e}")
            st.code(csv_data_raw[:500])

else:
    # ── No URL provided — show instructions and manual upload fallback
    st.warning("No device URL received. Click a **🌍 TraceGPS** link from the ShipNav file manager.")
    st.markdown("""
### How to use
1. Connect your phone or laptop to the **same WiFi** as ShipNav,  
   or connect to the ShipNav AP:  **SSID:** `ShipNav` &nbsp;·&nbsp; **Password:** `shipnav1`
2. Open the ShipNav web UI at the IP shown on the device screen
3. Go to **SD Card Files**
4. Click **🌍 TraceGPS** next to any `.csv` file
5. The track will load on the map automatically

---
### Or upload a CSV manually
""")
    uploaded = st.file_uploader("Upload a ShipNav CSV file", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        render_map(df, uploaded.name)
