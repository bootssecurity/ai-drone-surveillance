import logging
import math
import json
import os
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import nearest_points

logger = logging.getLogger("GeofenceManager")

class GeofenceManager:
    """
    Manages geofence boundaries for drone operations, ensuring the drone
    stays within designated safe areas.
    """
    
    def __init__(self, config):
        """
        Initialize the geofence manager with configuration.
        
        Args:
            config (dict): Configuration dictionary for the geofence
        """
        self.config = config
        self.boundaries = []
        self.max_altitude = config.get('max_altitude', 30)  # meters
        self.min_altitude = config.get('min_altitude', 2)   # meters
        self.buffer_distance = config.get('buffer_distance', 5)  # meters
        
        # Load boundaries from config
        self._load_boundaries()
        
        logger.info(f"Geofence manager initialized with {len(self.boundaries)} boundaries")
    
    def _load_boundaries(self):
        """Load geofence boundaries from configuration."""
        # Check if config has boundaries directly
        if 'boundaries' in self.config:
            for boundary in self.config['boundaries']:
                self._add_boundary(boundary)
        
        # Check if config has a file path to load from
        elif 'boundary_file' in self.config:
            file_path = self.config['boundary_file']
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        boundary_data = json.load(f)
                        
                    if isinstance(boundary_data, list):
                        # List of boundaries
                        for boundary in boundary_data:
                            self._add_boundary(boundary)
                    elif isinstance(boundary_data, dict):
                        # Single boundary or structured data
                        if 'boundaries' in boundary_data:
                            for boundary in boundary_data['boundaries']:
                                self._add_boundary(boundary)
                        else:
                            self._add_boundary(boundary_data)
                    
                except Exception as e:
                    logger.error(f"Failed to load boundary file: {str(e)}")
        
        # If no boundaries were loaded, create a default circular boundary
        if not self.boundaries and 'default_center' in self.config:
            center = self.config['default_center']
            radius = self.config.get('default_radius', 100)  # meters
            
            # Create a circular boundary
            self._create_circular_boundary(
                center.get('latitude', 0),
                center.get('longitude', 0),
                radius
            )
            logger.info(f"Created default circular boundary with radius {radius}m")
    
    def _add_boundary(self, boundary_data):
        """
        Add a boundary from config data.
        
        Args:
            boundary_data (dict): Boundary configuration
        """
        boundary_type = boundary_data.get('type', 'polygon')
        
        if boundary_type == 'polygon':
            # Polygon boundary
            coordinates = boundary_data.get('coordinates', [])
            if len(coordinates) >= 3:
                # Convert coordinates to shapely polygon
                polygon_points = [(point.get('longitude', 0), point.get('latitude', 0)) 
                               for point in coordinates]
                
                # Ensure the polygon is closed
                if polygon_points[0] != polygon_points[-1]:
                    polygon_points.append(polygon_points[0])
                    
                polygon = Polygon(polygon_points)
                
                # Add buffer if specified
                if boundary_data.get('buffer', 0) > 0:
                    # Convert buffer from meters to degrees (approximate)
                    buffer_degrees = self._meters_to_degrees(boundary_data['buffer'])
                    polygon = polygon.buffer(buffer_degrees)
                
                self.boundaries.append({
                    'type': 'polygon',
                    'geometry': polygon,
                    'name': boundary_data.get('name', f'Boundary_{len(self.boundaries)}')
                })
                logger.info(f"Added polygon boundary: {boundary_data.get('name', 'Unnamed')}")
                
        elif boundary_type == 'circle':
            # Circular boundary
            center = boundary_data.get('center', {})
            radius = boundary_data.get('radius', 100)  # meters
            
            self._create_circular_boundary(
                center.get('latitude', 0),
                center.get('longitude', 0),
                radius,
                boundary_data.get('name', f'Boundary_{len(self.boundaries)}')
            )
            logger.info(f"Added circular boundary: {boundary_data.get('name', 'Unnamed')}")
    
    def _create_circular_boundary(self, center_lat, center_lon, radius_meters, name=None):
        """
        Create a circular boundary.
        
        Args:
            center_lat (float): Center latitude
            center_lon (float): Center longitude
            radius_meters (float): Radius in meters
            name (str): Boundary name
        """
        # Convert radius from meters to degrees (approximate)
        radius_degrees = self._meters_to_degrees(radius_meters)
        
        # Create a circular polygon
        center_point = Point(center_lon, center_lat)
        circle = center_point.buffer(radius_degrees)
        
        self.boundaries.append({
            'type': 'circle',
            'geometry': circle,
            'name': name or f'Circle_{len(self.boundaries)}',
            'center': (center_lat, center_lon),
            'radius': radius_meters
        })
    
    def _meters_to_degrees(self, meters, latitude=0):
        """
        Convert distance in meters to approximate degrees.
        This is a simple approximation that varies with latitude.
        
        Args:
            meters (float): Distance in meters
            latitude (float): Latitude for conversion (affects longitude conversion)
            
        Returns:
            float: Approximate distance in degrees
        """
        # Approximate conversion (1 degree of latitude is about 111,111 meters)
        # For longitude, it varies with latitude
        if abs(latitude) > 89:
            # Avoid division by zero near poles
            latitude = 89 if latitude > 0 else -89
            
        # Convert meters to degrees (approximate)
        return meters / 111111.0
    
    def is_point_inside(self, latitude, longitude, altitude=None):
        """
        Check if a point is inside any of the geofence boundaries.
        
        Args:
            latitude (float): Point latitude
            longitude (float): Point longitude
            altitude (float): Point altitude (optional)
            
        Returns:
            bool: True if the point is inside the geofence
        """
        # Check altitude constraints if provided
        if altitude is not None:
            if altitude > self.max_altitude or altitude < self.min_altitude:
                return False
        
        # Create shapely point
        point = Point(longitude, latitude)
        
        # Check if the point is inside any boundary
        for boundary in self.boundaries:
            if boundary['geometry'].contains(point):
                return True
                
        # Not within any boundary
        return False
    
    def get_nearest_safe_point(self, latitude, longitude):
        """
        Get the nearest point that is inside the geofence.
        
        Args:
            latitude (float): Current latitude
            longitude (float): Current longitude
            
        Returns:
            tuple: Safe point (latitude, longitude)
        """
        point = Point(longitude, latitude)
        
        # If inside a boundary, return the same point
        for boundary in self.boundaries:
            if boundary['geometry'].contains(point):
                return latitude, longitude
        
        # Find the nearest point on any boundary
        nearest_boundary = None
        min_distance = float('inf')
        nearest_safe_point = None
        
        for boundary in self.boundaries:
            # Get the nearest point on the boundary
            nearest_point_on_boundary = nearest_points(point, boundary['geometry'])[1]
            
            # Calculate distance
            distance = point.distance(nearest_point_on_boundary)
            
            if distance < min_distance:
                min_distance = distance
                nearest_boundary = boundary
                nearest_safe_point = nearest_point_on_boundary
        
        if nearest_safe_point:
            # Move point slightly inside the boundary for safety
            if nearest_boundary['type'] == 'circle':
                # For circles, move towards center
                center_point = Point(nearest_boundary['center'][1], nearest_boundary['center'][0])
                # Create a line from nearest point to center
                line = LineString([nearest_safe_point, center_point])
                # Move a small distance along this line
                buffer_degrees = self._meters_to_degrees(self.buffer_distance)
                if line.length > buffer_degrees:
                    # Interpolate a point along the line
                    safe_point = line.interpolate(buffer_degrees)
                    return safe_point.y, safe_point.x
            
            # For polygons or if circle approach doesn't work, just return the boundary point
            return nearest_safe_point.y, nearest_safe_point.x
        
        # Fallback to the original point if no boundaries exist
        return latitude, longitude
    
    def calculate_breach_distance(self, latitude, longitude):
        """
        Calculate how far a point is outside the geofence.
        
        Args:
            latitude (float): Point latitude
            longitude (float): Point longitude
            
        Returns:
            float: Distance in meters outside the geofence (0 if inside)
        """
        point = Point(longitude, latitude)
        
        # If inside a boundary, return 0
        for boundary in self.boundaries:
            if boundary['geometry'].contains(point):
                return 0
        
        # Find the nearest point on any boundary
        min_distance_degrees = float('inf')
        
        for boundary in self.boundaries:
            # Get the nearest point on the boundary
            nearest_point = nearest_points(point, boundary['geometry'])[1]
            
            # Calculate distance in degrees
            distance_degrees = point.distance(nearest_point)
            
            if distance_degrees < min_distance_degrees:
                min_distance_degrees = distance_degrees
        
        # Convert degrees to meters (approximate)
        return min_distance_degrees * 111111.0
    
    def add_temporary_boundary(self, boundary_data):
        """
        Add a temporary boundary for the current session.
        
        Args:
            boundary_data (dict): Boundary configuration
            
        Returns:
            bool: True if boundary was added successfully
        """
        try:
            self._add_boundary(boundary_data)
            return True
        except Exception as e:
            logger.error(f"Failed to add temporary boundary: {str(e)}")
            return False
    
    def remove_boundary(self, boundary_name):
        """
        Remove a boundary by name.
        
        Args:
            boundary_name (str): Name of the boundary to remove
            
        Returns:
            bool: True if boundary was removed successfully
        """
        for i, boundary in enumerate(self.boundaries):
            if boundary['name'] == boundary_name:
                self.boundaries.pop(i)
                logger.info(f"Removed boundary: {boundary_name}")
                return True
                
        logger.warning(f"Boundary not found: {boundary_name}")
        return False
    
    def get_boundaries(self):
        """
        Get a list of all boundaries.
        
        Returns:
            list: List of boundary information
        """
        return [
            {
                'name': b['name'],
                'type': b['type'],
                # Other properties specific to boundary type
                **(
                    {'center': b['center'], 'radius': b['radius']} 
                    if b['type'] == 'circle' else {}
                )
            }
            for b in self.boundaries
        ] 