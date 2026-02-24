#!/usr/bin/env python3
"""Export kenpath/svara-tts-v1 to ONNX and run a quick ORT sanity check.

Usage:
  python scripts/export_svara_onnx.py \
    --model-id kenpath/svara-tts-v1 \
    --output models/tts/svara/svara_tts.onnx
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path

import torch


def _load_model(model_id: str):
    from transformers import AutoModel, AutoModelForSpeechSeq2Seq

    last_exc: Exception | None = None
    for cls in (AutoModel, AutoModelForSpeechSeq2Seq):
        common_kwargs = {
            "use_safetensors": True,
            "trust_remote_code": True,
        }
        try:
            # Newer transformers prefers `dtype`; keep backward fallback below.
            return cls.from_pretrained(
                model_id,
                dtype=torch.float32,
                **common_kwargs,
            )
        except TypeError:
            try:
                return cls.from_pretrained(
                    model_id,
                    torch_dtype=torch.float32,
                    **common_kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"failed to load model {model_id}: {last_exc}")


def _load_tokenizer(model_id: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)


def export_onnx(model_id: str, output: Path, opset: int = 17) -> None:
    print(f"Loading model: {model_id}")
    model = _load_model(model_id)
    model.eval()

    print("Loading tokenizer...")
    tokenizer = _load_tokenizer(model_id)

    sample_text = "Hello, how are you?"
    encoded = tokenizer(sample_text, return_tensors="pt")
    input_ids = encoded["input_ids"]
    attention_mask = encoded.get("attention_mask", torch.ones_like(input_ids))
    if hasattr(model, "config"):
        # Avoid cache-related signature/graph issues during export.
        try:
            model.config.use_cache = False
        except Exception:
            pass

    class _OnnxWrapper(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner
            self._allowed = set(inspect.signature(inner.forward).parameters.keys())

        def forward(self, input_ids, attention_mask):
            kwargs = {}
            if "input_ids" in self._allowed:
                kwargs["input_ids"] = input_ids
            if "attention_mask" in self._allowed:
                kwargs["attention_mask"] = attention_mask
            out = self.inner(**kwargs)
            if hasattr(out, "last_hidden_state"):
                return out.last_hidden_state
            if isinstance(out, (tuple, list)) and len(out) > 0:
                return out[0]
            return out

    wrapper = _OnnxWrapper(model).eval()

    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Exporting ONNX to: {output}")
    torch.onnx.export(
        wrapper,
        (input_ids, attention_mask),
        str(output),
        input_names=["input_ids", "attention_mask"],
        output_names=["audio"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "audio": {0: "batch", 1: "time"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )

    print("Validating with ONNX Runtime...")
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    ort_inputs = {
        "input_ids": input_ids.detach().cpu().numpy().astype(np.int64),
        "attention_mask": attention_mask.detach().cpu().numpy().astype(np.int64),
    }
    ort_out = sess.run(["audio"], ort_inputs)
    if not ort_out or ort_out[0] is None:
        raise RuntimeError("ONNX Runtime produced empty output")

    print(f"DONE: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="kenpath/svara-tts-v1")
    parser.add_argument("--output", default="models/tts/svara/svara_tts.onnx")
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()

    export_onnx(args.model_id, Path(args.output), args.opset)


if __name__ == "__main__":
    main()
