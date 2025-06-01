import json
import os
import logging
import sys

logger = logging.getLogger("Settings")

# Default configuration
DEFAULT_CONFIG = {
    # Drone settings
    "drone": {
        "connection_string": "udp:127.0.0.1:14550",
        "connection_timeout": 30,
        "baud_rate": 57600,
        "default_altitude": 10,
        "max_altitude": 30,
        "default_airspeed": 3,
        "return_airspeed": 5,
        "critical_battery_level": 15,
        "low_battery_level": 30,
        "missions": {
            "patrol": {
                "name": "Standard Patrol",
                "waypoints": [
                    {"latitude": 37.7749, "longitude": -122.4194, "altitude": 10},
                    {"latitude": 37.7750, "longitude": -122.4190, "altitude": 15},
                    {"latitude": 37.7755, "longitude": -122.4185, "altitude": 10},
                    {"latitude": 37.7753, "longitude": -122.4192, "altitude": 15}
                ]
            }
        }
    },
    
    # Detection settings
    "detection": {
        "camera_source": 0,
        "detection_interval": 0.5,
        "fire_threshold": 0.7,
        "person_threshold": 0.8,
        "suspicious_threshold": 0.6,
        "threat_threshold": 0.75,
        "break_in_confidence": 0.85,
        "restricted_hours": {
            "start": 22,  # 10 PM
            "end": 6      # 6 AM
        },
        "restricted_areas": [
            {"x1": 100, "y1": 100, "x2": 300, "y2": 300},
            {"x1": 400, "y1": 400, "x2": 600, "y2": 600}
        ],
        "fire_model": {
            "path": "models/fire_model.tflite",
            "labels": "models/fire_labels.txt"
        },
        "person_model": {
            "path": "models/person_model.tflite",
            "labels": "models/person_labels.txt"
        },
        "suspicious_model": {
            "path": "models/suspicious_model.tflite",
            "labels": "models/suspicious_labels.txt"
        },
        "threat_model": {
            "path": "models/threat_model.tflite",
            "labels": "models/threat_labels.txt"
        }
    },
    
    # Geofence settings
    "geofence": {
        "max_altitude": 30,
        "min_altitude": 2,
        "buffer_distance": 5,
        "default_center": {
            "latitude": 37.7749,
            "longitude": -122.4194
        },
        "default_radius": 100,
        "boundaries": [
            {
                "type": "circle",
                "name": "Main Area",
                "center": {
                    "latitude": 37.7749,
                    "longitude": -122.4194
                },
                "radius": 100
            },
            {
                "type": "polygon",
                "name": "Secondary Area",
                "coordinates": [
                    {"latitude": 37.7760, "longitude": -122.4190},
                    {"latitude": 37.7765, "longitude": -122.4180},
                    {"latitude": 37.7755, "longitude": -122.4175},
                    {"latitude": 37.7750, "longitude": -122.4185}
                ],
                "buffer": 5
            }
        ]
    },
    
    # Communication settings
    "communication": {
        "method": "websocket",  # websocket, rest, or both
        "host": "0.0.0.0",
        "port": 8000,
        "rest_host": "0.0.0.0",
        "rest_port": 8001
    },
    
    # Emergency response settings
    "emergency": {
        "fire_inspection_altitude": 15,
        "tracking_altitude": 10,
        "investigation_altitude": 12,
        "threat_observation_altitude": 20,
        "automatic_response": True,
        "alert_contacts": [
            {"name": "Security Office", "email": "security@example.com", "phone": "555-1234"},
            {"name": "Fire Department", "email": "fire@example.com", "phone": "555-5678"}
        ]
    }
}

def load_settings(config_path=None):
    """
    Load settings from a configuration file, falling back to defaults.
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
            
            # Merge user config with defaults
            merge_configs(config, user_config)
            logger.info(f"Loaded configuration from {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {str(e)}")
            logger.info("Using default configuration")
    else:
        if config_path:
            logger.warning(f"Configuration file not found: {config_path}")
        logger.info("Using default configuration")
    
    return config

def merge_configs(base_config, user_config):
    """
    Recursively merge user configuration into base configuration.
    
    Args:
        base_config (dict): Base configuration to update
        user_config (dict): User configuration to merge in
    """
    for key, value in user_config.items():
        if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
            # Recursively merge dictionaries
            merge_configs(base_config[key], value)
        else:
            # Replace or add value
            base_config[key] = value

def save_settings(config, config_path):
    """
    Save configuration to a file.
    
    Args:
        config (dict): Configuration dictionary
        config_path (str): Path to save configuration
        
    Returns:
        bool: True if saved successfully
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Save to file
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.info(f"Configuration saved to {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save configuration to {config_path}: {str(e)}")
        return False

def create_default_config(config_path):
    """
    Create a default configuration file if it doesn't exist.
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        bool: True if created successfully
    """
    if not os.path.exists(config_path):
        return save_settings(DEFAULT_CONFIG, config_path)
    return False

def update_setting(config, path, value):
    """
    Update a specific setting in the configuration.
    
    Args:
        config (dict): Configuration dictionary
        path (str): Dot-separated path to the setting (e.g., 'drone.max_altitude')
        value: New value for the setting
        
    Returns:
        bool: True if updated successfully
    """
    try:
        parts = path.split('.')
        current = config
        
        # Navigate to the nested dictionary
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Update the value
        current[parts[-1]] = value
        return True
        
    except Exception as e:
        logger.error(f"Failed to update setting {path}: {str(e)}")
        return False

def get_setting(config, path, default=None):
    """
    Get a specific setting from the configuration.
    
    Args:
        config (dict): Configuration dictionary
        path (str): Dot-separated path to the setting (e.g., 'drone.max_altitude')
        default: Default value if setting not found
        
    Returns:
        Value of the setting or default if not found
    """
    try:
        parts = path.split('.')
        current = config
        
        # Navigate to the nested dictionary
        for part in parts:
            if part not in current:
                return default
            current = current[part]
        
        return current
        
    except Exception:
        return default 