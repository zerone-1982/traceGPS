import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO

st.set_page_config(page_title="ShipNav TraceGPS", layout="wide")

query_params = st.query_params
csv_url  = query_params.get("url",     None)
csv_text = query_params.get("csvdata", None)

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

# ── Phase 2: csvdata passed back from the self-contained iframe HTML ──────────
if csv_text:
    try:
        import urllib.parse
        decoded = urllib.parse.unquote_plus(csv_text)
        df = pd.read_csv(StringIO(decoded))
        label = csv_url.split("f=")[-1] if csv_url and "f=" in csv_url else "device"
        render_map(df, label)
    except Exception as e:
        st.error(f"Parse error: {e}")

# ── Phase 1: URL provided — render the ENTIRE map inside the iframe via JS ───
elif csv_url:
    st.info(f"📡 Fetching from ShipNav device: `{csv_url}`")

    import streamlit.components.v1 as components

    # This self-contained HTML page:
    #  1. Fetches the CSV from the device (browser has local network access)
    #  2. Parses the CSV in JS
    #  3. Renders a Leaflet map with a coloured polyline — fully inside the iframe
    #  No cross-origin redirect needed at all.
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShipNav Track</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#061120; color:#7fdbff; font-family:monospace; }}
  #status {{ padding:10px 14px; font-size:13px; min-height:36px; }}
  #map {{ width:100%; height:calc(100vh - 36px); display:none; }}
  .err {{ color:#fca5a5; }}
  a {{ color:#7fdbff; }}
  .info-box {{
    background:rgba(6,17,32,0.85); color:#7fdbff;
    padding:6px 10px; border-radius:6px; font-family:monospace; font-size:12px;
    line-height:1.6;
  }}
</style>
</head>
<body>
<div id="status">⏳ Fetching CSV from device…</div>
<div id="map"></div>
<script>
const CSV_URL = {repr(csv_url)};

// ── Parse CSV text into array of objects ───────────────────────────────────
function parseCSV(text) {{
  const lines = text.trim().split(/\\r?\\n/);
  if (lines.length < 2) throw new Error('CSV has no data rows');
  const headers = lines[0].split(',').map(h => h.trim());
  return lines.slice(1).map(line => {{
    const vals = line.split(',');
    const obj = {{}};
    headers.forEach((h, i) => obj[h] = vals[i] ? vals[i].trim() : '');
    return obj;
  }}).filter(r => r[headers[0]] !== '');  // skip blank rows
}}

// ── SOG → colour (blue=slow, red=fast) ────────────────────────────────────
function sogColor(sog, maxSog) {{
  if (maxSog === 0) return '#00e5ff';
  const t = Math.min(sog / maxSog, 1);
  // Interpolate: cyan(0) → yellow(0.5) → red(1)
  let r, g, b;
  if (t < 0.5) {{
    const u = t * 2;
    r = Math.round(0   + u * 255); g = Math.round(229 + u * (230-229)); b = Math.round(255 + u * (0-255));
  }} else {{
    const u = (t - 0.5) * 2;
    r = Math.round(255); g = Math.round(230 - u * 230); b = 0;
  }}
  return `rgb(${{r}},${{g}},${{b}})`;
}}

// ── Main ───────────────────────────────────────────────────────────────────
(async function() {{
  const status = document.getElementById('status');
  const mapDiv = document.getElementById('map');

  try {{
    const resp = await fetch(CSV_URL, {{ cache: 'no-cache' }});
    if (!resp.ok) throw new Error('HTTP ' + resp.status + ' ' + resp.statusText);
    const text = await resp.text();
    const rows = parseCSV(text);

    if (rows.length === 0) throw new Error('No data rows in CSV');

    status.textContent = `✅ ${{rows.length}} track points loaded`;
    mapDiv.style.display = 'block';

    // Build lat/lon arrays
    const lats  = rows.map(r => parseFloat(r['Lat_deg'])).filter(v => !isNaN(v));
    const lons  = rows.map(r => parseFloat(r['Lon_deg'])).filter(v => !isNaN(v));
    const sogs  = rows.map(r => parseFloat(r['SOG_kts'] || 0));
    const cogs  = rows.map(r => r['COG_deg']    || '');
    const brgs  = rows.map(r => r['Bearing_deg'] || '');
    const times = rows.map(r => r['UTC_ISO8601'] || '');
    const maxSog = Math.max(...sogs.filter(v => !isNaN(v)));

    // Leaflet map centred on track
    const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const midLon = (Math.min(...lons) + Math.max(...lons)) / 2;
    const map = L.map('map').setView([midLat, midLon], 15);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>'
    }}).addTo(map);

    // Draw coloured segments
    for (let i = 0; i < lats.length - 1; i++) {{
      const col = sogColor(sogs[i], maxSog);
      L.polyline([[lats[i], lons[i]], [lats[i+1], lons[i+1]]], {{
        color: col, weight: 4, opacity: 0.9
      }}).addTo(map);
    }}

    // Circle markers with popups every 10th point
    for (let i = 0; i < lats.length; i += Math.max(1, Math.floor(lats.length/60))) {{
      L.circleMarker([lats[i], lons[i]], {{
        radius: 4, color: sogColor(sogs[i], maxSog),
        fillOpacity: 0.9, weight: 1
      }})
      .bindPopup(
        `<b>${{times[i]}}</b><br>` +
        `SOG: ${{sogs[i].toFixed(2)}} kts<br>` +
        `COG: ${{cogs[i]}}°<br>` +
        `Bearing: ${{brgs[i]}}°`
      ).addTo(map);
    }}

    // Start / end markers
    L.marker([lats[0], lons[0]])
      .bindPopup(`<b>START</b><br>${{times[0]}}`).addTo(map);
    L.marker([lats[lats.length-1], lons[lons.length-1]])
      .bindPopup(`<b>END</b><br>${{times[times.length-1]}}`).addTo(map);

    // Fit map to track bounds
    map.fitBounds(L.latLngBounds(lats.map((la, i) => [la, lons[i]])),
                  {{ padding: [20, 20] }});

    // Info box (legend)
    const info = L.control({{ position: 'bottomleft' }});
    info.onAdd = function() {{
      const d = L.DomUtil.create('div', 'info-box');
      d.innerHTML =
        `<b>Track:</b> ${{rows.length}} pts<br>` +
        `<b>Max SOG:</b> ${{maxSog.toFixed(1)}} kts<br>` +
        `<span style="color:#00e5ff">■</span> Slow &nbsp;` +
        `<span style="color:#ffff00">■</span> Medium &nbsp;` +
        `<span style="color:#ff0000">■</span> Fast`;
      return d;
    }};
    info.addTo(map);

  }} catch(e) {{
    status.innerHTML =
      `<span class="err">❌ ${{e.message}}</span><br>` +
      `Make sure your browser is on the same WiFi/AP as ShipNav.<br>` +
      `Test link: <a href="${{CSV_URL}}" target="_blank">${{CSV_URL}}</a>`;
  }}
}})();
</script>
</body>
</html>"""

    # Height fills most of viewport — the map renders entirely here
    components.html(html, height=700, scrolling=False)

# ── No URL ────────────────────────────────────────────────────────────────────
else:
    st.warning("No device URL received. Click a **🌍 TraceGPS** link in the ShipNav file manager.")
    st.markdown("""
### How to use
1. Connect to the **same WiFi** as ShipNav, or to the ShipNav AP:
   - **SSID:** `ShipNav`  ·  **Password:** `shipnav1`
2. Open the ShipNav web UI (IP shown on device Settings screen)
3. Go to **SD Card Files**
4. Click **🌍 TraceGPS** next to any `.csv` recording

---
### Manual upload
""")
    up = st.file_uploader("Upload a ShipNav CSV", type="csv")
    if up:
        render_map(pd.read_csv(up), up.name)

