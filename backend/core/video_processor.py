"""
video_processor.py — Drone video frame extraction (RESPOND layer)

Takes a video file, samples frames at a defined interval (e.g., 1 frame every 2 seconds),
and returns them as JPEG bytes for pipeline processing.
"""
import cv2
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def extract_frames(video_bytes: bytes, sample_every_n_seconds: float = 2.0) -> list[bytes]:
    """
    Extracts frames from video bytes at the specified interval.
    
    Args:
        video_bytes: Raw bytes of the uploaded video (mp4, avi, etc.)
        sample_every_n_seconds: How often to sample a frame (default 2 seconds)
        
    Returns:
        List of JPEG encoded image bytes.
    """
    # OpenCV VideoCapture cannot read from memory directly, requires temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(video_bytes)
        temp_path = f.name
        
    frames = []
    try:
        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            logger.error("[VideoProcessor] Could not open video file.")
            return []
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps != fps:  # Check for 0 or NaN
            fps = 30.0
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"[VideoProcessor] Opened video: FPS={fps:.1f}, Total Frames={total_frames}")
        
        frame_interval = max(1, int(fps * sample_every_n_seconds))
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_idx % frame_interval == 0:
                success, buffer = cv2.imencode('.jpg', frame)
                if success:
                    frames.append(buffer.tobytes())
                    
            frame_idx += 1
            
        cap.release()
        logger.info(f"[VideoProcessor] Extracted {len(frames)} frames (sampling every {sample_every_n_seconds}s)")
        
    except Exception as e:
        logger.error(f"[VideoProcessor] Error extracting frames: {e}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
    return frames
