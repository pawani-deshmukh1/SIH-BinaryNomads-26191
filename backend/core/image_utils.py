import io
import numpy as np
from PIL import Image
from fastapi import UploadFile

def preprocess_image(file_bytes: bytes, target_size: int = 512) -> np.ndarray:
    """
    Reads image bytes, resizes, normalizes (ImageNet), and returns a tensor of shape [1, 3, H, W].
    """
    # 1. Open image
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    
    # 2. Resize
    img = img.resize((target_size, target_size), Image.Resampling.BILINEAR)
    
    # 3. Convert to numpy and scale to [0, 1]
    img_array = np.array(img, dtype=np.float32) / 255.0
    
    # 4. Normalize with ImageNet stats
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img_array = (img_array - mean) / std
    
    # 5. Transpose from HWC to CHW
    img_array = np.transpose(img_array, (2, 0, 1))
    
    # 6. Add batch dimension -> [1, 3, H, W]
    img_tensor = np.expand_dims(img_array, axis=0)
    
    return img_tensor
