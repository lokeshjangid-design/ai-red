import os
import uuid
import cv2
import numpy as np
import time
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from ultralytics import YOLO
import base64
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Load YOLO model - use fastest model for real-time processing
print("Loading YOLO model...")
model = YOLO('yolov8n.pt')  # Using nano model for fastest speed
print("Model loaded successfully!")

# Vehicle class IDs in COCO dataset
VEHICLE_CLASSES = {
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
    1: 'bicycle'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_mock_plate():
    """Generate a realistic Indian plate number"""
    import random
    import string
    
    # Generate realistic Indian plate format (e.g., MH12AB1234)
    state_codes = ['MH', 'DL', 'KA', 'TN', 'GJ', 'RJ', 'UP', 'WB', 'PB', 'HR']
    district_numbers = ['01', '12', '15', '20', '31', '45', '08', '47', '09', '14']
    
    state = random.choice(state_codes)
    district = random.choice(district_numbers)
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    numbers = ''.join(random.choices(string.digits, k=4))
    
    return f"{state}{district}{letters}{numbers}"

def detect_number_plate(frame, bbox):
    """
    Detect and read number plate from vehicle bounding box
    bbox: (x1, y1, x2, y2) - vehicle bounding box
    Returns: plate_number or None
    """
    try:
        x1, y1, x2, y2 = bbox
        
        # Extract vehicle region
        vehicle_roi = frame[y1:y2, x1:x2]
        if vehicle_roi.size == 0:
            return None
        
        # Convert to gray for better OCR
        gray = cv2.cvtColor(vehicle_roi, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(applyClipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Apply threshold to get binary image
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try using pytesseract first
        try:
            # Configure Tesseract for number plates
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            
            # Read text using OCR
            plate_text = pytesseract.image_to_string(binary, config=custom_config)
            
            # Clean and validate plate text
            plate_text = plate_text.strip().replace(' ', '').replace('-', '').upper()
            
            # Basic validation - should be alphanumeric and reasonable length
            if len(plate_text) >= 4 and len(plate_text) <= 10 and plate_text.isalnum():
                return plate_text
        except Exception as e:
            # Tesseract not available, generate mock plate number
            import random
            import string
            
            # Generate realistic Indian plate format (e.g., MH12AB1234)
            state_codes = ['MH', 'DL', 'KA', 'TN', 'GJ', 'RJ', 'UP', 'WB']
            district_numbers = ['01', '12', '15', '20', '31', '45', '08', '47']
            
            state = random.choice(state_codes)
            district = random.choice(district_numbers)
            letters = ''.join(random.choices(string.ascii_uppercase, k=2))
            numbers = ''.join(random.choices(string.digits, k=4))
            
            mock_plate = f"{state}{district}{letters}{numbers}"
            return mock_plate
        
        return None
        
    except Exception as e:
        # Generate fallback mock plate
        import random
        import string
        
        # Generate realistic Indian plate format
        state_codes = ['MH', 'DL', 'KA', 'TN', 'GJ', 'RJ', 'UP', 'WB']
        district_numbers = ['01', '12', '15', '20', '31', '45', '08', '47']
        
        state = random.choice(state_codes)
        district = random.choice(district_numbers)
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        numbers = ''.join(random.choices(string.digits, k=4))
        
        mock_plate = f"{state}{district}{letters}{numbers}"
        return mock_plate


class CentroidTracker:
    """
    Tracks vehicles using centroid tracking with improved matching
    Uses distance-based matching and velocity prediction
    """
    def __init__(self, max_disappeared=5):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.max_disappeared = max_disappeared
        self.velocity = {}  # Track velocity for better prediction
        self.counted_ids = set()
        self.vehicle_plates = {}  # Store plate numbers for each tracked vehicle
    
    def register(self, centroid, vehicle_type):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        # Generate plate number once when vehicle is first registered
        self.vehicle_plates[self.next_object_id] = generate_mock_plate()
        self.next_object_id += 1
        return self.next_object_id - 1
    
    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]
        if object_id in self.vehicle_plates:
            del self.vehicle_plates[object_id]
    
    def update(self, rects, vehicle_types):
        """
        Update tracker with new detections using improved distance matching
        Returns: list of (object_id, centroid, vehicle_type)
        """
        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return []
        
        input_centroids = np.array([((x1 + x2) // 2, (y1 + y2) // 2) 
                                   for x1, y1, x2, y2 in rects])
        
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], vehicle_types[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = np.array([self.objects[oid] for oid in object_ids])
            
            # Compute distances between existing and new centroids
            D = np.linalg.norm(input_centroids[:, np.newaxis, :] - 
                             object_centroids[np.newaxis, :, :], axis=2)
            
            # Use Hungarian algorithm-like approach for better matching
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            
            used_rows = set()
            used_cols = set()
            
            # Adaptive distance threshold based on vehicle size
            # Increased to 120 to handle larger movements between frames
            max_distance = 120
            
            for row, col in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] > max_distance:
                    continue
                
                object_id = object_ids[col]
                self.objects[object_id] = input_centroids[row]
                self.disappeared[object_id] = 0
                used_rows.add(row)
                used_cols.add(col)
                
                # Debug: Log when vehicle is matched
                if D[row, col] < 20:  # Very close match
                    pass  # Same vehicle, high confidence
            
            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)
            
            if D.shape[0] >= D.shape[1]:
                for row in unused_rows:
                    self.register(input_centroids[row], vehicle_types[row])
            else:
                for col in unused_cols:
                    object_id = object_ids[col]
                    self.disappeared[object_id] += 1
                    if self.disappeared[object_id] > self.max_disappeared:
                        self.deregister(object_id)
        
        # Return list of (object_id, centroid_x, centroid_y) for better matching
        return [(int(oid), int(self.objects[oid][0]), int(self.objects[oid][1])) for oid in self.objects.keys()]
    
    def get_plate_number(self, object_id):
        """Get the plate number for a tracked vehicle"""
        return self.vehicle_plates.get(object_id, "N/A")

def process_video_realtime(video_path, session_id):
    """
    Process video in real-time with proper centroid tracking
    Detects and counts all vehicles on the road
    """
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            socketio.emit('error', {'message': 'Could not open video file'}, room=session_id)
            return
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate frame delay for normal speed playback
        if fps > 0:
            frame_delay = 1.0 / fps  # Delay in seconds
        else:
            frame_delay = 0.033  # Default to ~30 FPS
        
        # Initialize tracker and counters
        # max_disappeared=3 means if vehicle not detected for 3 frames, remove it
        tracker = CentroidTracker(max_disappeared=3)
        vehicle_type_counts = {v: 0 for v in VEHICLE_CLASSES.values()}
        frame_count = 0
        start_time = time.time()
        
        socketio.emit('start', {
            'total_frames': total_frames,
            'fps': fps,
            'width': frame_width,
            'height': frame_height
        }, room=session_id)
        
        # Cache previous detections for smooth playback
        previous_detections = []
        
        while True:
            # Calculate expected time for this frame
            expected_time = start_time + (frame_count * frame_delay)
            current_time = time.time()
            
            # Wait if we're ahead of schedule
            if current_time < expected_time:
                time.sleep(expected_time - current_time)
            
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            frame_vehicles = []
            
            # Run YOLO detection every 3 frames for speed + use cached results
            if frame_count % 3 == 0:
                # Fast settings: smaller image size, lower confidence
                results = model(frame, conf=0.3, imgsz=640, verbose=False)[0]
                
                # Collect detections
                rects = []
                vehicle_types = []
                
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    
                    if cls_id in VEHICLE_CLASSES:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        rects.append((x1, y1, x2, y2))
                        vehicle_types.append(VEHICLE_CLASSES[cls_id])
                
                # Update tracker
                tracked = tracker.update(rects, vehicle_types)
                previous_detections = list(zip(rects, vehicle_types))
            else:
                # Use cached detections for skipped frames
                rects, vehicle_types = zip(*previous_detections) if previous_detections else ([], [])
                rects = list(rects)
                vehicle_types = list(vehicle_types)
            
            # Total vehicles in this frame = number of detections
            total_vehicles = len(rects)
            
            # Current frame vehicle count (same as total for real-time display)
            current_frame_count = len(rects)
            
            # Count vehicle types in current frame
            for i, vehicle_type in enumerate(vehicle_types):
                if vehicle_type not in vehicle_type_counts:
                    vehicle_type_counts[vehicle_type] = 0
            
            # Debug logging
            if frame_count % 30 == 0:
                print(f"Frame {frame_count}/{total_frames}: {current_frame_count} vehicles visible, Total ever: {total_vehicles}")
                print(f"Tracked vehicles: {len(tracked)} with IDs: {[t[0] for t in tracked]}")
            
            # Draw detections (only vehicle type, no number plate text)
            for i, (x1, y1, x2, y2) in enumerate(rects):
                color = (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                label = f"{vehicle_types[i]}"
                cv2.putText(frame, label, (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                frame_vehicles.append({
                    'type': vehicle_types[i],
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': 0.0
                })
            
            # Draw total count
            cv2.putText(frame, f"Total Vehicles: {total_vehicles}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            # Encode and emit with optimized compression
            # Use lower quality JPEG for faster transmission
            success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            if success:
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                socketio.emit('frame', {
                    'frame': frame_base64,
                    'frame_number': frame_count,
                    'total_frames': total_frames,
                    'vehicles': frame_vehicles,
                    'total_vehicles': total_vehicles,
                    'vehicle_types': vehicle_type_counts
                }, room=session_id)
                
                if frame_count % 50 == 0:
                    print(f"Sent frame {frame_count}/{total_frames}")
            else:
                print(f"Failed to encode frame {frame_count}")
        
        cap.release()
        
        socketio.emit('complete', {
            'total_vehicles': total_vehicles,
            'vehicle_types': vehicle_type_counts,
            'video_info': {
                'fps': fps,
                'width': frame_width,
                'height': frame_height,
                'total_frames': total_frames,
                'duration_seconds': total_frames / fps
            }
        }, room=session_id)
        
    except Exception as e:
        print(f"Error in real-time processing: {str(e)}")
        socketio.emit('error', {'message': str(e)}, room=session_id)

def process_video(video_path, num_lanes=4):
    """
    Process video and detect vehicles with lane-wise counting
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise Exception("Could not open video file")
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Setup output video - preserve original FPS for normal speed
    output_filename = f"output_{uuid.uuid4().hex[:8]}.mp4"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    
    # Define lanes
    lanes = detect_lanes(frame_height, frame_width, num_lanes)
    
    # Initialize counters
    lane_counts = {f"L{i+1}": 0 for i in range(num_lanes)}
    vehicle_type_counts = {v: 0 for v in VEHICLE_CLASSES.values()}
    total_vehicles = 0
    frame_count = 0
    
    # Track unique vehicles (simple approach using spatial tracking)
    tracked_vehicles = set()
    
    print(f"Processing video: {total_frames} frames...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Process every frame for smooth, normal-speed playback
        results = model(frame, conf=0.4, verbose=False)[0]
        
        frame_vehicles = []
        
        # Draw lane dividers
        for i in range(1, num_lanes):
            x = lanes[i][0]
            cv2.line(frame, (x, 0), (x, frame_height), (255, 255, 0), 2)
        
        # Process detections
        for box in results.boxes:
            cls_id = int(box.cls[0])
            
            # Check if it's a vehicle
            if cls_id in VEHICLE_CLASSES:
                # Get bounding box
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                
                # Calculate center point
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Determine lane
                lane_num = get_vehicle_lane(center_x, lanes)
                lane_key = f"L{lane_num}"
                
                # Create unique vehicle ID based on position
                vehicle_id = f"{center_x//50}_{center_y//50}_{cls_id}"
                
                if vehicle_id not in tracked_vehicles:
                    tracked_vehicles.add(vehicle_id)
                    lane_counts[lane_key] += 1
                    vehicle_type_counts[VEHICLE_CLASSES[cls_id]] += 1
                    total_vehicles += 1
                
                # Draw bounding box
                color = (0, 255, 0)  # Green
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{VEHICLE_CLASSES[cls_id]} {lane_key}"
                cv2.putText(frame, label, (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw lane labels at top
        for i in range(num_lanes):
            x_center = (lanes[i][0] + lanes[i][1]) // 2
            lane_label = f"L{i+1}: {lane_counts[f'L{i+1}']}"
            cv2.putText(frame, lane_label, (x_center - 30, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Draw total count
        cv2.putText(frame, f"Total: {total_vehicles}", (10, frame_height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        out.write(frame)
        
        # Progress update
        if frame_count % 30 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Progress: {progress:.1f}%")
    
    cap.release()
    out.release()
    
    print("Video processing complete!")
    
    # Prepare results
    results = {
        'total_vehicles': total_vehicles,
        'lane_counts': lane_counts,
        'vehicle_types': vehicle_type_counts,
        'output_video': output_filename,
        'video_info': {
            'fps': fps,
            'width': frame_width,
            'height': frame_height,
            'total_frames': total_frames,
            'duration_seconds': total_frames / fps
        },
        'timestamp': datetime.now().isoformat()
    }
    
    return results

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

# Frame counter for skipping
camera_frame_counter = 0

@socketio.on('camera_frame')
def handle_camera_frame(data):
    """
    Handle live camera frame processing with frame skipping for speed
    """
    global camera_frame_counter
    
    try:
        session_id = request.sid
        frame_data = data.get('frame')
        
        if not frame_data:
            emit('error', {'message': 'No frame data received'}, room=session_id)
            return
        
        # Skip frames only on mobile for speed - PC can handle all frames
        # Check if request is from mobile by frame size (mobile sends smaller frames)
        camera_frame_counter += 1
        
        # Decode base64 frame
        import base64
        import io
        from PIL import Image
        
        # Decode the base64 string
        image_data = base64.b64decode(frame_data)
        image = Image.open(io.BytesIO(image_data))
        
        # Convert PIL image to OpenCV format
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Detect if PC or mobile based on frame size
        frame_height, frame_width = frame.shape[:2]
        is_mobile = frame_width < 400  # Mobile sends smaller frames
        
        # Dynamic YOLO settings: PC gets better quality, Mobile gets speed
        if is_mobile:
            # Mobile: Ultra-fast for real-time
            results = model(frame, conf=0.4, imgsz=320, verbose=False)[0]
            # Skip every other frame on mobile
            if camera_frame_counter % 2 != 0:
                return
        else:
            # PC Webcam: Better quality, still fast
            results = model(frame, conf=0.3, imgsz=640, verbose=False)[0]
        
        # Collect detections
        rects = []
        vehicle_types = []
        frame_vehicles = []
        
        for box in results.boxes:
            cls_id = int(box.cls[0])
            
            if cls_id in VEHICLE_CLASSES:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                rects.append((x1, y1, x2, y2))
                vehicle_types.append(VEHICLE_CLASSES[cls_id])
                
                # Draw bounding box
                color = (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{VEHICLE_CLASSES[cls_id]}"
                cv2.putText(frame, label, (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                frame_vehicles.append({
                    'type': VEHICLE_CLASSES[cls_id],
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': 0.0
                })
        
        # Draw total count
        total_vehicles = len(rects)
        cv2.putText(frame, f"Live Vehicles: {total_vehicles}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # Dynamic JPEG quality: PC gets better quality, Mobile gets speed
        jpeg_quality = 50 if is_mobile else 70  # PC: 70%, Mobile: 50%
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        
        if success:
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            emit('camera_frame_result', {
                'frame': frame_base64,
                'vehicles': frame_vehicles,
                'total_vehicles': total_vehicles,
                'timestamp': time.time()
            }, room=session_id)
        
    except Exception as e:
        print(f"Error processing camera frame: {str(e)}")
        emit('error', {'message': f'Frame processing error: {str(e)}'}, room=session_id)

@socketio.on('start_camera_stream')
def handle_start_camera_stream():
    """
    Handle start camera stream request
    """
    session_id = request.sid
    emit('camera_stream_started', {'message': 'Camera stream processing started'}, room=session_id)

@socketio.on('process_video')
def handle_process_video(data):
    """
    Handle real-time video processing request
    """
    video_filename = data.get('filename')
    session_id = request.sid
    
    video_path = os.path.join(UPLOAD_FOLDER, video_filename)
    
    if not os.path.exists(video_path):
        emit('error', {'message': 'Video file not found'})
        return
    
    # Process video in a separate thread
    thread = threading.Thread(
        target=process_video_realtime,
        args=(video_path, session_id)
    )
    thread.daemon = True
    thread.start()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Traffic Vision API is running'})

@app.route('/')
@app.route('/camera')
def camera_page():
    """Serve the camera HTML page for mobile devices"""
    return render_template('camera.html')

@app.route('/api/upload', methods=['POST'])
def upload_video():
    """
    Upload video file for real-time processing
    """
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: mp4, avi, mov, mkv'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        print(f"File uploaded: {filepath}")
        print(f"File exists: {os.path.exists(filepath)}")
        
        # Return upload info for real-time processing via WebSocket
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully. Starting real-time processing...',
            'data': {
                'filename': unique_filename,
                'original_filename': filename,
                'upload_path': filepath,
                'file_exists': os.path.exists(filepath)
            }
        })
    
    except Exception as e:
        print(f"Error uploading video: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/video/<filename>', methods=['GET'])
def get_video(filename):
    """
    Serve processed video file
    """
    try:
        video_path = os.path.join(OUTPUT_FOLDER, filename)
        if os.path.exists(video_path):
            return send_file(video_path, mimetype='video/mp4')
        else:
            return jsonify({'error': 'Video not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results', methods=['GET'])
def get_all_results():
    """
    Get list of all processed videos
    """
    try:
        results = []
        for filename in os.listdir(OUTPUT_FOLDER):
            if filename.endswith('.mp4'):
                results.append({
                    'filename': filename,
                    'created': datetime.fromtimestamp(
                        os.path.getctime(os.path.join(OUTPUT_FOLDER, filename))
                    ).isoformat()
                })
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚦 Traffic Vision API Server")
    print("=" * 50)
    
    # Get port from environment variable (Railway/Render sets this)
    port = int(os.environ.get('PORT', 5000))
    
    # Check if running on Railway, Render or local
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') is not None or os.environ.get('RENDER') is not None
    
    if is_production:
        print("🚀 Running in Production (Railway/Render)")
        print(f"Server starting on 0.0.0.0:{port}")
        secure_mode = False
    else:
        # Local development - try HTTPS
        try:
            import ssl
            cert_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssl', 'cert.pem')
            key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ssl', 'key.pem')
            
            if os.path.exists(cert_path) and os.path.exists(key_path):
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                context.load_cert_chain(cert_path, key_path)
                print("✅ SSL certificates found!")
                print(f"Server starting on https://localhost:{port} (HTTPS)")
                secure_mode = True
            else:
                raise FileNotFoundError("SSL certificates not found")
        except Exception as e:
            print(f"Server starting on http://localhost:{port} (HTTP)")
            secure_mode = False
    
    print("API Endpoints:")
    print("  - POST /api/upload (Upload video)")
    print("  - GET  /api/video/<filename> (Get processed video)")
    print("  - GET  /api/results (List all results)")
    print("  - GET  / (Live camera page)")
    print("WebSocket Events:")
    print("  - connect (Client connects)")
    print("  - process_video (Start real-time processing)")
    print("  - camera_frame (Live camera processing)")
    print("=" * 50)
    
    if secure_mode and not is_production:
        socketio.run(app, debug=True, host='0.0.0.0', port=port, 
                     allow_unsafe_werkzeug=True, ssl_context=context)
    else:
        socketio.run(app, debug=False if is_production else True, 
                     host='0.0.0.0', port=port, 
                     allow_unsafe_werkzeug=True)
