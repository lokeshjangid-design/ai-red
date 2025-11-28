import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import io from 'socket.io-client';
import { 
  Upload, 
  Video, 
  BarChart3, 
  Car, 
  Truck, 
  Bike,
  Bus,
  Activity,
  CheckCircle,
  AlertCircle,
  Loader,
  Play,
  Pause,
  Camera,
  CameraOff
} from 'lucide-react';
import './App.css';

const API_URL = window.location.protocol === 'https:' 
  ? 'https://localhost:5000/api' 
  : 'http://localhost:5000/api';
const SOCKET_URL = window.location.protocol === 'https:' 
  ? 'https://localhost:5000' 
  : 'http://localhost:5000';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [liveFrame, setLiveFrame] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [uploadedFilename, setUploadedFilename] = useState(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [isMobile, setIsMobile] = useState(false);
  const [localIP, setLocalIP] = useState('192.168.1.11');
  const socketRef = useRef(null);
  const canvasRef = useRef(null);
  const videoRef = useRef(null);
  const frameCountRef = useRef(0);
  const lastFrameTimeRef = useRef(Date.now());

  // Detect mobile device
  useEffect(() => {
    const userAgent = navigator.userAgent || navigator.vendor || window.opera;
    const mobileCheck = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
    setIsMobile(mobileCheck);
    
    // Get current URL to show IP if accessing via mobile
    const currentHost = window.location.hostname;
    if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
      setLocalIP(currentHost);
    }
  }, []);

  // Initialize WebSocket connection
  useEffect(() => {
    socketRef.current = io(SOCKET_URL);

    socketRef.current.on('connected', (data) => {
      console.log('Connected to server:', data);
    });

    socketRef.current.on('frame', (data) => {
      // Throttle frame updates for smoother playback
      const now = Date.now();
      const timeSinceLastFrame = now - lastFrameTimeRef.current;
      
      // Update UI every 50ms (20 FPS) to prevent lag
      if (timeSinceLastFrame > 50) {
        setLiveFrame(`data:image/jpeg;base64,${data.frame}`);
        setLiveStats({
          frameNumber: data.frame_number,
          totalFrames: data.total_frames,
          totalVehicles: data.total_vehicles,
          vehicles: data.vehicles,
          vehicleTypes: data.vehicle_types
        });
        lastFrameTimeRef.current = now;
      }
    });

    socketRef.current.on('complete', (data) => {
      setResults(data);
      setProcessing(false);
    });

    socketRef.current.on('error', (data) => {
      setError(data.message);
      setProcessing(false);
    });

    socketRef.current.on('camera_frame_result', (data) => {
      // Handle camera frame results
      const now = Date.now();
      const timeSinceLastFrame = now - lastFrameTimeRef.current;
      
      // Update UI every 100ms for smooth camera feed
      if (timeSinceLastFrame > 100) {
        setLiveFrame(`data:image/jpeg;base64,${data.frame}`);
        setLiveStats({
          frameNumber: frameCountRef.current++,
          totalFrames: 'Live',
          totalVehicles: data.total_vehicles,
          vehicles: data.vehicles,
          vehicleTypes: {},
          timestamp: data.timestamp
        });
        lastFrameTimeRef.current = now;
      }
    });

    socketRef.current.on('camera_stream_started', (data) => {
      console.log('Camera stream started:', data);
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
      setResults(null);
      setVideoUrl(null);
      setLiveFrame(null);
      setLiveStats(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a video file first');
      return;
    }

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('video', selectedFile);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          console.log(`Upload Progress: ${percentCompleted}%`);
        },
      });

      if (response.data.success) {
        const uploadedFilename = response.data.data.filename;
        console.log('Video uploaded:', uploadedFilename);
        console.log('File exists on server:', response.data.data.file_exists);
        setUploadedFilename(uploadedFilename);
        setUploading(false);
        // Start real-time processing
        startRealTimeProcessing(uploadedFilename);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to process video');
      console.error('Upload error:', err);
      setUploading(false);
    }
  };

  const startRealTimeProcessing = (filename) => {
    setProcessing(true);
    setLiveFrame(null);
    setLiveStats(null);
    
    if (socketRef.current) {
      socketRef.current.emit('process_video', {
        filename: filename
      });
    }
  };

  const startCamera = async () => {
    try {
      setError(null);
      
      // Check if mediaDevices is supported
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setError('Camera API not supported in this browser. Please use Chrome, Firefox, or Safari.');
        return;
      }

      // Request camera with proper constraints and user gesture
      console.log('Requesting camera access...');
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          facingMode: 'environment', // Use back camera on mobile
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false 
      });
      
      console.log('Camera access granted!');
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setCameraStream(stream);
        setCameraActive(true);
        
        // Wait for video to be ready
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play();
          // Start live camera processing
          startCameraProcessing();
        };
      }
    } catch (err) {
      console.error('Camera error details:', err);
      
      // Handle specific permission errors
      if (err.name === 'NotAllowedError') {
        setError('📱 Camera permission denied. Please:\n1. Click the camera icon 📷 in your address bar\n2. Select "Allow"\n3. Refresh the page and try again');
      } else if (err.name === 'NotFoundError') {
        setError('No camera found. Please ensure your device has a camera.');
      } else if (err.name === 'NotReadableError') {
        setError('Camera is already in use by another application.');
      } else if (err.name === 'OverconstrainedError') {
        setError('Camera constraints not supported. Trying with default settings...');
        // Retry with basic constraints
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ 
            video: true,
            audio: false 
          });
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            setCameraStream(stream);
            setCameraActive(true);
            startCameraProcessing();
          }
        } catch (retryErr) {
          setError('Camera access failed. Please check your camera settings.');
        }
      } else {
        setError(`Camera access failed: ${err.message || 'Unknown error'}`);
      }
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
      setCameraActive(false);
      setProcessing(false);
      setLiveFrame(null);
      setLiveStats(null);
    }
  };

  const startCameraProcessing = () => {
    setProcessing(true);
    
    if (socketRef.current) {
      socketRef.current.emit('start_camera_stream');
    }
  };

  const captureFrame = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Convert to base64 and send to server
      const frameData = canvas.toDataURL('image/jpeg', 0.8);
      
      if (socketRef.current) {
        socketRef.current.emit('camera_frame', {
          frame: frameData.split(',')[1] // Remove data:image/jpeg;base64, prefix
        });
      }
    }
  };

  // Auto-capture frames when camera is active
  useEffect(() => {
    let interval;
    if (cameraActive && processing) {
      interval = setInterval(captureFrame, 100); // Capture every 100ms
    }
    return () => clearInterval(interval);
  }, [cameraActive, processing]);

  const getVehicleIcon = (type) => {
    switch(type) {
      case 'car': return <Car size={20} />;
      case 'truck': return <Truck size={20} />;
      case 'motorcycle': return <Bike size={20} />;
      case 'bus': return <Bus size={20} />;
      default: return <Car size={20} />;
    }
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <Activity size={32} />
            <h1>Traffic Vision System</h1>
          </div>
          <p className="subtitle">AI-Powered 360° Traffic Analysis Dashboard</p>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Upload Section */}
        <div className="upload-section">
          <div className="card">
            <div className="card-header">
              <Upload size={24} />
              <h2>Upload Traffic Video</h2>
            </div>
            
            <div className="upload-area">
              <input
                type="file"
                id="video-upload"
                accept="video/mp4,video/avi,video/mov,video/mkv"
                onChange={handleFileSelect}
                className="file-input"
              />
              <label htmlFor="video-upload" className="file-label">
                <Video size={48} />
                <span className="upload-text">
                  {selectedFile ? selectedFile.name : 'Click to select video'}
                </span>
                <span className="upload-hint">
                  Supported formats: MP4, AVI, MOV, MKV
                </span>
              </label>
            </div>

            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading || processing}
              className="upload-button"
            >
              {uploading ? (
                <>
                  <Loader className="spinner" size={20} />
                  Uploading...
                </>
              ) : processing ? (
                <>
                  <Loader className="spinner" size={20} />
                  Processing...
                </>
              ) : (
                <>
                  <Upload size={20} />
                  Analyze Video
                </>
              )}
            </button>

            {error && (
              <div className="alert alert-error">
                <AlertCircle size={20} />
                <span>{error}</span>
              </div>
            )}
          </div>
        </div>

        {/* Live Camera Section */}
        <div className="camera-section">
          <div className="card">
            <div className="card-header">
              <Camera size={24} />
              <h2>Live Camera Traffic Analysis</h2>
            </div>
            
            {/* Mobile Instructions */}
            {isMobile ? (
              <div className="mobile-welcome">
                <h3>📱 Mobile Detected!</h3>
                <p>You're accessing from: {localIP}</p>
                <p>Ready for live traffic monitoring 🚦</p>
              </div>
            ) : (
              <div className="pc-instructions">
                <h3>💻 PC Instructions</h3>
                <p><strong>To test on mobile:</strong></p>
                <ol>
                  <li>Open browser on your phone</li>
                  <li>Go to: <strong>http://{localIP}:3000</strong></li>
                  <li>Click "Start Camera" button</li>
                  <li>Allow camera permissions</li>
                  <li>Point at traffic for live analysis!</li>
                </ol>
                <div className="qr-placeholder">
                  <p>📱 Scan this code on mobile:</p>
                  <div className="qr-code">
                    <span>http://{localIP}:3000</span>
                  </div>
                </div>
              </div>
            )}
            
            <div className="camera-controls">
              {!cameraActive ? (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    startCamera();
                  }}
                  disabled={processing}
                  className="camera-button start"
                >
                  <Camera size={20} />
                  {isMobile ? '📱 Start Phone Camera' : 'Start Camera'}
                </button>
              ) : (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    stopCamera();
                  }}
                  className="camera-button stop"
                >
                  <CameraOff size={20} />
                  Stop Camera
                </button>
              )}
            </div>

            {/* Hidden video element for camera stream */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              style={{ display: 'none' }}
            />
            
            {/* Hidden canvas for frame capture */}
            <canvas
              ref={canvasRef}
              style={{ display: 'none' }}
            />

            <div className="camera-info">
              <p>📱 {isMobile ? 'iPhone & Android' : 'Works with iPhone & Android'} cameras</p>
              <p>🚦 Point camera at traffic for real-time analysis</p>
              <p>⚡ Like webcamtoy.com - just allow camera access</p>
              {isMobile && (
                <p>🔗 Your IP: {localIP}:3000</p>
              )}
            </div>
          </div>
        </div>

        {/* Live Stream Section */}
        {processing && liveFrame && (
          <div className="live-stream-section">
            <div className="card">
              <div className="card-header">
                <Video size={24} />
                <h2>Live Detection Stream</h2>
              </div>
              
              <div className="live-container">
                <div className="live-video">
                  <img 
                    src={liveFrame} 
                    alt="Live detection"
                    className="live-frame"
                  />
                </div>
                
                <div className="live-stats-panel">
                  <div className="live-stat">
                    <span className="live-label">Frame</span>
                    <span className="live-value">
                      {liveStats?.frameNumber}/{liveStats?.totalFrames}
                    </span>
                  </div>
                  
                  <div className="live-stat">
                    <span className="live-label">Total Vehicles</span>
                    <span className="live-value">{liveStats?.totalVehicles}</span>
                  </div>
                  
                  <div className="live-vehicles">
                    <h4>Current Frame Vehicles:</h4>
                    {liveStats?.vehicles?.length > 0 ? (
                      liveStats.vehicles.map((vehicle, idx) => (
                        <div key={idx} className="vehicle-badge">
                          {getVehicleIcon(vehicle.type)}
                          <span>{vehicle.type}</span>
                        </div>
                      ))
                    ) : (
                      <span className="no-vehicles">No vehicles detected</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Section */}
        {results && (
          <div className="results-section">
            {/* Success Message */}
            <div className="alert alert-success">
              <CheckCircle size={20} />
              <span>Video processed successfully!</span>
            </div>

            {/* Statistics Cards */}
            <div className="stats-grid">
              <div className="stat-card total">
                <div className="stat-icon">
                  <BarChart3 size={32} />
                </div>
                <div className="stat-content">
                  <h3>Total Vehicles</h3>
                  <p className="stat-value">{results.total_vehicles}</p>
                </div>
              </div>

            </div>

            {/* Vehicle Types */}
            <div className="card">
              <div className="card-header">
                <Car size={24} />
                <h2>Vehicle Classification</h2>
              </div>
              <div className="vehicle-types">
                {Object.entries(results.vehicle_types).map(([type, count]) => (
                  count > 0 && (
                    <div key={type} className="vehicle-type-item">
                      <div className="vehicle-type-icon">
                        {getVehicleIcon(type)}
                      </div>
                      <div className="vehicle-type-info">
                        <span className="vehicle-type-name">
                          {type.charAt(0).toUpperCase() + type.slice(1)}
                        </span>
                        <span className="vehicle-type-count">{count}</span>
                      </div>
                    </div>
                  )
                ))}
              </div>
            </div>

            {/* Video Info */}
            <div className="card">
              <div className="card-header">
                <Video size={24} />
                <h2>Video Information</h2>
              </div>
              <div className="video-info">
                <div className="info-item">
                  <span className="info-label">Resolution:</span>
                  <span className="info-value">
                    {results.video_info.width} × {results.video_info.height}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">FPS:</span>
                  <span className="info-value">{results.video_info.fps}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Duration:</span>
                  <span className="info-value">
                    {results.video_info.duration_seconds.toFixed(2)}s
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Total Frames:</span>
                  <span className="info-value">{results.video_info.total_frames}</span>
                </div>
              </div>
            </div>

            {/* Processed Video */}
            {videoUrl && (
              <div className="card">
                <div className="card-header">
                  <Video size={24} />
                  <h2>Processed Video with Detection</h2>
                </div>
                <div className="video-container">
                  <video controls className="result-video">
                    <source src={videoUrl} type="video/mp4" />
                    Your browser does not support the video tag.
                  </video>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Feature Description */}
        {!results && !uploading && (
          <div className="features-section">
            <div className="card">
              <div className="card-header">
                <Activity size={24} />
                <h2>System Features</h2>
              </div>
              <div className="features-grid">
                <div className="feature-item">
                  <Car size={32} />
                  <h3>Multi-Vehicle Detection</h3>
                  <p>Detects cars, bikes, trucks, buses, and more</p>
                </div>
                <div className="feature-item">
                  <BarChart3 size={32} />
                  <h3>Lane-wise Analysis</h3>
                  <p>Automatic lane detection and vehicle counting</p>
                </div>
                <div className="feature-item">
                  <Video size={32} />
                  <h3>360° Camera Support</h3>
                  <p>Works with wide-angle traffic camera feeds</p>
                </div>
                <div className="feature-item">
                  <Activity size={32} />
                  <h3>Real-time Processing</h3>
                  <p>Fast AI-powered video analysis</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>Traffic Vision System v1.0 | AI-Powered Traffic Management</p>
      </footer>
    </div>
  );
}

export default App;
