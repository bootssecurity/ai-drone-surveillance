import logging
import time
import threading
import queue
import cv2
import numpy as np
import os
from datetime import datetime

# Import Coral libraries
try:
    from pycoral.adapters import common
    from pycoral.adapters import detect
    from pycoral.utils.dataset import read_label_file
    from pycoral.utils.edgetpu import make_interpreter
    CORAL_AVAILABLE = True
except ImportError:
    CORAL_AVAILABLE = False
    logging.warning("Google Coral libraries not available. Will fall back to TensorFlow.")
    import tensorflow as tf

logger = logging.getLogger("EmergencyDetector")

class EmergencyDetector:
    """
    Detector class that uses either Google Coral or TensorFlow to detect emergencies
    like fires, break-ins, suspicious activities, etc.
    """
    
    def __init__(self, config, use_coral=True):
        """
        Initialize the detector with configuration.
        
        Args:
            config (dict): Configuration dictionary for the detector
            use_coral (bool): Whether to use Google Coral for inference
        """
        self.config = config
        self.use_coral = use_coral and CORAL_AVAILABLE
        self.camera_source = config.get('camera_source', 0)  # Default to first camera
        self.detection_interval = config.get('detection_interval', 0.5)  # Seconds between detections
        
        # Initialize models based on what's available
        self.models = {
            'fire': self._load_model('fire'),
            'person': self._load_model('person'),
            'suspicious': self._load_model('suspicious'),
            'threat': self._load_model('threat')
        }
        
        # Event queue for detected emergencies
        self.event_queue = queue.Queue()
        
        # Detection thresholds
        self.thresholds = {
            'fire': config.get('fire_threshold', 0.7),
            'person': config.get('person_threshold', 0.8),
            'suspicious': config.get('suspicious_threshold', 0.6),
            'threat': config.get('threat_threshold', 0.75)
        }
        
        # Initialize video capture
        self.cap = None
        self.running = False
        self.frame_lock = threading.Lock()
        self.current_frame = None
        
        logger.info(f"Emergency detector initialized (Using Coral: {self.use_coral})")
    
    def _load_model(self, model_type):
        """
        Load an AI model for a specific type of detection.
        
        Args:
            model_type (str): Type of model to load (fire, person, etc.)
            
        Returns:
            object: Loaded model ready for inference
        """
        model_info = self.config.get(f'{model_type}_model', {})
        model_path = model_info.get('path', f'models/{model_type}_model.tflite')
        labels_path = model_info.get('labels', f'models/{model_type}_labels.txt')
        
        # Check if model exists
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return None
            
        try:
            if self.use_coral:
                # Load model for Coral Edge TPU
                interpreter = make_interpreter(model_path)
                interpreter.allocate_tensors()
                
                # Load labels if available
                labels = None
                if os.path.exists(labels_path):
                    labels = read_label_file(labels_path)
                
                return {
                    'interpreter': interpreter,
                    'labels': labels,
                    'input_details': interpreter.get_input_details(),
                    'output_details': interpreter.get_output_details()
                }
            else:
                # Fall back to TensorFlow
                interpreter = tf.lite.Interpreter(model_path=model_path)
                interpreter.allocate_tensors()
                
                # Load labels if available
                labels = None
                if os.path.exists(labels_path):
                    with open(labels_path, 'r') as f:
                        labels = {i: line.strip() for i, line in enumerate(f.readlines())}
                
                return {
                    'interpreter': interpreter,
                    'labels': labels,
                    'input_details': interpreter.get_input_details(),
                    'output_details': interpreter.get_output_details()
                }
                
        except Exception as e:
            logger.error(f"Failed to load {model_type} model: {str(e)}")
            return None
    
    def start(self):
        """Start the detection system."""
        if self.running:
            logger.warning("Detection system already running")
            return
            
        # Initialize camera
        try:
            self.cap = cv2.VideoCapture(self.camera_source)
            if not self.cap.isOpened():
                raise Exception(f"Failed to open camera source: {self.camera_source}")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {str(e)}")
            return
            
        self.running = True
        logger.info("Detection system started")
        
        # Start detection loop
        while self.running:
            try:
                # Capture frame
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Store current frame for other methods to access
                with self.frame_lock:
                    self.current_frame = frame
                
                # Perform detections
                self._process_frame(frame)
                
                # Wait before next detection
                time.sleep(self.detection_interval)
                
            except Exception as e:
                logger.error(f"Error in detection loop: {str(e)}")
                time.sleep(1)  # Wait a bit before trying again
        
        # Clean up
        if self.cap is not None:
            self.cap.release()
        logger.info("Detection system stopped")
    
    def stop(self):
        """Stop the detection system."""
        self.running = False
    
    def _process_frame(self, frame):
        """
        Process a video frame to detect emergencies.
        
        Args:
            frame (numpy.ndarray): Video frame to process
        """
        # Save the frame size for calculating coordinates
        height, width = frame.shape[:2]
        
        # Detect fires
        if self.models['fire']:
            fire_detected = self._detect_with_model('fire', frame)
            if fire_detected:
                self._add_event('fire', fire_detected)
        
        # Detect people (potential break-ins)
        if self.models['person']:
            people_detected = self._detect_with_model('person', frame)
            if people_detected:
                # Further analyze if this person represents a break-in
                # This would typically involve additional logic like:
                # - Is the person in a restricted area?
                # - Is it outside of authorized hours?
                # - Are they exhibiting suspicious behavior?
                for person in people_detected:
                    if self._analyze_break_in(person, frame):
                        self._add_event('break_in', person)
        
        # Detect suspicious activity
        if self.models['suspicious']:
            suspicious_detected = self._detect_with_model('suspicious', frame)
            if suspicious_detected:
                self._add_event('suspicious', suspicious_detected)
        
        # Detect threats
        if self.models['threat']:
            threats_detected = self._detect_with_model('threat', frame)
            if threats_detected:
                self._add_event('threat', threats_detected)
    
    def _detect_with_model(self, model_type, frame):
        """
        Perform detection with a specific model.
        
        Args:
            model_type (str): Type of model to use
            frame (numpy.ndarray): Frame to analyze
            
        Returns:
            list: List of detection results or None
        """
        model = self.models[model_type]
        if not model:
            return None
            
        try:
            # Resize and preprocess the image according to model requirements
            input_details = model['input_details'][0]
            required_height, required_width = input_details['shape'][1:3]
            
            # Resize frame to match model input
            resized_frame = cv2.resize(frame, (required_width, required_height))
            
            # Prepare input data based on model format
            if input_details['dtype'] == np.float32:
                # Normalize pixel values if using floating point
                input_data = np.expand_dims(resized_frame, axis=0).astype(np.float32) / 255.0
            else:
                # Keep as uint8 otherwise
                input_data = np.expand_dims(resized_frame, axis=0)
            
            if self.use_coral:
                # Run inference with Coral
                common.set_input(model['interpreter'], input_data)
                model['interpreter'].invoke()
                
                # Get detection results
                results = detect.get_objects(
                    model['interpreter'], 
                    score_threshold=self.thresholds[model_type]
                )
                
                if not results:
                    return None
                    
                # Convert results to our format
                detections = []
                frame_height, frame_width = frame.shape[:2]
                for result in results:
                    bbox = result.bbox
                    # Convert normalized coordinates if needed
                    x1 = int(bbox.xmin * frame_width)
                    y1 = int(bbox.ymin * frame_height)
                    x2 = int(bbox.xmax * frame_width)
                    y2 = int(bbox.ymax * frame_height)
                    
                    detection = {
                        'bbox': (x1, y1, x2, y2),
                        'confidence': result.score,
                        'class_id': result.id,
                        'class_name': model['labels'][result.id] if model['labels'] else f"class_{result.id}",
                        'location': self._calculate_location((x1, y1, x2, y2)),
                        'timestamp': datetime.now().isoformat()
                    }
                    detections.append(detection)
                
                return detections
            else:
                # Run inference with TensorFlow
                interpreter = model['interpreter']
                input_details = interpreter.get_input_details()
                output_details = interpreter.get_output_details()
                
                # Set input tensor
                interpreter.set_tensor(input_details[0]['index'], input_data)
                
                # Run inference
                interpreter.invoke()
                
                # Get detection results - format depends on model
                # This example assumes SSD model format with bounding boxes
                boxes = interpreter.get_tensor(output_details[0]['index'])[0]
                classes = interpreter.get_tensor(output_details[1]['index'])[0]
                scores = interpreter.get_tensor(output_details[2]['index'])[0]
                
                detections = []
                frame_height, frame_width = frame.shape[:2]
                
                for i in range(len(scores)):
                    if scores[i] >= self.thresholds[model_type]:
                        # Convert normalized coordinates
                        y1, x1, y2, x2 = boxes[i]
                        x1 = int(x1 * frame_width)
                        x2 = int(x2 * frame_width)
                        y1 = int(y1 * frame_height)
                        y2 = int(y2 * frame_height)
                        
                        class_id = int(classes[i])
                        detection = {
                            'bbox': (x1, y1, x2, y2),
                            'confidence': float(scores[i]),
                            'class_id': class_id,
                            'class_name': model['labels'][class_id] if model['labels'] else f"class_{class_id}",
                            'location': self._calculate_location((x1, y1, x2, y2)),
                            'timestamp': datetime.now().isoformat()
                        }
                        detections.append(detection)
                
                return detections
                
        except Exception as e:
            logger.error(f"Error during {model_type} detection: {str(e)}")
            return None
    
    def _analyze_break_in(self, person_detection, frame):
        """
        Analyze if a person detection represents a break-in.
        
        Args:
            person_detection (dict): Person detection result
            frame (numpy.ndarray): Frame where person was detected
            
        Returns:
            bool: True if this appears to be a break-in
        """
        # This would typically involve more sophisticated analysis,
        # such as checking against restricted zones, authorized personnel,
        # time of day, etc.
        
        # For this example, we'll just use a simple heuristic:
        # If the person is detected with high confidence and in certain areas
        confidence_threshold = self.config.get('break_in_confidence', 0.85)
        
        # Check confidence
        if person_detection['confidence'] < confidence_threshold:
            return False
            
        # Check if in restricted area (would come from geofencing)
        # This is a placeholder - real implementation would integrate with the geofence system
        x1, y1, x2, y2 = person_detection['bbox']
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        # Example: check if in a predefined restricted area
        restricted_areas = self.config.get('restricted_areas', [])
        for area in restricted_areas:
            if area['x1'] <= center_x <= area['x2'] and area['y1'] <= center_y <= area['y2']:
                # Person is in restricted area
                return True
        
        # Check time of day if needed
        current_hour = datetime.now().hour
        restricted_hours = self.config.get('restricted_hours', {})
        start_hour = restricted_hours.get('start', 22)  # e.g., 10 PM
        end_hour = restricted_hours.get('end', 6)      # e.g., 6 AM
        
        # Check if current time is within restricted hours
        if start_hour <= current_hour or current_hour < end_hour:
            # It's within restricted hours, so more likely to be a break-in
            return True
            
        # Not determined to be a break-in
        return False
    
    def _calculate_location(self, bbox):
        """
        Calculate the approximate real-world location based on a bounding box.
        This would typically use camera calibration, drone position, and other sensors.
        
        Args:
            bbox (tuple): Bounding box (x1, y1, x2, y2)
            
        Returns:
            dict: Location information
        """
        # This is a placeholder - real implementation would convert
        # pixel coordinates to real-world coordinates using the drone's
        # position, orientation, and camera parameters
        
        # For now, just return center of bounding box
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        return {
            'pixel_x': center_x,
            'pixel_y': center_y,
            # These would be calculated in a real system:
            'latitude': 0.0,
            'longitude': 0.0,
            'altitude': 0.0,
            'accuracy': 0.0
        }
    
    def _add_event(self, event_type, detection_results):
        """
        Add a detected event to the event queue.
        
        Args:
            event_type (str): Type of event (fire, break_in, etc.)
            detection_results (list): List of detection results
        """
        if isinstance(detection_results, list):
            for detection in detection_results:
                event = {
                    'type': event_type,
                    'timestamp': detection.get('timestamp', datetime.now().isoformat()),
                    'confidence': detection.get('confidence', 0.0),
                    'location': detection.get('location', {}),
                    'bbox': detection.get('bbox', (0, 0, 0, 0)),
                    'class_name': detection.get('class_name', '')
                }
                self.event_queue.put(event)
                logger.info(f"Added {event_type} event with confidence {event['confidence']:.2f}")
        else:
            # Single detection
            event = {
                'type': event_type,
                'timestamp': detection_results.get('timestamp', datetime.now().isoformat()),
                'confidence': detection_results.get('confidence', 0.0),
                'location': detection_results.get('location', {}),
                'bbox': detection_results.get('bbox', (0, 0, 0, 0)),
                'class_name': detection_results.get('class_name', '')
            }
            self.event_queue.put(event)
            logger.info(f"Added {event_type} event with confidence {event['confidence']:.2f}")
    
    def get_events(self):
        """
        Get all pending detected events.
        
        Returns:
            list: List of detected events
        """
        events = []
        while not self.event_queue.empty():
            events.append(self.event_queue.get())
        return events
    
    def get_current_frame(self):
        """
        Get the most recent frame captured by the detector.
        
        Returns:
            numpy.ndarray: Current video frame or None
        """
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None 