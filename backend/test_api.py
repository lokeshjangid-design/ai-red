"""
Test script for Traffic Vision API
Run this to verify backend is working correctly
"""

import requests
import os

API_URL = "http://localhost:5000/api"

def test_health_check():
    """Test if API is running"""
    print("Testing health check...")
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed:", response.json())
            return True
        else:
            print("❌ Health check failed:", response.status_code)
            return False
    except Exception as e:
        print("❌ Error:", str(e))
        return False

def test_video_upload(video_path, num_lanes=4):
    """Test video upload and processing"""
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return False
    
    print(f"\nTesting video upload: {video_path}")
    print(f"Lanes: {num_lanes}")
    
    try:
        with open(video_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {'lanes': num_lanes}
            
            print("Uploading... (this may take a while)")
            response = requests.post(
                f"{API_URL}/upload",
                files=files,
                data=data,
                timeout=300  # 5 minutes timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print("✅ Video processed successfully!")
                    print("\nResults:")
                    print(f"  Total Vehicles: {result['data']['total_vehicles']}")
                    print(f"  Lane Counts: {result['data']['lane_counts']}")
                    print(f"  Vehicle Types: {result['data']['vehicle_types']}")
                    print(f"  Output Video: {result['data']['output_video']}")
                    return True
                else:
                    print("❌ Processing failed:", result)
                    return False
            else:
                print("❌ Upload failed:", response.status_code)
                print("Response:", response.text)
                return False
                
    except Exception as e:
        print("❌ Error:", str(e))
        return False

def test_get_results():
    """Test getting list of results"""
    print("\nTesting get results...")
    try:
        response = requests.get(f"{API_URL}/results")
        if response.status_code == 200:
            results = response.json()
            print(f"✅ Found {len(results.get('results', []))} processed videos")
            return True
        else:
            print("❌ Get results failed:", response.status_code)
            return False
    except Exception as e:
        print("❌ Error:", str(e))
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Traffic Vision API Test Suite")
    print("=" * 50)
    
    # Test 1: Health Check
    if not test_health_check():
        print("\n⚠️  Backend server is not running!")
        print("Please start the server first: python server.py")
        exit(1)
    
    # Test 2: Get Results
    test_get_results()
    
    # Test 3: Video Upload (optional)
    print("\n" + "=" * 50)
    print("Video Upload Test (Optional)")
    print("=" * 50)
    video_path = input("\nEnter path to test video (or press Enter to skip): ").strip()
    
    if video_path and os.path.exists(video_path):
        lanes = input("Number of lanes (default 4): ").strip() or "4"
        test_video_upload(video_path, int(lanes))
    else:
        print("Skipping video upload test")
    
    print("\n" + "=" * 50)
    print("Test suite completed!")
    print("=" * 50)
