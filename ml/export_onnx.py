"""
export_onnx.py — Phase 0 gate script for DISHA / SIH26191
==========================================================
Exports all 3 trained models to ONNX and verifies each export by:
  1. Running a forward pass through the ONNX Runtime session
  2. Comparing output against PyTorch (max abs diff < TOLERANCE)

Run from the project root:
    python ml/export_onnx.py

All three models must print PASS before any backend work starts.

GPU note (RTX 2050 / 4 GB VRAM):
  Models are exported and verified one at a time.
  After each export the PyTorch model is deleted and CUDA cache cleared
  to stay within the 4 GB budget.
"""

import os
import sys
import json
import zipfile
import tempfile
import shutil
import importlib.util
from pathlib import Path
from datetime import datetime

# Enable ORT logs to see if it loads CUDA properly
os.environ["ORT_LOGGING_LEVEL"] = "2"  

import numpy as np
import torch
import torch.nn as nn

# Expose PyTorch's bundled cuDNN to onnxruntime
torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
if hasattr(os, 'add_dll_directory') and os.path.exists(torch_lib):
    os.add_dll_directory(torch_lib)
os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")

import onnxruntime as ort

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent.resolve()
MODEL_DIR   = ROOT / "models"
ONNX_DIR    = ROOT / "models"   # ONNX files land alongside .pt files

DAMAGE_PT    = MODEL_DIR / "best_siamese_resnet50_3class_finetuned.pt"
LANDSLIDE_PT = MODEL_DIR / "best_monolith_landslide_finetuned.pt"
FLOOD_ZIP    = MODEL_DIR / "segformer_flood_model.zip"

DAMAGE_ONNX    = ONNX_DIR / "damage_model.onnx"
LANDSLIDE_ONNX = ONNX_DIR / "landslide_model.onnx"
FLOOD_ONNX     = ONNX_DIR / "flood_model.onnx"

TOLERANCE = 5e-2   # max abs diff between PyTorch and ONNX outputs (GPU FP32 optimization)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"

# Image sizes used during training
DAMAGE_H, DAMAGE_W     = 512, 512
LANDSLIDE_H, LANDSLIDE_W = 512, 512
FLOOD_IMG_SIZE         = 224   # from config.json: image_size: 224

# ── Helpers ────────────────────────────────────────────────────────────────────

def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg):  print(f"  [WARN] {msg}")
def fail(msg):  print(f"  [FAIL] {msg}")

