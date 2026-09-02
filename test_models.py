import onnxruntime as ort
import numpy as np
from PIL import Image

def _preprocess_image(img_path, target_size=(224, 224)):
    img = Image.open(img_path).convert("RGB")
    img = img.resize(target_size, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
    return arr

sess = ort.InferenceSession('c:/Users/Ashutosh/Desktop/DISHA/models/flood_model.onnx', providers=['CPUExecutionProvider'])
# Find a sample image in the project, maybe the user uploaded one to a temp folder?
# I'll just create a dummy input to see the output range.
dummy_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
out = sess.run(None, {'pixel_values': dummy_input})[0]
print("Flood model output shape:", out.shape)
print("Flood model min:", out.min(), "max:", out.max())

mask = np.argmax(out[0], axis=0)
print("Mask unique values:", np.unique(mask))
print("Class 1 count:", np.sum(mask == 1))

# Also let's check landslide model
sess_l = ort.InferenceSession('c:/Users/Ashutosh/Desktop/DISHA/models/landslide_model.onnx', providers=['CPUExecutionProvider'])
out_l = sess_l.run(None, {'pixel_values': dummy_input})[0]
print("\nLandslide model output shape:", out_l.shape)
mask_l = np.argmax(out_l[0], axis=0)
print("Landslide Mask unique values:", np.unique(mask_l))
print("Landslide Class 1 count:", np.sum(mask_l == 1))
