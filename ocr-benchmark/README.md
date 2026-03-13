This folder contains a document OCR benchmark for the scanned lab paperwork in `lab-manager`.

Goals:
- Evaluate OCR quality on the actual incoming documents the lab system will ingest.
- Prefer field recall and usable structured content over generic OCR benchmark scores.
- Keep the benchmark repeatable so new models can be compared on the same samples.

Current adapters:
- `apple_vision`: macOS Vision OCR, no external API key required.
- `tesseract`: local classic OCR baseline.
- `deepseek_ocr2`: planned local adapter for DeepSeek-OCR-2.
- `openai_vision`: planned API adapter using the local `OPENAI_API_KEY`.

Workflow:
1. Render PDFs and images into a normalized image set.
2. Run one or more OCR adapters on the same rendered files.
3. Compare raw OCR output against manually curated expected field strings.
4. Rank models by field recall on business-critical data.

Commands:

```bash
python3.12 scripts/render_docs.py
swift scripts/ocr_vision.swift data/renders results/apple_vision.json
python3.12 scripts/run_tesseract.py data/renders results/tesseract.json
python3.12 scripts/evaluate_fields.py data/gold_fields.json results/apple_vision.json
python3.12 scripts/evaluate_fields.py data/gold_fields.json results/tesseract.json
```