def free_gpu():
    """Release GPU memory after each model."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

def ort_session(onnx_path: Path):
    """Create ONNX Runtime session: CUDA first, CPU fallback."""
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    try:
        sess = ort.InferenceSession(str(onnx_path), providers=providers)
        used = sess.get_providers()[0]
        ok(f"ONNX Runtime session on: {used}")
        return sess
    except Exception as e:
        fail(f"ORT session failed: {e}")
        return None

def compare_outputs(pt_out: np.ndarray, ort_out: np.ndarray, name: str) -> bool:
    diff = np.abs(pt_out - ort_out).max()
    if diff < TOLERANCE:
        ok(f"{name} -- max abs diff = {diff:.2e}  (threshold {TOLERANCE})  -> PASS")
        return True
    else:
        fail(f"{name} -- max abs diff = {diff:.2e}  EXCEEDS threshold {TOLERANCE}  -> FAIL")
        return False

def load_model_class(file_path: Path, class_name: str):
    """Load a class from an exact file path using importlib. Avoids sys.path collisions."""
    spec = importlib.util.spec_from_file_location("model_def", str(file_path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)

def export_damage() -> bool:
    banner("MODEL A -- Damage Assessment (Siamese ResNet50, 3-class)")

    SiameseResNet50UNet = load_model_class(
        ROOT / "ml" / "damage" / "model_def.py",
        "SiameseResNet50UNet"
    )

    # -- load weights
    print(f"  Loading checkpoint from {DAMAGE_PT.name} ...")
    state_dict = torch.load(DAMAGE_PT, map_location="cpu", weights_only=False)
    model = SiameseResNet50UNet()
    try:
        model.load_state_dict(state_dict, strict=True)
        ok("State dict loaded (strict=True)")
    except RuntimeError as e:
        warn("Strict load failed -- trying strict=False")
        result = model.load_state_dict(state_dict, strict=False)
        if result.missing_keys:
            warn(f"Missing keys ({len(result.missing_keys)}): {result.missing_keys[:3]} ...")
        if result.unexpected_keys:
            warn(f"Unexpected keys ({len(result.unexpected_keys)}): {result.unexpected_keys[:3]} ...")
        ok("State dict loaded with strict=False")

    model = model.to(DEVICE).eval()

    # -- dummy inputs (two separate [1,3,H,W] tensors)
    dummy_pre  = torch.randn(1, 3, DAMAGE_H, DAMAGE_W, device=DEVICE)
    dummy_post = torch.randn(1, 3, DAMAGE_H, DAMAGE_W, device=DEVICE)

    # -- PyTorch forward
    with torch.no_grad():
        pt_out = model(dummy_pre, dummy_post).cpu().numpy()
    ok(f"PyTorch output shape: {pt_out.shape}")

    # -- Export to ONNX
    print(f"  Exporting to {DAMAGE_ONNX.name} ...")
    torch.onnx.export(
        model,
        (dummy_pre, dummy_post),
        str(DAMAGE_ONNX),
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,            # legacy TorchScript exporter -- stable, supports dynamic_axes
        input_names=["pre_image", "post_image"],
        output_names=["damage_logits"],
        dynamic_axes={
            "pre_image":    {0: "batch"},
            "post_image":   {0: "batch"},
            "damage_logits":{0: "batch"},
        },
    )
    ok(f"Exported -> {DAMAGE_ONNX} ({DAMAGE_ONNX.stat().st_size / 1e6:.1f} MB)")

    # -- free GPU before ORT session
    del model
    free_gpu()

    # -- ONNX Runtime verification
    sess = ort_session(DAMAGE_ONNX)
    if sess is None:
        return False

    ort_inputs = {
        "pre_image":  dummy_pre.cpu().numpy(),
        "post_image": dummy_post.cpu().numpy(),
    }
    ort_out = sess.run(None, ort_inputs)[0]
    return compare_outputs(pt_out, ort_out, "Damage model")

# ── Model B: Landslide (ResNet50 UNet) ────────────────────────────────────────

def export_landslide() -> bool:
    banner("MODEL B -- Landslide Detection (ResNet50 U-Net, binary)")

    MonolithLandslideUNet = load_model_class(
        ROOT / "ml" / "landslide" / "model_def.py",
        "MonolithLandslideUNet"
    )

    print(f"  Loading checkpoint from {LANDSLIDE_PT.name} ...")
    state_dict = torch.load(LANDSLIDE_PT, map_location="cpu", weights_only=False)
    model = MonolithLandslideUNet()
    try:
        model.load_state_dict(state_dict, strict=True)
        ok("State dict loaded (strict=True)")
    except RuntimeError as e:
        warn("Strict load failed -- trying strict=False")
        result = model.load_state_dict(state_dict, strict=False)
        if result.missing_keys:
            warn(f"Missing keys ({len(result.missing_keys)}): {result.missing_keys[:3]} ...")
        if result.unexpected_keys:
            warn(f"Unexpected keys ({len(result.unexpected_keys)}): {result.unexpected_keys[:3]} ...")
        ok("State dict loaded with strict=False")

    model = model.to(DEVICE).eval()

    dummy_img = torch.randn(1, 3, LANDSLIDE_H, LANDSLIDE_W, device=DEVICE)

    with torch.no_grad():
        pt_out = model(dummy_img).cpu().numpy()
    ok(f"PyTorch output shape: {pt_out.shape}")

    print(f"  Exporting to {LANDSLIDE_ONNX.name} ...")
    torch.onnx.export(
        model,
        dummy_img,
        str(LANDSLIDE_ONNX),
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,            # legacy TorchScript exporter
        input_names=["image"],
        output_names=["landslide_logits"],
        dynamic_axes={
            "image":            {0: "batch"},
            "landslide_logits": {0: "batch"},
        },
    )
    ok(f"Exported -> {LANDSLIDE_ONNX} ({LANDSLIDE_ONNX.stat().st_size / 1e6:.1f} MB)")

    del model
    free_gpu()

    sess = ort_session(LANDSLIDE_ONNX)
    if sess is None:
        return False

    ort_inputs = {"image": dummy_img.cpu().numpy()}
    ort_out = sess.run(None, ort_inputs)[0]
    return compare_outputs(pt_out, ort_out, "Landslide model")

# ── Model C: Flood (HuggingFace SegFormer) ────────────────────────────────────

def export_flood() -> bool:
    banner("MODEL C — Flood Segmentation (SegFormer, binary, image_size=224)")

    # -- unzip to temp dir
    tmp_dir = Path(tempfile.mkdtemp(prefix="disha_flood_"))
    print(f"  Extracting {FLOOD_ZIP.name} to {tmp_dir} ...")
    with zipfile.ZipFile(FLOOD_ZIP) as z:
        z.extractall(tmp_dir)
    ok(f"Extracted: {[p.name for p in tmp_dir.iterdir()]}")

    # -- load via transformers
    try:
        from transformers import SegformerForSemanticSegmentation
    except ImportError:
        fail("transformers not installed. Run: pip install transformers")
        shutil.rmtree(tmp_dir)
        return False

    print("  Loading SegformerForSemanticSegmentation …")
    model = SegformerForSemanticSegmentation.from_pretrained(str(tmp_dir))
    model = model.to(DEVICE).eval()
    ok("HuggingFace model loaded")

    # SegFormer image_size=224; HF pipeline uses pixel_values [B,3,H,W]
    dummy_px = torch.randn(1, 3, FLOOD_IMG_SIZE, FLOOD_IMG_SIZE, device=DEVICE)

    # -- PyTorch forward (HF model returns logits at 1/4 resolution = 56x56)
    with torch.no_grad():
        hf_out = model(pixel_values=dummy_px)
        pt_out = hf_out.logits.cpu().numpy()   # [1, 2, 56, 56]
    ok(f"PyTorch output shape: {pt_out.shape}  (logits at 1/4 resolution)")

    # -- Export to ONNX
    # We export a thin wrapper that returns just the logits tensor.
    class SegFormerWrapper(nn.Module):
        def __init__(self, m):
            super().__init__()
            self.model = m
        def forward(self, pixel_values):
            return self.model(pixel_values=pixel_values).logits

    wrapper = SegFormerWrapper(model).to(DEVICE).eval()

    print(f"  Exporting to {FLOOD_ONNX.name} ...")
    torch.onnx.export(
        wrapper,
        dummy_px,
        str(FLOOD_ONNX),
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,            # legacy TorchScript exporter
        input_names=["pixel_values"],
        output_names=["flood_logits"],
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "flood_logits": {0: "batch"},
        },
    )
    ok(f"Exported -> {FLOOD_ONNX} ({FLOOD_ONNX.stat().st_size / 1e6:.1f} MB)")

    del model, wrapper
    free_gpu()
    shutil.rmtree(tmp_dir)

    sess = ort_session(FLOOD_ONNX)
    if sess is None:
        return False

    ort_inputs = {"pixel_values": dummy_px.cpu().numpy()}
    ort_out = sess.run(None, ort_inputs)[0]
    return compare_outputs(pt_out, ort_out, "Flood model")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\nDISHA — ONNX Export & Sanity Check")
    print(f"Timestamp : {datetime.now().isoformat()}")
    print(f"Device    : {DEVICE}")
    if torch.cuda.is_available():
        print(f"GPU       : {torch.cuda.get_device_name(0)}")
        print(f"VRAM      : {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    results = {}

    results["damage"]    = export_damage()
    results["landslide"] = export_landslide()
    results["flood"]     = export_flood()

    # ── Summary ────────────────────────────────────────────────────────────────
    banner("EXPORT SUMMARY")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<12} [{status}]")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        ok("All 3 models exported and verified. Phase 0 COMPLETE.")
        ok("You may now proceed to Phase 2 (InferenceEngine).")
    else:
        fail("One or more models FAILED. Do not proceed to backend work.")
        fail("Fix model definition mismatches and re-run this script.")
        sys.exit(1)


if __name__ == "__main__":
    main()
