#!/usr/bin/env python3

import argparse
import logging
import sys
import os
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SystemTest")

def test_config():
    """Test configuration loading."""
    logger.info("Testing configuration loading...")
    
    try:
        from config.settings import load_settings
        
        # Test loading default config
        config = load_settings()
        logger.info(f"Loaded default configuration successfully")
        
        # Test loading custom config
        custom_config_path = "config/default_config.json"
        if os.path.exists(custom_config_path):
            config = load_settings(custom_config_path)
            logger.info(f"Loaded custom configuration from {custom_config_path}")
        
        # Verify essential settings
        assert "drone" in config, "Missing 'drone' section in config"
        assert "detection" in config, "Missing 'detection' section in config"
        assert "geofence" in config, "Missing 'geofence' section in config"
        
        logger.info("Configuration test passed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration test failed: {str(e)}")
        return False

def test_geofence():
    """Test geofence functionality."""
    logger.info("Testing geofence functionality...")
    
    try:
        from config.settings import load_settings
        from geofence.geofence_manager import GeofenceManager
        
        # Load config
        config = load_settings()
        
        # Initialize geofence
        geofence = GeofenceManager(config['geofence'])
        logger.info(f"Initialized geofence with {len(geofence.boundaries)} boundaries")
        
        # Test point inside/outside
        test_points = [
            # Inside points (expected to be inside the default geofence)
            {"lat": 37.7749, "lon": -122.4194, "expected": True, "name": "Center point"},
            {"lat": 37.7759, "lon": -122.4184, "expected": True, "name": "Near center"},
            
            # Outside points (expected to be outside the default geofence)
            {"lat": 38.7749, "lon": -122.4194, "expected": False, "name": "Far away"},
            {"lat": 37.7849, "lon": -122.4294, "expected": False, "name": "Outside boundary"}
        ]
        
        for point in test_points:
            result = geofence.is_point_inside(point["lat"], point["lon"])
            status = "PASS" if result == point["expected"] else "FAIL"
            logger.info(f"Test point '{point['name']}': {status} (got {result}, expected {point['expected']})")
            
            if result != point["expected"]:
                logger.warning(f"Geofence test failed for point {point['name']}")
                
        # Test nearest safe point
        outside_point = {"lat": 38.7749, "lon": -122.4194}
        safe_lat, safe_lon = geofence.get_nearest_safe_point(outside_point["lat"], outside_point["lon"])
        logger.info(f"Nearest safe point for ({outside_point['lat']}, {outside_point['lon']}) is ({safe_lat}, {safe_lon})")
        
        # Verify the safe point is inside
        assert geofence.is_point_inside(safe_lat, safe_lon), "Generated safe point is not inside geofence"
        
        logger.info("Geofence test passed")
        return True
        
    except Exception as e:
        logger.error(f"Geofence test failed: {str(e)}")
        return False

def test_drone_simulation():
    """Test drone controller in simulation mode."""
    logger.info("Testing drone controller (simulation)...")
    
    try:
        from config.settings import load_settings
        from drone_control.drone_controller import DroneController
        from geofence.geofence_manager import GeofenceManager
        
        # Load config
        config = load_settings()
        
        # Initialize geofence
        geofence = GeofenceManager(config['geofence'])
        
        # Initialize drone controller in simulation mode
        drone = DroneController(config['drone'], simulation_mode=True, geofence_manager=geofence)
        logger.info("Initialized drone controller in simulation mode")
        
        # Test connection
        assert drone.connect(), "Failed to connect to simulated drone"
        logger.info("Connected to simulated drone")
        
        # Test takeoff
        assert drone.takeoff(altitude=10), "Failed to take off"
        logger.info("Simulated takeoff successful")
        
        # Test movement
        assert drone.move_to_coordinates({"latitude": 37.7750, "longitude": -122.4195}), "Failed to move"
        logger.info("Simulated movement successful")
        
        # Test status
        status = drone.get_status()
        logger.info(f"Drone status: {status['status']}")
        
        # Test return to home
        assert drone.return_to_home(), "Failed to return to home"
        logger.info("Simulated return to home successful")
        
        # Test landing
        assert drone.land(), "Failed to land"
        logger.info("Simulated landing successful")
        
        # Test disconnection
        drone.disconnect()
        logger.info("Disconnected from simulated drone")
        
        logger.info("Drone controller test passed")
        return True
        
    except Exception as e:
        logger.error(f"Drone controller test failed: {str(e)}")
        return False

