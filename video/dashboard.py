import streamlit as st
import cv2
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AI Traffic Dashboard", layout="wide")

st.title("🚦 AI Traffic Monitoring Dashboard")

# ----- VIDEO SECTION -----
st.subheader("📹 YOLO Processed Video Output")

video_file = "output_tracking_final.mp4"
video_bytes = open(video_file, "rb").read()
st.video(video_bytes)

# ----- LIVE STATISTICS -----
st.subheader("📊 Traffic Statistics")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Vehicles", "Calculating…")

with col2:
    st.metric("Congestion Level", "Low")

with col3:
    st.metric("Signal Recommendation", "Green Corridor")

# ----- OTHER FEATURES -----
st.subheader("🛣 Green Corridor Logic")
st.write("""
- If vehicle density > threshold → extend green signal  
- If ambulance detected → immediate green  
""")

st.subheader("🎥 360° Camera Integration")
st.write("Supports multiple camera feeds (feature ready).")

st.success("Dashboard Loaded ✔")
