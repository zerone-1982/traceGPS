import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="Ship Tracker", layout="wide")

st.title("🚢 Voyage Visualizer")
st.write("Upload your voyage CSV file to view the path on an interactive map.")

# 2. Streamlit's Native File Uploader (Replaces Tkinter)
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        # Load the data
        df = pd.read_csv(uploaded_file)
        
        # Check for required columns
        required_cols = ['Lat_deg', 'Lon_deg', 'UTC_ISO8601']
        if all(col in df.columns for col in required_cols):
            
            # 3. Create Map using OpenStreetMap (Free)
            fig = px.scatter_mapbox(
                df, 
                lat="Lat_deg", 
                lon="Lon_deg", 
                hover_name="UTC_ISO8601", 
                color="SOG_kts" if "SOG_kts" in df.columns else None,
                zoom=14, 
                height=700,
                title="Ship Trajectory"
            )

            fig.update_layout(
                mapbox_style="open-street-map",
                margin={"r":0,"t":40,"l":0,"b":0}
            )

            # 4. Display the map in the browser
            st.plotly_chart(fig, use_container_width=True)
            
            # Show a data preview below the map
            #st.subheader("Recent Data Points")
            #st.dataframe(df.tail(10))
            
        else:
            st.error(f"Error: Missing columns. Your CSV must have: {required_cols}")
            
    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
