from fastapi.testclient import TestClient
from backend.main import app
import io
from PIL import Image

client = TestClient(app)

def create_dummy_image_bytes():
    img = Image.new('RGB', (100, 100), color = 'red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def test_ml_endpoints():
    print("--- Testing Real ML ONNX Endpoints ---")
    
    img_bytes = create_dummy_image_bytes()
    
    # 1. Damage Endpoint
    print("\n1. Testing /damage/")
    resp = client.post("/damage/", files={
        "pre_image": ("pre.png", img_bytes, "image/png"),
        "post_image": ("post.png", img_bytes, "image/png")
    })
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] /damage/ success. Confidence: {data['model_confidence']['score']}")
        print(f"       Damage Severity Score: {data.get('severity_score', 'N/A')}")
        print(f"       Extracted Features: {len(data['features'])}")
    else:
        print(f"[FAIL] /damage/: {resp.status_code} {resp.text}")

    # 2. Flood Risk Endpoint
    print("\n2. Testing /flood-risk/")
    resp = client.post("/flood-risk/", files={"image": ("flood.png", img_bytes, "image/png")})
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] /flood-risk/ success. Risk Score: {data['risk_score']}")
    else:
        print(f"[FAIL] /flood-risk/: {resp.status_code} {resp.text}")

    # 3. Landslide Risk Endpoint
    print("\n3. Testing /landslide-risk/")
    resp = client.post("/landslide-risk/", files={"image": ("landslide.png", img_bytes, "image/png")})
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] /landslide-risk/ success. Risk Score: {data['risk_score']}")
    else:
        print(f"[FAIL] /landslide-risk/: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    test_ml_endpoints()
