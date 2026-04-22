import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="ShipNav TraceGPS", layout="wide")

query_params = st.query_params
csv_url  = query_params.get("url",     None)
csv_text = query_params.get("csvdata", None)   # POSTed back from JS after fetch

LAT_COL  = "Lat_deg"
LON_COL  = "Lon_deg"
TIME_COL = "UTC_ISO8601"
SOG_COL  = "SOG_kts"
COG_COL  = "COG_deg"
BRG_COL  = "Bearing_deg"


def render_map(df: pd.DataFrame, label: str):
    missing = [c for c in [LAT_COL, LON_COL] if c not in df.columns]
    if missing:
        st.error(f"CSV missing columns: {missing}. Found: {list(df.columns)}")
        return

    st.success(f"✅ **{len(df)}** track points  ·  `{label}`")

    c1, c2, c3, c4 = st.columns(4)
    if SOG_COL in df.columns:
        c1.metric("Max SOG",  f"{df[SOG_COL].max():.1f} kts")
        c2.metric("Avg SOG",  f"{df[SOG_COL].mean():.1f} kts")
    c3.metric("Points", len(df))
    if TIME_COL in df.columns and len(df) > 1:
        c4.metric("Period",
                  f"{str(df[TIME_COL].iloc[0])[-8:]} → {str(df[TIME_COL].iloc[-1])[-8:]}")

    color_col = SOG_COL if SOG_COL in df.columns else None
    fig = px.scatter_mapbox(
        df, lat=LAT_COL, lon=LON_COL,
        hover_name=TIME_COL if TIME_COL in df.columns else None,
        hover_data={k: True for k in [SOG_COL, COG_COL, BRG_COL] if k in df.columns},
        color=color_col,
        color_continuous_scale="Turbo",
        zoom=14, height=620,
    )
    fig.add_scattermapbox(
        lat=df[LAT_COL], lon=df[LON_COL],
        mode="lines", line=dict(width=2, color="#00e5ff"),
        name="Track", hoverinfo="skip",
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("📋 Raw data"):
        st.dataframe(df, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
st.title("🚢 ShipNav GPS Trace")

# ── Phase 2: CSV text was uploaded from the browser via a form POST ──────────
if csv_text:
    try:
        import urllib.parse
        decoded = urllib.parse.unquote_plus(csv_text)
        df = pd.read_csv(StringIO(decoded))
        label = csv_url.split("f=")[-1] if csv_url and "f=" in csv_url else "device"
        render_map(df, label)
    except Exception as e:
        st.error(f"Parse error: {e}")

# ── Phase 1: We have a device URL — inject JS that fetches + submits CSV ─────
elif csv_url:
    st.info(f"📡 Connecting to ShipNav device: `{csv_url}`")

    import streamlit.components.v1 as components

    # The JS runs in the BROWSER (which is on the same local network as the device).
    # It fetches the CSV, then submits it as a normal HTML form POST back to this
    # Streamlit page — Streamlit receives it as a query param named "csvdata".
    # We URL-encode the CSV so it survives the GET redirect.
    html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin:0; font-family: monospace; background:#061120; color:#7fdbff; padding:8px; }}
  #msg {{ margin-top:6px; font-size:13px; }}
  .err {{ color:#fca5a5; }}
  .ok  {{ color:#34d399; }}
  a    {{ color:#7fdbff; }}
</style>
</head>
<body>
<div id="msg">⏳ Fetching CSV from device…</div>
<script>
(async function() {{
  const msg  = document.getElementById('msg');
  const url  = {repr(csv_url)};
  const base = window.location.href.split('?')[0];

  try {{
    msg.textContent = '⏳ Connecting to ' + url + ' …';
    const resp = await fetch(url, {{ mode: 'cors', cache: 'no-cache' }});
    if (!resp.ok) throw new Error('HTTP ' + resp.status + ' ' + resp.statusText);
    const text = await resp.text();
    const lines = text.trim().split('\\n').length;
    msg.textContent = '✅ Got ' + lines + ' rows — loading map…';

    // Build a redirect URL with csvdata as a query param.
    // encodeURIComponent is safe for any CSV content.
    const encoded = encodeURIComponent(text);
    const redirect = base + '?url=' + encodeURIComponent(url)
                           + '&csvdata=' + encoded;

    // Some browsers cap URL length ~2 MB which is enough for typical tracks.
    // If the CSV is too large we warn and offer direct download instead.
    if (redirect.length > 1900000) {{
      msg.innerHTML = '⚠️ Track file is very large (' + lines +
        ' points). <a href="' + url + '">Download CSV</a> and use manual upload below.';
      return;
    }}

    window.top.location.href = redirect;

  }} catch(e) {{
    msg.innerHTML =
      '<span class="err">❌ ' + e.message + '</span><br>' +
      'Check that your browser is on the <b>same WiFi / AP</b> as ShipNav.<br>' +
      'Test the link directly: <a href="' + url + '" target="_blank">' + url + '</a>';
  }}
}})();
</script>
</body>
</html>
"""
    # height must be tall enough to show the message while redirect happens
    components.html(html, height=120, scrolling=False)

# ── No URL at all ─────────────────────────────────────────────────────────────
else:
    st.warning("No device URL received. Click a **🌍 TraceGPS** link in the ShipNav file manager.")
    st.markdown("""
### How to use
1. Connect to the **same WiFi** as ShipNav, or to the AP:
   - **SSID:** `ShipNav`  **Password:** `shipnav1`
2. Open the ShipNav web UI at the IP shown on the device Settings screen
3. Go to **SD Card Files**
4. Click **🌍 TraceGPS** next to any `.csv` recording

---
### Manual upload
""")
    up = st.file_uploader("Upload a ShipNav CSV", type="csv")
    if up:
        render_map(pd.read_csv(up), up.name)

