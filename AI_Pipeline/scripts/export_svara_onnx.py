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
    from transformers import AutoConfig, AutoModel, AutoModelForSpeechSeq2Seq

    def _normalized_config():
        cfg = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
        rope = getattr(cfg, "rope_scaling", None)
        if isinstance(rope, dict) and "type" not in rope and "rope_type" in rope:
            # Backward-compatible normalization for older transformers that
            # expect only {"type", "factor"}.
            cfg.rope_scaling = {
                "type": rope.get("rope_type", "dynamic"),
                "factor": float(rope.get("factor", 1.0)),
            }
        return cfg

    last_exc: Exception | None = None
    for cls in (AutoModel, AutoModelForSpeechSeq2Seq):
        common_kwargs = {
            "use_safetensors": True,
            "trust_remote_code": True,
            # Avoid SDPA/vmap masking path that breaks ONNX tracing for some
            # Llama-based configs in recent torch/transformers combinations.
            "attn_implementation": "eager",
        }
        try:
            # Prefer FP16 for smaller/faster ONNX in CPU-only runtime.
            return cls.from_pretrained(
                model_id,
                dtype=torch.float16,
                **common_kwargs,
            )
        except TypeError:
            try:
                return cls.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    **common_kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                # Retry with normalized config for rope_scaling schema mismatch.
                if "rope_scaling" in str(exc):
                    try:
                        cfg = _normalized_config()
                        return cls.from_pretrained(
                            model_id,
                            torch_dtype=torch.float16,
                            config=cfg,
                            **common_kwargs,
                        )
                    except Exception as retry_exc:  # noqa: BLE001
                        last_exc = retry_exc
                        continue
                last_exc = exc
        except Exception as exc:  # noqa: BLE001
            # Retry with normalized config for rope_scaling schema mismatch.
            if "rope_scaling" in str(exc):
                try:
                    cfg = _normalized_config()
                    return cls.from_pretrained(
                        model_id,
                        torch_dtype=torch.float16,
                        config=cfg,
                        **common_kwargs,
                    )
                except Exception as retry_exc:  # noqa: BLE001
                    last_exc = retry_exc
                    continue
            last_exc = exc
    raise RuntimeError(f"failed to load model {model_id}: {last_exc}")


def _load_tokenizer(model_id: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)


def export_onnx(model_id: str, output: Path, opset: int = 17) -> None:
    print(f"Loading model: {model_id}")
    model = _load_model(model_id)
    model = model.half()
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
        try:
            model.config._attn_implementation = "eager"
        except Exception:
            pass

    class _OnnxWrapper(torch.nn.Module):
        def __init__(self, inner, include_attention_mask: bool):
            super().__init__()
            self.inner = inner
            self._allowed = set(inspect.signature(inner.forward).parameters.keys())
            self._include_attention_mask = include_attention_mask

        def forward(self, input_ids, attention_mask=None):
            kwargs = {}
            if "input_ids" in self._allowed:
                kwargs["input_ids"] = input_ids
            if (
                self._include_attention_mask
                and attention_mask is not None
                and "attention_mask" in self._allowed
            ):
                kwargs["attention_mask"] = attention_mask
            out = self.inner(**kwargs)
            if hasattr(out, "last_hidden_state"):
                return out.last_hidden_state
            if isinstance(out, (tuple, list)) and len(out) > 0:
                return out[0]
            return out

    output.parent.mkdir(parents=True, exist_ok=True)

    def _do_export(include_attention_mask: bool) -> None:
        wrapper = _OnnxWrapper(model, include_attention_mask=include_attention_mask).eval()
        input_names = ["input_ids"]
        dynamic_axes = {
            "input_ids": {0: "batch", 1: "seq"},
            "audio": {0: "batch", 1: "time"},
        }
        export_args = (input_ids,)
        if include_attention_mask:
            export_args = (input_ids, attention_mask)
            input_names.append("attention_mask")
            dynamic_axes["attention_mask"] = {0: "batch", 1: "seq"}
        print(
            f"Exporting ONNX to: {output} "
            f"(include_attention_mask={include_attention_mask})"
        )
        torch.onnx.export(
            wrapper,
            export_args,
            str(output),
            input_names=input_names,
            output_names=["audio"],
            dynamic_axes=dynamic_axes,
            opset_version=opset,
            do_constant_folding=True,
        )

    try:
        _do_export(include_attention_mask=True)
    except Exception as exc:  # noqa: BLE001
        print(f"Primary export path failed: {exc}")
        print("Retrying export without attention_mask to bypass tracing issue...")
        _do_export(include_attention_mask=False)

    print("Validating with ONNX Runtime...")
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    ort_inputs = {"input_ids": input_ids.detach().cpu().numpy().astype(np.int64)}
    if any(inp.name == "attention_mask" for inp in sess.get_inputs()):
        ort_inputs["attention_mask"] = (
            attention_mask.detach().cpu().numpy().astype(np.int64)
        )
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
