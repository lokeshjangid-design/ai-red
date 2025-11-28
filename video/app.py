import streamlit as st
import os
from ultralytics import YOLO
import cv2
import tempfile

st.title("AI Traffic Analyzer 🚦")
st.write("Upload a normal traffic video → get YOLO analysis + dashboard")

uploaded_file = st.file_uploader("Upload Traffic Video", type=["mp4", "mov", "avi"])

if uploaded_file:
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(uploaded_file.read())

    model = YOLO("yolov8n.pt")

    st.info("Processing video... Please wait.")

    cap = cv2.VideoCapture(tfile.name)
    
    # Get original video properties to preserve normal speed
    original_fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter("output.mp4", fourcc, original_fps, 
                          (frame_width, frame_height))

    total_vehicles = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results = model(frame)[0]

        count = 0
        for box in results.boxes:
            cls = int(box.cls)
            if cls in [2,3,5,7]:  # car, motorcycle, bus, truck
                count += 1
                x1,y1,x2,y2 = box.xyxy[0].int().tolist()
                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)

        total_vehicles += count
        out.write(frame)

    cap.release()
    out.release()

    st.success("Processing Complete!")

    st.video("output.mp4")

    st.metric("Total Vehicles Detected", total_vehicles)
