"""
WebSocket Stream Route
Real-time video streaming with anomaly alerts
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Set
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming
    
    Receives:
        - Configuration updates
        - Start/stop stream commands
        
    Sends:
        - Real-time detections
        - Anomaly alerts
        - Frame metadata
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            command = message.get('command')
            
            if command == 'ping':
                # Respond to keepalive
                await websocket.send_json({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'update_config':
                # Handle configuration updates
                config = message.get('config', {})
                logger.info(f"Config update received: {config}")
                
                await websocket.send_json({
                    'type': 'config_updated',
                    'config': config,
                    'timestamp': datetime.now().isoformat()
                })
            
            elif command == 'get_status':
                # Send current status
                await websocket.send_json({
                    'type': 'status',
                    'active_connections': len(manager.active_connections),
                    'timestamp': datetime.now().isoformat()
                })
            
            else:
                logger.warning(f"Unknown command: {command}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected normally")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


async def send_detection_update(detections: List[dict], frame_number: int):
    """
    Send detection update to all clients
    
    Args:
        detections: List of detection dictionaries
        frame_number: Current frame number
    """
    message = {
        'type': 'detection',
        'frame_number': frame_number,
        'detections': detections,
        'count': len(detections),
        'timestamp': datetime.now().isoformat()
    }
    
    await manager.broadcast(message)


async def send_anomaly_alert(event_type: str, details: dict, frame_number: int, snapshot: str = None):
    """
    Send anomaly alert to all clients
    
    Args:
        event_type: Type of anomaly (overcrowding, loitering, zone_violation, suspicious_activity)
        details: Event details dictionary
        frame_number: Frame number where event occurred
        snapshot: Optional base64 encoded snapshot
    """
    message = {
        'type': 'alert',
        'event_type': event_type,
        'frame_number': frame_number,
        'details': details,
        'timestamp': datetime.now().isoformat(),
        'snapshot': snapshot
    }
    
    await manager.broadcast(message)


async def send_tracking_update(tracks: List[dict], frame_number: int):
    """
    Send tracking update to all clients
    
    Args:
        tracks: List of tracked objects
        frame_number: Current frame number
    """
    message = {
        'type': 'tracking',
        'frame_number': frame_number,
        'tracks': tracks,
        'timestamp': datetime.now().isoformat()
    }
    
    await manager.broadcast(message)
