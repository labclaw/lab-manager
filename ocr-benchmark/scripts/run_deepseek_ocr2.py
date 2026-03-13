#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("output_json")
    parser.add_argument(
        "--model",
        default="deepseek-ai/DeepSeek-OCR-2",
        help="Hugging Face model id",
    )
    parser.add_argument(
        "--mode",
        choices=["free", "markdown"],
        default="free",
        help="Use raw OCR or document-to-markdown prompt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not torch.cuda.is_available():
        raise SystemExit(
            "DeepSeek-OCR-2 official inference path requires CUDA. Run this script on the GPU server."
        )

    prompt = (
        "<image>\nFree OCR."
        if args.mode == "free"
        else "<image>\n<|grounding|>Convert the document to markdown. "
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        args.model,
        trust_remote_code=True,
        use_safetensors=True,
    ).eval().cuda().to(torch.bfloat16)

    input_dir = Path(args.input_dir)
    output_json = Path(args.output_json)

    docs = []
    with tempfile.TemporaryDirectory(prefix="deepseek-ocr2-") as tmpdir:
        for image_path in sorted(input_dir.iterdir()):
            if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                continue
            print(f"processing {image_path.name}")
            result = model.infer(
                tokenizer,
                prompt=prompt,
                image_file=str(image_path),
                output_path=tmpdir,
                base_size=1024,
                image_size=768,
                crop_mode=True,
                save_results=False,
            )
            docs.append(
                {
                    "file": image_path.name,
                    "fullText": result if isinstance(result, str) else str(result),
                    "lines": [],
                    "model": args.model,
                    "mode": args.mode,
                }
            )

    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=True))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
