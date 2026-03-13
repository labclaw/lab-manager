# Professional OCR evaluation report

Date: 2026-03-13

## Objective

Choose the best OCR foundation for a lab consumables intake system using the lab's own scanned paperwork.

## Dataset

Current benchmark set:

- `8` real scanned single-page documents
- vendor packing lists, package summaries, invoices
- low-contrast scans
- structured tables and line items
- handwritten receiving dates on several pages

## Models under consideration

Professional OCR candidates:

- `Mistral OCR 3`
- `DeepSeek-OCR-2`
- `PaddleOCR-VL-1.5`
- `PP-OCRv5`
- `Google Document AI Enterprise OCR`
- `Azure Document Intelligence`
- `AWS Textract`

Local baselines:

- `Apple Vision OCR`
- `Tesseract`

## Actual results so far

Completed local runs:

- `Apple Vision OCR`: `60/60` typed fields, `1/5` handwritten dates, `61/65` overall
- `Tesseract`: `41/60` typed fields, `0/5` handwritten dates, `41/65` overall

Interpretation:

- `Tesseract` is not a viable product OCR foundation for this document class.
- `Apple Vision OCR` is surprisingly strong on typed fields and is a useful local baseline.
- Handwritten receiving dates remain a real failure slice even for the stronger local baseline.
- The next evaluation round should treat handwriting as a first-class gate, not a nice-to-have metric.

## Status by professional model

- `DeepSeek-OCR-2`: runner prepared, but official inference path is CUDA-oriented; formal run should happen on the GPU server.
- `Mistral OCR 3`: not run yet; requires vendor API key.
- `PaddleOCR-VL-1.5`: not run yet; local Mac path still needs to be validated.
- `PP-OCRv5`: not run yet; candidate for lightweight baseline, not likely final winner.
- `Google Document AI Enterprise OCR`: not run yet; requires vendor credentials.
- `Azure Document Intelligence`: not run yet; requires vendor credentials.
- `AWS Textract`: not run yet; requires vendor credentials.

## Official source links

- Mistral OCR 3: <https://mistral.ai/news/mistral-ocr-3>
- DeepSeek-OCR-2 model card: <https://huggingface.co/deepseek-ai/DeepSeek-OCR-2>
- DeepSeek-OCR-2 paper: <https://arxiv.org/abs/2601.20552>
- PaddleOCR main site: <https://www.paddleocr.ai/main/en/index.html>
- PaddleOCR-VL-1.5: <https://www.paddleocr.ai/main/en/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL-1.5.html>
- PP-OCRv5 multilingual docs: <https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html>
- Google Enterprise Document OCR: <https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr>
- Azure Document Intelligence: <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/read>
- AWS Textract: <https://docs.aws.amazon.com/textract/latest/dg/what-is.html>

## Recommended next step

Run the exact same benchmark on the GPU server with:

1. `DeepSeek-OCR-2`
2. `PaddleOCR-VL-1.5`
3. `PP-OCRv5`

Then add vendor API runs for:

1. `Mistral OCR 3`
2. `Google Document AI`
3. `Azure Document Intelligence`
4. `AWS Textract`

The final model decision should be based on the same field-level benchmark, not on public leaderboard claims alone.
