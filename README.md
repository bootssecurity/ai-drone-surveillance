# AI-Powered Drone Surveillance System

A comprehensive drone control system using AI and Google Coral for real-time detection of break-ins, fires, suspicious activities, threats, and other emergencies with autonomous flying capabilities in a geofenced area.

## Features

- **Real-time Detection**: Uses Google Coral Edge TPU for efficient AI processing
  - Fire detection
  - Person/intruder detection
  - Suspicious activity detection
  - Threat assessment
  
- **Autonomous Flight**
  - Geofenced operation to ensure the drone stays within designated areas
  - Automated takeoff, landing, and return-to-home
  - Pre-configured patrol missions
  - Dynamic response to detected emergencies

- **Communication**
  - WebSocket-based real-time communication with ground control
  - REST API for system integration
  - Alert system for emergency notifications

- **Safety Features**
  - Geofencing to prevent fly-aways
  - Automatic return on low battery
  - Fail-safe mechanisms

## System Requirements

- Python 3.8+
- Google Coral Edge TPU (optional, falls back to TensorFlow)
- Compatible drone with MAVLink support
- Camera (onboard or connected to the processing system)
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/drone-surveillance.git
   cd drone-surveillance
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Download required AI models:
   ```
   # Create models directory
   mkdir -p models
   
   # Download models (examples)
   wget -O models/fire_model.tflite https://example.com/fire_model.tflite
   wget -O models/person_model.tflite https://example.com/person_model.tflite
   ```

4. Configure the system:
   - Edit `config/default_config.json` to match your environment
   - Set up geofencing boundaries
   - Configure detection thresholds

## Usage

### Starting the System

To start the system in normal mode:

```
python main.py --config config/default_config.json
```

To start in simulation mode (without connecting to a real drone):

```
python main.py --config config/default_config.json --simulation
```

Enable debug logging:

```
python main.py --config config/default_config.json --debug
```

### System Control

The system can be controlled through:

1. WebSocket interface (default port 8000)
2. REST API (default port 8001)

Example WebSocket command to start a patrol mission:

```javascript
// Connect to WebSocket
const socket = new WebSocket('ws://localhost:8000');

// Send a command
socket.send(JSON.stringify({
  type: 'mission',
  mission_id: 'patrol'
}));
```

Example REST API command to move the drone:

```bash
curl -X POST http://localhost:8001/api/command \
  -H "Content-Type: application/json" \
  -d '{"type":"move","coordinates":{"latitude":37.7749,"longitude":-122.4194},"altitude":15}'
```

## Architecture

The system consists of the following modules:

- **Main Control** (`main.py`): Coordinates all other components
- **Drone Control** (`drone_control/`): Handles drone flight operations
- **Detection** (`detection/`): AI-based detection of emergency situations
- **Geofence** (`geofence/`): Manages flight boundaries and safety constraints
- **Communication** (`communication/`): Handles ground station communication
- **Configuration** (`config/`): System settings and configuration

## Google Coral Integration

The system is designed to work with Google Coral Edge TPU for efficient AI processing. If a Coral device is detected, the system automatically uses it for inference. Otherwise, it falls back to using TensorFlow on the CPU.

To enable Coral:
1. Make sure your Coral device is connected
2. Install the PyCoral library as specified in requirements.txt
3. The system will automatically detect and use the Coral device

## Custom AI Models

To use custom AI models:
1. Convert your models to TensorFlow Lite format compatible with Coral
2. Place them in the `models/` directory
3. Update the configuration file to point to your models

## Expanding the System

The modular architecture makes it easy to extend the system:

- Add new detection models by updating the `EmergencyDetector` class
- Create new mission types in the configuration
- Implement additional safety features
- Integrate with other systems through the communication interfaces

## License

[MIT License](LICENSE)

## Acknowledgements

- DroneKit for drone control
- Google Coral team for edge AI capabilities
- OpenCV for computer vision processing 