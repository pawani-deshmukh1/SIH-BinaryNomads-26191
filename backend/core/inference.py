import asyncio
import onnxruntime as ort
import numpy as np
from pathlib import Path
from .scoring_types import ModelConfidence
from datetime import datetime, timezone

class InferenceEngine:
    def __init__(self):
        # We assume models are mounted via docker-compose to /app/models or locally to ./models
        model_dir = Path(__file__).resolve().parent.parent.parent / "models"
        
        self.model_paths = {
            "damage": str(model_dir / "damage_model.onnx"),
            "flood": str(model_dir / "flood_model.onnx"),
            "landslide": str(model_dir / "landslide_model.onnx"),
        }
        
        # We attempt CUDA first, fallback to CPU
        self.providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    def run(self, model_name: str, inputs: dict[str, np.ndarray]) -> tuple[np.ndarray | None, ModelConfidence | None]:
        """
        Loads the ONNX model, runs inference, and unloads it to save VRAM.
        Inputs: dictionary mapping ONNX input names to numpy arrays.
        """
        if model_name not in self.model_paths:
            print(f"[InferenceEngine] Unknown model {model_name}")
            return None, None
            
        path = self.model_paths[model_name]
        if not Path(path).exists():
            print(f"[InferenceEngine] Model file missing: {path}")
            return None, None

        try:
            # Load into VRAM
            session = ort.InferenceSession(path, providers=self.providers)
            
            # Run inference
            output = session.run(None, inputs)
            
            # Unload from VRAM immediately (important for 4GB RTX 2050)
            del session
            
            # Extract output tensor
            logits = output[0]
            
            # Calculate a mock confidence for now based on max logit magnitude
            # In production, this would be softmax/sigmoid probability
            score = float(np.clip(np.max(logits) / 10.0, 0.0, 1.0))
            
            confidence = ModelConfidence(
                score=score,
                last_updated=datetime.now(timezone.utc)
            )
            
            return logits, confidence
            
        except Exception as e:
            print(f"[InferenceEngine] Error running {model_name}: {e}")
            return None, None

    async def run_async(self, model_name: str, inputs: dict[str, np.ndarray]) -> tuple[np.ndarray | None, 'ModelConfidence | None']:
        """
        Async wrapper around run() using asyncio.to_thread.
        Allows multiple models to be gathered in parallel:
            damage, flood, landslide = await asyncio.gather(
                engine.run_async('damage', d_inputs),
                engine.run_async('flood', f_inputs),
                engine.run_async('landslide', l_inputs),
            )
        """
        return await asyncio.to_thread(self.run, model_name, inputs)

# Singleton instance
engine = InferenceEngine()
