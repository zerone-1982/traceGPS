import pandas as pd
import plotly.express as px
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys

def create_map():
    # Set up the file selection window
    root = tk.Tk()
    root.withdraw()  # Hide the main Tkinter window
    root.attributes("-topmost", True)  # Bring the file dialog to the front

    # Open file explorer to select the CSV
    file_path = filedialog.askopenfilename(
        title="Select Voyage CSV Data",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    # If the user cancels the selection
    if not file_path:
        return

    try:
        # 1. Load the data
        df = pd.read_csv(file_path)
        
        # 2. Check for required columns
        required_cols = ['Lat_deg', 'Lon_deg', 'UTC_ISO8601']
        if not all(col in df.columns for col in required_cols):
            messagebox.showerror("Column Error", 
                                 f"Missing columns! Your CSV must have: {', '.join(required_cols)}")
            return

        # 3. Create the Interactive Map
        # We use 'open-street-map' because it does not require an API token
        fig = px.scatter_mapbox(
            df, 
            lat="Lat_deg", 
            lon="Lon_deg", 
            hover_name="UTC_ISO8601", 
            color="SOG_kts" if "SOG_kts" in df.columns else None,
            zoom=13, 
            height=800,
            title=f"Ship Track Visualization: {os.path.basename(file_path)}"
        )

        fig.update_layout(
            mapbox_style="open-street-map",
            margin={"r":0,"t":50,"l":0,"b":0}
        )

        # 4. Save and Open
        # This saves a temporary HTML file in the same folder as the EXE
        output_file = "temp_ship_map.html"
        fig.write_html(output_file)
        
        # Use os.startfile to open the map in the default browser
        os.startfile(output_file)

    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}")

if __name__ == "__main__":
    create_map()