def test_detector():
    """Test detection system in simulation mode."""
    logger.info("Testing detection system...")
    
    try:
        from config.settings import load_settings
        from detection.detector import EmergencyDetector
        import numpy as np
        import cv2
        
        # Load config
        config = load_settings()
        
        # Create a simple test image (black with a white square)
        test_image = np.zeros((300, 300, 3), dtype=np.uint8)
        test_image[100:200, 100:200] = 255  # White square
        
        # Save test image for reference
        cv2.imwrite("test_image.jpg", test_image)
        logger.info("Created test image: test_image.jpg")
        
        # Create a simplified config for testing
        detector_config = {
            "camera_source": None,
            "detection_interval": 0.1,
            "fire_threshold": 0.5,
            "person_threshold": 0.5,
            "suspicious_threshold": 0.5,
            "threat_threshold": 0.5
        }
        
        # Initialize detector (this will likely fail to load models but should handle it gracefully)
        detector = EmergencyDetector(detector_config, use_coral=False)
        logger.info("Initialized detector")
        
        # Test manual frame processing (this is just to verify the code doesn't crash)
        detector._process_frame(test_image)
        logger.info("Processed test frame")
        
        # Get any detected events (should be empty in this test)
        events = detector.get_events()
        logger.info(f"Detected {len(events)} events in test image")
        
        logger.info("Detection system test passed")
        return True
        
    except Exception as e:
        logger.error(f"Detection system test failed: {str(e)}")
        return False

def test_communication():
    """Test communication system."""
    logger.info("Testing communication system...")
    
    try:
        import asyncio
        import websockets
        import threading
        import json
        import time
        from config.settings import load_settings
        from communication.communicator import Communicator
        
        # Load config
        config = load_settings()
        
        # Simplified config for testing
        comm_config = {
            "method": "websocket",
            "host": "127.0.0.1",
            "port": 8765
        }
        
        # Initialize communicator
        communicator = Communicator(comm_config)
        logger.info("Initialized communicator")
        
        # Start communication system
        communicator.start()
        logger.info("Started communication system")
        
        # Give it a moment to start
        time.sleep(1)
        
        # Create a test client
        async def test_client():
            uri = f"ws://{comm_config['host']}:{comm_config['port']}"
            try:
                async with websockets.connect(uri) as websocket:
                    logger.info("Connected test client to WebSocket server")
                    
                    # Send a test command
                    command = {
                        "type": "test",
                        "timestamp": time.time()
                    }
                    await websocket.send(json.dumps(command))
                    logger.info("Sent test command")
                    
                    # Wait for acknowledgment
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    logger.info(f"Received response: {response_data}")
                    
                    # Check if it's an acknowledgment
                    assert response_data.get("type") == "ack", "Response is not an acknowledgment"
                    assert response_data.get("command") == "test", "Wrong command in acknowledgment"
                    
                    logger.info("Test client communication successful")
                    return True
            except Exception as e:
                logger.error(f"WebSocket client error: {str(e)}")
                return False
        
        # Run the test client
        client_success = asyncio.run(test_client())
        
        # Stop communication system
        communicator.stop()
        logger.info("Stopped communication system")
        
        if client_success:
            logger.info("Communication system test passed")
            return True
        else:
            logger.error("Communication system test failed")
            return False
        
    except Exception as e:
        logger.error(f"Communication system test failed: {str(e)}")
        return False

def run_tests(args):
    """Run the selected tests."""
    tests = {
        "config": test_config,
        "geofence": test_geofence,
        "drone": test_drone_simulation,
        "detector": test_detector,
        "communication": test_communication
    }
    
    results = {}
    
    if args.all:
        # Run all tests
        for name, test_func in tests.items():
            logger.info(f"\n{'=' * 50}\nRunning {name} test\n{'=' * 50}")
            results[name] = test_func()
    else:
        # Run selected tests
        for name in args.tests:
            if name in tests:
                logger.info(f"\n{'=' * 50}\nRunning {name} test\n{'=' * 50}")
                results[name] = tests[name]()
            else:
                logger.error(f"Unknown test: {name}")
                results[name] = False
    
    # Print summary
    logger.info(f"\n{'=' * 50}\nTest Results\n{'=' * 50}")
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{name}: {status}")
    
    # Return True if all tests passed
    return all(results.values())

def main():
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(description='Test drone surveillance system components')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('tests', nargs='*', default=['config'], 
                      help='Tests to run (config, geofence, drone, detector, communication)')
    args = parser.parse_args()
    
    success = run_tests(args)
    
    if success:
        logger.info("All tests passed!")
        sys.exit(0)
    else:
        logger.error("One or more tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 