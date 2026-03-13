# lab-manager

Private OCR-first foundation for a lab consumables intake and inventory system.

This repo is organized around the first critical problem in the pipeline:

1. New package / packing list / invoice arrives.
2. Staff takes a photo or uploads a scan.
3. OCR extracts usable text from low-quality real-world documents.
4. Backend normalizes fields and archives both image and structured data.
5. Data lands in the inventory database.

The current focus is the OCR benchmark. We are using the lab's own scanned documents, not generic public datasets.

## Repository layout

- `Scan*.pdf`, `Scan*.jpeg`: original benchmark samples from the lab.
- `ocr-benchmark/`: OCR evaluation harness, model adapters, renders, and results.
- `scripts/`: repo bootstrap and sync helpers.
- `docs/`: model research notes and benchmark plan.

## Quality bar

This repo is quality-first. A model only passes if it can reliably recover the fields that matter for operations:

- vendor / supplier
- document type
- order date / invoice date / package date
- shipping and billing blocks
- PO / delivery / sales order / invoice references
- catalog number / item description / lot or batch
- quantity
- handwritten receiving date or note

## Quick start

```bash
cd /Users/robert/workspace/36-labclaw/lab-manager
./scripts/bootstrap_env.sh
python3.12 ocr-benchmark/scripts/render_docs.py
swift ocr-benchmark/scripts/ocr_vision.swift ocr-benchmark/data/renders ocr-benchmark/results/apple_vision.json
python3.12 ocr-benchmark/scripts/run_tesseract.py ocr-benchmark/data/renders ocr-benchmark/results/tesseract.json
python3.12 ocr-benchmark/scripts/evaluate_fields.py ocr-benchmark/data/gold_fields.json ocr-benchmark/results/apple_vision.json
```

## GPU server sync

The repo is prepared to sync to another PC that has a GPU server.

Set:

```bash
export LAB_GPU_HOST=user@gpu-host
export LAB_GPU_PATH=/srv/lab-manager
```

Then run:

```bash
./scripts/sync_gpu_server.sh
```

This uses `rsync` for working tree sync. Git remains the source of truth for version history.
