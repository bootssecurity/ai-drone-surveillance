import logging
import json
import threading
import queue
import time
import socket
import websockets
import asyncio
from datetime import datetime

logger = logging.getLogger("Communicator")

class Communicator:
    """
    Handles communication between the drone and ground control systems,
    supporting multiple communication methods including WebSockets and REST API.
    """
    
    def __init__(self, config):
        """
        Initialize the communicator with configuration.
        
        Args:
            config (dict): Configuration dictionary for communication
        """
        self.config = config
        self.comm_method = config.get('method', 'websocket')
        self.host = config.get('host', '0.0.0.0')
        self.port = config.get('port', 8000)
        self.clients = set()
        
        # Command and status queues
        self.command_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.alert_queue = queue.Queue()
        
        # WebSocket server
        self.websocket_server = None
        self.websocket_thread = None
        
        # REST API server
        self.rest_server = None
        self.rest_thread = None
        
        # Running flag
        self.running = False
        
        logger.info(f"Communicator initialized (Method: {self.comm_method})")
    
    def start(self):
        """Start the communication system."""
        if self.running:
            logger.warning("Communication system already running")
            return
            
        self.running = True
        
        # Start the appropriate communication method
        if self.comm_method == 'websocket':
            self._start_websocket_server()
        elif self.comm_method == 'rest':
            self._start_rest_server()
        elif self.comm_method == 'both':
            self._start_websocket_server()
            self._start_rest_server()
        else:
            logger.warning(f"Unknown communication method: {self.comm_method}")
            
        logger.info("Communication system started")
    
    def stop(self):
        """Stop the communication system."""
        if not self.running:
            return
            
        self.running = False
        
        # Stop WebSocket server if running
        if self.websocket_server:
            asyncio.run(self._stop_websocket_server())
            
        # Stop REST server if running
        if self.rest_server:
            self._stop_rest_server()
            
        logger.info("Communication system stopped")
    
    def send_status(self, status):
        """
        Send a status update to connected clients.
        
        Args:
            status (dict): Status information to send
        """
        # Add timestamp
        status['timestamp'] = datetime.now().isoformat()
        
        # Put status in queue for async sending
        self.status_queue.put(status)
    
    def send_alert(self, alert):
        """
        Send an alert to connected clients.
        
        Args:
            alert (dict): Alert information to send
        """
        # Add timestamp if not present
        if 'timestamp' not in alert:
            alert['timestamp'] = datetime.now().isoformat()
            
        # Add severity if not present
        if 'severity' not in alert:
            # Determine severity based on type
            if alert.get('type') == 'fire':
                alert['severity'] = 'critical'
            elif alert.get('type') == 'break_in':
                alert['severity'] = 'high'
            elif alert.get('type') == 'suspicious':
                alert['severity'] = 'medium'
            elif alert.get('type') == 'threat':
                alert['severity'] = 'high'
            else:
                alert['severity'] = 'medium'
        
        # Put alert in queue for async sending
        self.alert_queue.put(alert)
        
        logger.info(f"Alert queued: {alert.get('type')} - {alert.get('severity')}")
    
    def get_commands(self):
        """
        Get pending commands from clients.
        
        Returns:
            list: List of commands
        """
        commands = []
        while not self.command_queue.empty():
            commands.append(self.command_queue.get())
        return commands
    
    def _start_websocket_server(self):
        """Start the WebSocket server."""
        self.websocket_thread = threading.Thread(target=self._run_websocket_server)
        self.websocket_thread.daemon = True
        self.websocket_thread.start()
        logger.info(f"WebSocket server started on {self.host}:{self.port}")
    
    def _run_websocket_server(self):
        """Run the WebSocket server in a separate thread."""
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Define handler for WebSocket connections
        async def handler(websocket, path):
            # Register client
            self.clients.add(websocket)
            client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            logger.info(f"New WebSocket client connected: {client_info}")
            
            try:
                # Start tasks for sending status updates and alerts
                sender_task = asyncio.create_task(self._websocket_sender(websocket))
                
                # Handle incoming messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Check if it's a command
                        if 'type' in data:
                            # Add to command queue
                            self.command_queue.put(data)
                            logger.info(f"Received command: {data.get('type')}")
                            
                            # Send acknowledgment
                            await websocket.send(json.dumps({
                                'type': 'ack',
                                'command': data.get('type'),
                                'timestamp': datetime.now().isoformat(),
                                'status': 'received'
                            }))
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON from client: {client_info}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"WebSocket client disconnected: {client_info}")
            finally:
                # Clean up
                self.clients.remove(websocket)
                sender_task.cancel()
        
        # Start the WebSocket server
        start_server = websockets.serve(
            handler, 
            self.host, 
            self.port
        )
        
        # Run server
        self.websocket_server = loop.run_until_complete(start_server)
        loop.run_forever()
    
    async def _websocket_sender(self, websocket):
        """
        Task to send status updates and alerts to a WebSocket client.
        
        Args:
            websocket: WebSocket connection
        """
        while self.running:
            try:
                # Send status updates
                if not self.status_queue.empty():
                    status = self.status_queue.get()
                    await websocket.send(json.dumps({
                        'type': 'status',
                        'data': status
                    }))
                
                # Send alerts
                if not self.alert_queue.empty():
                    alert = self.alert_queue.get()
                    await websocket.send(json.dumps({
                        'type': 'alert',
                        'data': alert
                    }))
                
                # Sleep a bit to avoid tight loop
                await asyncio.sleep(0.1)
                
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket sender: {str(e)}")
                await asyncio.sleep(1)
    
    async def _stop_websocket_server(self):
        """Stop the WebSocket server."""
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.websocket_server = None
    
    def _start_rest_server(self):
        """Start the REST API server."""
        try:
            from flask import Flask, request, jsonify
            
            app = Flask(__name__)
            
            # Define routes
            @app.route('/api/status', methods=['GET'])
            def get_status():
                # This would normally retrieve the latest status
                # For simplicity, we'll just return a placeholder
                return jsonify({
                    'status': 'ok',
                    'message': 'REST API is running'
                })
            
            @app.route('/api/command', methods=['POST'])
            def post_command():
                try:
                    command = request.json
                    if 'type' in command:
                        self.command_queue.put(command)
                        logger.info(f"Received REST command: {command.get('type')}")
                        return jsonify({
                            'status': 'ok',
                            'message': 'Command received'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Invalid command format'
                        }), 400
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': str(e)
                    }), 500
            
            # Start the server in a separate thread
            self.rest_thread = threading.Thread(
                target=lambda: app.run(
                    host=self.config.get('rest_host', self.host),
                    port=self.config.get('rest_port', self.port + 1),
                    debug=False
                )
            )
            self.rest_thread.daemon = True
            self.rest_thread.start()
            
            self.rest_server = app
            logger.info(f"REST API server started on {self.config.get('rest_host', self.host)}:"
                      f"{self.config.get('rest_port', self.port + 1)}")
            
        except ImportError:
            logger.warning("Flask not available. REST API server not started.")
    
    def _stop_rest_server(self):
        """Stop the REST API server."""
        # This is a bit tricky with Flask in a thread
        # For a proper implementation, you'd use a proper WSGI server with shutdown capabilities
        # This is just a placeholder
        self.rest_server = None
        logger.info("REST API server stopped") 