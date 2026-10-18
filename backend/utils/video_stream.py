"""
Video Stream Utility Module
Handles video ingestion from files, RTSP streams, or connected webcams
with reconnection backoff, timeout protection, and robust cleanup.
"""
import cv2
import numpy as np
import time
from typing import Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class VideoStream:
    """Resilient video stream reader supporting files, RTSP, and webcams"""
    
    def __init__(
        self,
        source: Union[str, int] = "0",
        buffer_size: int = 1,
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0
    ):
        """
        Initialize video stream reader.
        
        Args:
            source: Video source - file path, RTSP URL, or webcam index (0, 1, etc.)
            buffer_size: Number of frames to buffer
            max_reconnect_attempts: Times to attempt reconnection on failure
            reconnect_delay: Initial delay in seconds before reconnection
        """
        self.raw_source = source
        self.source = source
        self.buffer_size = buffer_size
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        
        self.cap = None
        self.fps = 30
        self.frame_width = 640
        self.frame_height = 480
        self.total_frames = 0
        self.is_live = False
        
        # Parse numeric camera index
        try:
            source_int = int(source)
            self.source = source_int
            self.is_live = True
        except (ValueError, TypeError):
            if isinstance(source, str) and (source.startswith("rtsp://") or source.startswith("http://") or source.startswith("https://")):
                self.is_live = True
        
        self._initialize_capture()
        
    def _initialize_capture(self) -> bool:
        """Initialize OpenCV video capture with timeout and buffer configuration."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
                
        # Optimize RTSP streams to use TCP transport (prevents packet loss and frame corruption)
        if isinstance(self.source, str) and self.source.startswith("rtsp://"):
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        # Set buffer size environment if supported
        try:
            self.cap = cv2.VideoCapture(self.source)
            if self.is_live:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        except Exception as e:
            logger.error(f"Failed to open video source '{self.source}': {e}")
            self.cap = None
            return False
            
        if not self.cap or not self.cap.isOpened():
            logger.error(f"Cannot open video source: {self.source}")
            return False
            
        # Probe properties
        fps_val = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = int(fps_val) if (fps_val and fps_val > 0 and fps_val < 240) else 30
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        
        logger.info(
            f"Initialized stream '{self.source}': {self.frame_width}x{self.frame_height} "
            f"@ {self.fps}fps (total_frames: {self.total_frames})"
        )
        return True
        
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read next frame with automatic reconnection on stream drop.
        
        Returns:
            (success: bool, frame: np.ndarray or None)
        """
        if self.cap is None or not self.cap.isOpened():
            if self.is_live:
                if not self._reconnect():
                    return False, None
            else:
                return False, None
                
        ret, frame = self.cap.read()
        
        # If frame read failed on a live stream, try reconnecting
        if not ret and self.is_live:
            logger.warning(f"Live stream frame read failed for '{self.source}'. Attempting reconnection...")
            if self._reconnect():
                ret, frame = self.cap.read()
                
        return ret, frame
        
    def _reconnect(self) -> bool:
        """Attempt to reconnect to live stream with backoff."""
        delay = self.reconnect_delay
        for attempt in range(1, self.max_reconnect_attempts + 1):
            logger.info(f"Reconnection attempt {attempt}/{self.max_reconnect_attempts} for '{self.source}' in {delay:.1f}s...")
            time.sleep(delay)
            if self._initialize_capture():
                logger.info(f"Successfully reconnected to '{self.source}'")
                return True
            delay *= 1.5  # Exponential backoff
            
        logger.error(f"Max reconnection attempts exhausted for '{self.source}'.")
        return False
        
    def get_fps(self) -> int:
        return self.fps
        
    def get_resolution(self) -> Tuple[int, int]:
        return self.frame_width, self.frame_height
        
    def get_total_frames(self) -> int:
        return self.total_frames
        
    def set_position(self, frame_number: int):
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
    def release(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
            logger.info(f"Video stream '{self.source}' released.")
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        
    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()
