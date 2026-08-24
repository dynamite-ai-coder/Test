import logging
from io import BytesIO
import base64
from PIL import Image
from typing import Optional

logger = logging.getLogger(__name__)


class BrowserPreviewEncoder:
    """Encode browser screenshots for streaming preview."""
    
    @staticmethod
    def screenshot_to_base64(filepath: str) -> Optional[str]:
        """Convert screenshot to base64 for transmission."""
        try:
            with open(filepath, 'rb') as f:
                image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode screenshot: {e}")
            return None
    
    @staticmethod
    def resize_screenshot(filepath: str, max_width: int = 1280, max_height: int = 720) -> Optional[bytes]:
        """Resize screenshot for bandwidth efficiency."""
        try:
            img = Image.open(filepath)
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            output = BytesIO()
            img.save(output, format='PNG', quality=85)
            output.seek(0)
            return output.getvalue()
        except Exception as e:
            logger.error(f"Failed to resize screenshot: {e}")
            return None
    
    @staticmethod
    def generate_mjpeg_frame(filepath: str) -> Optional[bytes]:
        """Generate MJPEG frame from screenshot."""
        try:
            with open(filepath, 'rb') as f:
                image_data = f.read()
            
            frame = (
                b'--frameboundary\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(image_data)).encode() + b'\r\n'
                b'Content-Disposition: inline; filename="frame.jpg"\r\n\r\n'
                + image_data + b'\r\n'
            )
            return frame
        except Exception as e:
            logger.error(f"Failed to generate MJPEG frame: {e}")
            return None
