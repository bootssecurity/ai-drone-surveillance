#!/usr/bin/env python3

import argparse
import logging
import time
import sys
import os
from threading import Thread

# Import our custom modules
from drone_control.drone_controller import DroneController
from detection.detector import EmergencyDetector
from geofence.geofence_manager import GeofenceManager
from communication.communicator import Communicator
from config.settings import load_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("drone_system.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DroneSystem")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AI-powered Drone Surveillance System')
    parser.add_argument('--config', type=str, default='config/default_config.json',
                      help='Path to configuration file')
    parser.add_argument('--simulation', action='store_true',
                      help='Run in simulation mode instead of connecting to a real drone')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    return parser.parse_args()

class DroneSystem:
    """Main class that coordinates all the components of the drone system."""
    
    def __init__(self, config_path, simulation_mode=False):
        """Initialize the drone system."""
        logger.info("Initializing Drone System")
        
        # Load configuration
        self.config = load_settings(config_path)
        self.simulation_mode = simulation_mode
        
        # Initialize components
        self.geofence = GeofenceManager(self.config['geofence'])
        self.detector = EmergencyDetector(self.config['detection'], use_coral=True)
        self.communicator = Communicator(self.config['communication'])
        
        # Initialize drone controller last (after all other components are ready)
        self.drone = DroneController(
            self.config['drone'], 
            simulation_mode=simulation_mode,
            geofence_manager=self.geofence
        )
        
        self.running = False
        logger.info("Drone System initialized")
    
    def start(self):
        """Start the drone system."""
        logger.info("Starting Drone System")
        self.running = True
        
        # Start detection system
        self.detector_thread = Thread(target=self.detector.start)
        self.detector_thread.daemon = True
        self.detector_thread.start()
        
        # Start communication system
        self.communicator.start()
        
        # Connect to the drone
        if not self.drone.connect():
            logger.error("Failed to connect to drone. Exiting.")
            self.shutdown()
            return False
        
        # Start the main control loop
        self.control_thread = Thread(target=self.control_loop)
        self.control_thread.daemon = True
        self.control_thread.start()
        
        logger.info("Drone System started")
        return True
    
    def control_loop(self):
        """Main control loop for the drone system."""
        logger.info("Starting control loop")
        
        try:
            while self.running:
                # Check if detector has found anything
                events = self.detector.get_events()
                if events:
                    for event in events:
                        logger.info(f"Emergency event detected: {event['type']} at {event['location']}")
                        self.communicator.send_alert(event)
                        self.handle_emergency(event)
                
                # Check for incoming commands
                commands = self.communicator.get_commands()
                for cmd in commands:
                    self.handle_command(cmd)
                
                # Get drone status and send update
                status = self.drone.get_status()
                self.communicator.send_status(status)
                
                time.sleep(0.1)  # Small sleep to prevent CPU hogging
                
        except Exception as e:
            logger.error(f"Error in control loop: {str(e)}")
            self.shutdown()
    
    def handle_emergency(self, event):
        """Handle detected emergency events."""
        event_type = event['type']
        location = event.get('location')
        
        if event_type == 'fire':
            # Move closer to inspect and track the fire
            self.drone.move_to_coordinates(location, altitude=self.config['emergency']['fire_inspection_altitude'])
        elif event_type == 'break_in':
            # Track the intruder
            self.drone.move_to_coordinates(location, altitude=self.config['emergency']['tracking_altitude'])
        elif event_type == 'suspicious':
            # Move to investigate
            self.drone.move_to_coordinates(location, altitude=self.config['emergency']['investigation_altitude'])
        elif event_type == 'threat':
            # Keep distance but observe
            self.drone.move_to_coordinates(location, altitude=self.config['emergency']['threat_observation_altitude'])
    
    def handle_command(self, command):
        """Handle commands received from the ground station."""
        cmd_type = command['type']
        
        if cmd_type == 'move':
            self.drone.move_to_coordinates(command['coordinates'], altitude=command.get('altitude'))
        elif cmd_type == 'return':
            self.drone.return_to_home()
        elif cmd_type == 'land':
            self.drone.land()
        elif cmd_type == 'takeoff':
            self.drone.takeoff(altitude=command.get('altitude', self.config['drone']['default_altitude']))
        elif cmd_type == 'mission':
            # Load and execute a predefined mission
            self.drone.load_mission(command['mission_id'])
        elif cmd_type == 'shutdown':
            self.shutdown()
    
    def shutdown(self):
        """Safely shut down the drone system."""
        logger.info("Shutting down Drone System")
        self.running = False
        
        # Land the drone if it's flying
        if self.drone.is_flying():
            logger.info("Landing drone before shutdown")
            self.drone.land()
        
        # Disconnect from the drone
        self.drone.disconnect()
        
        # Stop other components
        self.detector.stop()
        self.communicator.stop()
        
        logger.info("Drone System shutdown complete")

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start the drone system
    drone_system = DroneSystem(args.config, args.simulation)
    if drone_system.start():
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            drone_system.shutdown()
    
    logger.info("Exiting Drone System") 