"""
Video Stream Utility Module
Handles video input from files, RTSP streams, or webcams
"""
import cv2
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class VideoStream:
    """Video stream reader supporting files, RTSP, and webcams"""
    
    def __init__(self, source: str = "0", buffer_size: int = 1):
        """
        Initialize video stream
        
        Args:
            source: Video source - file path, RTSP URL, or webcam index (0, 1, etc.)
            buffer_size: Number of frames to buffer
        """
        self.source = source
        self.buffer_size = buffer_size
        self.cap = None
        self.fps = 30
        self.frame_width = 640
        self.frame_height = 480
        self.total_frames = 0
        
        # Try to parse as integer (webcam index)
        try:
            source_int = int(source)
            self.source = source_int
        except ValueError:
            pass
        
        self._initialize_capture()
    
    def _initialize_capture(self):
        """Initialize video capture"""
        self.cap = cv2.VideoCapture(self.source)
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open video source: {self.source}")
            raise ValueError(f"Cannot open video source: {self.source}")
        
        # Get video properties
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        if self.fps == 0:
            self.fps = 30  # Default fallback
        
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Initialized video stream: {self.frame_width}x{self.frame_height} @ {self.fps}fps")
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read next frame from stream
        
        Returns:
            (success, frame) tuple
        """
        if self.cap is None or not self.cap.isOpened():
            return False, None
        
        ret, frame = self.cap.read()
        
        return ret, frame
    
    def get_fps(self) -> int:
        """Get frames per second"""
        return self.fps
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get video resolution"""
        return self.frame_width, self.frame_height
    
    def get_total_frames(self) -> int:
        """Get total number of frames (0 for streams)"""
        return self.total_frames
    
    def set_position(self, frame_number: int):
        """
        Set current frame position
        
        Args:
            frame_number: Frame number to seek to
        """
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    
    def release(self):
        """Release video capture"""
        if self.cap is not None:
            self.cap.release()
            logger.info("Video stream released")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
    
    def is_opened(self) -> bool:
        """Check if stream is open"""
        return self.cap is not None and self.cap.isOpened()


class VideoWriter:
    """Video writer for saving processed videos"""
    
    def __init__(self, output_path: str, fps: int, width: int, height: int,
                 fourcc: str = 'mp4v'):
        """
        Initialize video writer
        
        Args:
            output_path: Output file path
            fps: Frames per second
            width: Frame width
            height: Frame height
            fourcc: Video codec fourcc code
        """
        self.output_path = output_path
        self.fps = fps
        self.width = width
        self.height = height
        
        fourcc_code = cv2.VideoWriter_fourcc(*fourcc)
        self.writer = cv2.VideoWriter(output_path, fourcc_code, fps, (width, height))
        
        if not self.writer.isOpened():
            logger.error(f"Failed to create video writer: {output_path}")
            raise ValueError(f"Cannot create video writer: {output_path}")
        
        logger.info(f"Created video writer: {output_path} ({width}x{height} @ {fps}fps)")
    
    def write(self, frame: np.ndarray):
        """Write a frame"""
        if self.writer is not None:
            self.writer.write(frame)
    
    def release(self):
        """Release video writer"""
        if self.writer is not None:
            self.writer.release()
            logger.info(f"Video saved to: {self.output_path}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
