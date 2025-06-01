import logging
import time
import math
import threading
from enum import Enum

# Drone communication libraries
try:
    from dronekit import connect, VehicleMode, LocationGlobalRelative, Command
    from pymavlink import mavutil
    DRONEKIT_AVAILABLE = True
except ImportError:
    DRONEKIT_AVAILABLE = False
    logging.warning("DroneKit not available. Running in simulation mode only.")

logger = logging.getLogger("DroneController")

class DroneStatus(Enum):
    """Enum representing the drone's current status."""
    DISCONNECTED = 0
    CONNECTED = 1
    ARMED = 2
    FLYING = 3
    RETURNING = 4
    LANDING = 5
    ERROR = 6

class DroneController:
    """
    Controls the drone using DroneKit, handling autonomous navigation,
    waypoint management, and safety features.
    """
    
    def __init__(self, config, simulation_mode=False, geofence_manager=None):
        """
        Initialize the drone controller.
        
        Args:
            config (dict): Configuration dictionary for the drone
            simulation_mode (bool): Whether to operate in simulation mode
            geofence_manager (GeofenceManager): Geofence manager for safety boundaries
        """
        self.config = config
        self.simulation_mode = simulation_mode or not DRONEKIT_AVAILABLE
        self.geofence_manager = geofence_manager
        
        # Connection settings
        self.connection_string = config.get('connection_string', 'udp:127.0.0.1:14550')
        self.connection_timeout = config.get('connection_timeout', 30)
        self.baud_rate = config.get('baud_rate', 57600)
        
        # Flight parameters
        self.default_altitude = config.get('default_altitude', 10)  # meters
        self.max_altitude = config.get('max_altitude', 30)  # meters
        self.default_airspeed = config.get('default_airspeed', 3)  # m/s
        self.return_airspeed = config.get('return_airspeed', 5)  # m/s
        
        # Home location (will be set upon connection)
        self.home_location = None
        
        # Status and vehicle object
        self.status = DroneStatus.DISCONNECTED
        self.vehicle = None
        
        # Threading for background operations
        self.monitoring_thread = None
        self.running = False
        
        # Mission and waypoint tracking
        self.current_mission = None
        self.current_waypoint_index = 0
        
        logger.info(f"Drone controller initialized (Simulation mode: {self.simulation_mode})")
    
    def connect(self):
        """
        Connect to the drone.
        
        Returns:
            bool: True if connection succeeded, False otherwise
        """
        if self.status != DroneStatus.DISCONNECTED:
            logger.warning("Already connected to drone")
            return True
            
        if self.simulation_mode:
            logger.info("Running in simulation mode - creating virtual drone")
            self._create_simulated_drone()
            self.status = DroneStatus.CONNECTED
            return True
            
        try:
            logger.info(f"Connecting to drone at {self.connection_string}")
            self.vehicle = connect(
                self.connection_string,
                baud=self.baud_rate,
                wait_ready=True,
                timeout=self.connection_timeout
            )
            
            # Set up home location
            self.home_location = self.vehicle.location.global_relative_frame
            logger.info(f"Connected to drone. Home location set to: "
                        f"Lat: {self.home_location.lat}, Lon: {self.home_location.lon}")
            
            # Set default parameters
            self.vehicle.airspeed = self.default_airspeed
            
            # Start monitoring thread
            self.running = True
            self.monitoring_thread = threading.Thread(target=self._monitor_drone)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            self.status = DroneStatus.CONNECTED
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to drone: {str(e)}")
            self.status = DroneStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from the drone."""
        if self.status == DroneStatus.DISCONNECTED:
            logger.warning("Drone already disconnected")
            return
            
        # Stop monitoring thread
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
            
        # Disconnect vehicle
        if self.vehicle:
            self.vehicle.close()
            self.vehicle = None
            
        self.status = DroneStatus.DISCONNECTED
        logger.info("Disconnected from drone")
    
    def takeoff(self, altitude=None):
        """
        Take off to a specified altitude.
        
        Args:
            altitude (float): Target altitude in meters, or None to use default
            
        Returns:
            bool: True if takeoff succeeded, False otherwise
        """
        if not altitude:
            altitude = self.default_altitude
            
        # Check if altitude is within allowed range
        if altitude > self.max_altitude:
            logger.warning(f"Requested altitude {altitude}m exceeds maximum {self.max_altitude}m. "
                           f"Using maximum altitude.")
            altitude = self.max_altitude
            
        if self.simulation_mode:
            logger.info(f"SIMULATION: Taking off to {altitude}m")
            self.status = DroneStatus.FLYING
            return True
            
        if not self.vehicle:
            logger.error("Cannot take off: Not connected to drone")
            return False
            
        if self.status == DroneStatus.FLYING:
            logger.warning("Drone is already flying")
            return True
            
        try:
            # Check if drone can be armed
            if not self.vehicle.is_armable:
                logger.error("Cannot arm drone: not armable")
                return False
                
            # Switch to GUIDED mode
            self.vehicle.mode = VehicleMode("GUIDED")
            
            # Arm the drone
            self.vehicle.armed = True
            
            # Wait for arming
            start_time = time.time()
            while not self.vehicle.armed:
                if time.time() - start_time > 10:
                    logger.error("Arming timeout")
                    return False
                logger.info("Waiting for arming...")
                time.sleep(1)
                
            # Take off
            logger.info(f"Taking off to {altitude}m")
            self.vehicle.simple_takeoff(altitude)
            
            # Wait until target altitude is reached
            while True:
                current_altitude = self.vehicle.location.global_relative_frame.alt
                logger.info(f"Current altitude: {current_altitude}m")
                
                # Break if close enough to target altitude
                if current_altitude >= altitude * 0.95:
                    break
                    
                time.sleep(1)
                
            logger.info(f"Target altitude of {altitude}m reached")
            self.status = DroneStatus.FLYING
            return True
            
        except Exception as e:
            logger.error(f"Takeoff failed: {str(e)}")
            return False
    
    def land(self):
        """
        Land the drone at the current location.
        
        Returns:
            bool: True if landing command was sent successfully
        """
        if self.simulation_mode:
            logger.info("SIMULATION: Landing drone")
            self.status = DroneStatus.LANDING
            # Simulate landing time
            threading.Timer(5.0, self._simulated_landing_complete).start()
            return True
            
        if not self.vehicle:
            logger.error("Cannot land: Not connected to drone")
            return False
            
        if self.status not in [DroneStatus.FLYING, DroneStatus.RETURNING]:
            logger.warning("Drone is not flying, cannot land")
            return False
            
        try:
            # Send land command
            logger.info("Landing drone")
            self.vehicle.mode = VehicleMode("LAND")
            self.status = DroneStatus.LANDING
            return True
            
        except Exception as e:
            logger.error(f"Landing failed: {str(e)}")
            return False
    
    def return_to_home(self):
        """
        Command the drone to return to its home location.
        
        Returns:
            bool: True if return command was successful
        """
        if self.simulation_mode:
            logger.info("SIMULATION: Returning to home location")
            self.status = DroneStatus.RETURNING
            # Simulate return time
            threading.Timer(10.0, self._simulated_landing_complete).start()
            return True
            
        if not self.vehicle:
            logger.error("Cannot return home: Not connected to drone")
            return False
            
        if self.status != DroneStatus.FLYING:
            logger.warning("Drone is not flying, cannot return home")
            return False
            
        try:
            # Set return airspeed
            self.vehicle.airspeed = self.return_airspeed
            
            # Send RTL command
            logger.info("Returning to home location")
            self.vehicle.mode = VehicleMode("RTL")
            self.status = DroneStatus.RETURNING
            return True
            
        except Exception as e:
            logger.error(f"Return to home failed: {str(e)}")
            return False
    
    def move_to_coordinates(self, location, altitude=None):
        """
        Move to specific coordinates.
        
        Args:
            location (dict): Dictionary with latitude and longitude
            altitude (float): Target altitude in meters, or None to maintain current altitude
            
        Returns:
            bool: True if command was successful
        """
        if self.simulation_mode:
            logger.info(f"SIMULATION: Moving to lat={location.get('latitude', 0.0)}, "
                        f"lon={location.get('longitude', 0.0)}, alt={altitude or 'current'}")
            return True
            
        if not self.vehicle:
            logger.error("Cannot move: Not connected to drone")
            return False
            
        if self.status != DroneStatus.FLYING:
            logger.warning("Drone is not flying, cannot move")
            return False
            
        # Get coordinates
        lat = location.get('latitude')
        lon = location.get('longitude')
        
        if lat is None or lon is None:
            logger.error("Cannot move: Invalid coordinates")
            return False
            
        # Check if coordinates are within geofence
        if self.geofence_manager and not self.geofence_manager.is_point_inside(lat, lon):
            logger.warning(f"Coordinates ({lat}, {lon}) are outside geofence. "
                          f"Adjusting to nearest safe point.")
            safe_lat, safe_lon = self.geofence_manager.get_nearest_safe_point(lat, lon)
            lat, lon = safe_lat, safe_lon
            
        # Use current altitude if not specified
        if altitude is None:
            altitude = self.vehicle.location.global_relative_frame.alt
        else:
            # Check altitude limits
            if altitude > self.max_altitude:
                logger.warning(f"Requested altitude {altitude}m exceeds maximum {self.max_altitude}m. "
                             f"Using maximum altitude.")
                altitude = self.max_altitude
                
        try:
            # Create target location
            target = LocationGlobalRelative(lat, lon, altitude)
            
            # Send command to move to location
            logger.info(f"Moving to lat={lat}, lon={lon}, alt={altitude}m")
            self.vehicle.simple_goto(target)
            return True
            
        except Exception as e:
            logger.error(f"Move to coordinates failed: {str(e)}")
            return False
    
    def load_mission(self, mission_id):
        """
        Load and execute a predefined mission.
        
        Args:
            mission_id (str): ID of the mission to load
            
        Returns:
            bool: True if mission was loaded successfully
        """
        if self.simulation_mode:
            logger.info(f"SIMULATION: Loading mission {mission_id}")
            return True
            
        if not self.vehicle:
            logger.error("Cannot load mission: Not connected to drone")
            return False
            
        # Mission should be loaded from config or database
        mission_data = self.config.get('missions', {}).get(mission_id)
        if not mission_data:
            logger.error(f"Mission {mission_id} not found")
            return False
            
        try:
            # Clear any existing mission
            self.vehicle.commands.clear()
            
            # Add waypoints
            for i, waypoint in enumerate(mission_data.get('waypoints', [])):
                lat = waypoint.get('latitude')
                lon = waypoint.get('longitude')
                alt = waypoint.get('altitude', self.default_altitude)
                
                # Check if within geofence
                if self.geofence_manager and not self.geofence_manager.is_point_inside(lat, lon):
                    logger.warning(f"Waypoint {i} ({lat}, {lon}) is outside geofence. "
                                  f"Adjusting to nearest safe point.")
                    safe_lat, safe_lon = self.geofence_manager.get_nearest_safe_point(lat, lon)
                    lat, lon = safe_lat, safe_lon
                
                # Add command
                cmd = Command(
                    0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0,
                    lat, lon, alt
                )
                self.vehicle.commands.add(cmd)
            
            # Upload mission
            self.vehicle.commands.upload()
            
            # Start mission
            logger.info(f"Starting mission {mission_id} with {len(mission_data.get('waypoints', []))} waypoints")
            self.vehicle.mode = VehicleMode("AUTO")
            self.current_mission = mission_id
            self.current_waypoint_index = 0
            return True
            
        except Exception as e:
            logger.error(f"Loading mission failed: {str(e)}")
            return False
    
    def get_status(self):
        """
        Get the current status of the drone.
        
        Returns:
            dict: Status information
        """
        if self.simulation_mode:
            # Return simulated status
            return {
                'status': self.status.name,
                'location': {
                    'latitude': 0.0,
                    'longitude': 0.0,
                    'altitude': self.default_altitude if self.status == DroneStatus.FLYING else 0.0
                },
                'battery': {
                    'voltage': 12.0,
                    'current': 10.0,
                    'level': 75.0
                },
                'airspeed': self.default_airspeed,
                'heading': 0,
                'mission': self.current_mission,
                'waypoint': self.current_waypoint_index
            }
            
        if not self.vehicle:
            return {
                'status': DroneStatus.DISCONNECTED.name
            }
            
        # Get actual status from vehicle
        location = self.vehicle.location.global_relative_frame
        battery = self.vehicle.battery
        
        return {
            'status': self.status.name,
            'location': {
                'latitude': location.lat,
                'longitude': location.lon,
                'altitude': location.alt
            },
            'battery': {
                'voltage': battery.voltage,
                'current': battery.current,
                'level': battery.level
            },
            'airspeed': self.vehicle.airspeed,
            'heading': self.vehicle.heading,
            'mission': self.current_mission,
            'waypoint': self.current_waypoint_index
        }
    
    def is_flying(self):
        """
        Check if the drone is currently flying.
        
        Returns:
            bool: True if the drone is flying
        """
        return self.status in [DroneStatus.FLYING, DroneStatus.RETURNING]
    
    def _create_simulated_drone(self):
        """Create a simulated drone for testing."""
        # This would normally start a simulated vehicle
        # For this example, we'll just set some flags
        logger.info("Created simulated drone")
        self.home_location = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 0.0
        }
    
    def _simulated_landing_complete(self):
        """Callback for simulated landing completion."""
        logger.info("SIMULATION: Landing complete")
        self.status = DroneStatus.CONNECTED
    
    def _monitor_drone(self):
        """Monitor drone status and handle events."""
        logger.info("Starting drone monitoring thread")
        
        while self.running and self.vehicle:
            try:
                # Check for mode changes
                if self.vehicle.mode.name == "LAND" and self.status != DroneStatus.LANDING:
                    logger.info("Detected LAND mode change")
                    self.status = DroneStatus.LANDING
                elif self.vehicle.mode.name == "RTL" and self.status != DroneStatus.RETURNING:
                    logger.info("Detected RTL mode change")
                    self.status = DroneStatus.RETURNING
                
                # Check if landed
                if self.status == DroneStatus.LANDING and not self.vehicle.armed:
                    logger.info("Drone has landed")
                    self.status = DroneStatus.CONNECTED
                
                # Check mission progress if in AUTO mode
                if self.vehicle.mode.name == "AUTO" and self.current_mission:
                    next_waypoint = self.vehicle.commands.next
                    if next_waypoint != self.current_waypoint_index:
                        self.current_waypoint_index = next_waypoint
                        logger.info(f"Moving to waypoint {self.current_waypoint_index}")
                
                # Battery monitoring
                if self.vehicle.battery.level is not None:
                    battery_level = self.vehicle.battery.level
                    if battery_level < self.config.get('critical_battery_level', 15):
                        logger.warning(f"CRITICAL BATTERY LEVEL: {battery_level}%. Returning home.")
                        self.return_to_home()
                    elif battery_level < self.config.get('low_battery_level', 30):
                        logger.warning(f"LOW BATTERY LEVEL: {battery_level}%")
                
                # Geofence checking
                if self.geofence_manager and self.status == DroneStatus.FLYING:
                    location = self.vehicle.location.global_relative_frame
                    if not self.geofence_manager.is_point_inside(location.lat, location.lon):
                        logger.warning("GEOFENCE BREACH DETECTED! Returning to safe area.")
                        # Get nearest safe point
                        safe_lat, safe_lon = self.geofence_manager.get_nearest_safe_point(
                            location.lat, location.lon
                        )
                        # Move to safe point
                        self.move_to_coordinates({'latitude': safe_lat, 'longitude': safe_lon})
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in drone monitoring: {str(e)}")
                time.sleep(5)  # Wait longer after an error
        
        logger.info("Drone monitoring thread stopped") 