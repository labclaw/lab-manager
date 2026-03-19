"""Multi-model consensus merge and cross-model review."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from lab_manager.intake.providers import VLMProvider

log = logging.getLogger(__name__)

MODEL_PRIORITY = [
    "opus_4_6",
    "gemini_3_1_pro",
    "gpt_5_4",
    "gemini_pro",
    "gemini",
    "codex",
    "opus",
]


def extract_parallel(
    providers: list[VLMProvider],
    image_path: str,
    prompt: str,
) -> dict[str, Optional[dict]]:
    """Run all providers in parallel, return {name: parsed_json}."""
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(providers), 5)) as executor:
        futures = {
            executor.submit(provider.extract, image_path, prompt): provider
            for provider in providers
        }
        for future in as_completed(futures):
            provider = futures[future]
            try:
                results[provider.name] = future.result(timeout=180)
            except TimeoutError:
                log.warning("%s timed out after 180s", provider.name)
                results[provider.name] = None
            except Exception as e:
                log.warning("%s failed: %s", provider.name, e)
                results[provider.name] = None
    return results


def consensus_merge(extractions: dict[str, Optional[dict]]) -> dict:
    """Merge extractions using consensus voting.

    - 3/3 agree → unanimous (auto-resolve)
    - 2/3 agree → majority wins (auto-resolve)
    - all disagree → flag for human
    """
    valid = {k: v for k, v in extractions.items() if v is not None}
    if not valid:
        return {"_error": "all_models_failed", "_needs_human": True}

    if len(valid) == 1:
        model, data = next(iter(valid.items()))
        data["_consensus"] = {"method": "single_model", "model": model}
        data["_needs_human"] = True
        return data

    all_fields = set()
    for data in valid.values():
        all_fields.update(data.keys())

    merged = {}
    field_details = {}

    for field in all_fields:
        if field.startswith("_"):
            continue

        values = {model: data.get(field) for model, data in valid.items()}

        # Normalize for comparison
        unique_vals = {}
        for model, val in values.items():
            key = (
                json.dumps(val, sort_keys=True, default=str)
                if val is not None
                else "null"
            )
            unique_vals.setdefault(key, []).append(model)

        if len(unique_vals) == 1:
            merged[field] = next(iter(values.values()))
            field_details[field] = {
                "agreement": "unanimous",
                "models": list(values.keys()),
            }
        else:
            best_key = max(unique_vals, key=lambda k: len(unique_vals[k]))
            best_models = unique_vals[best_key]
            max_count = len(best_models)
            tied_groups = [k for k, v in unique_vals.items() if len(v) == max_count]
            if max_count >= 2 and len(tied_groups) == 1:
                merged[field] = values[best_models[0]]
                field_details[field] = {
                    "agreement": "majority",
                    "winning_models": best_models,
                    "dissenting": {
                        m: values[m] for m in values if m not in best_models
                    },
                }
            elif len(tied_groups) > 1 and max_count >= 2:
                merged[field] = values[best_models[0]]
                field_details[field] = {
                    "agreement": "tied",
                    "tied_groups": {k: unique_vals[k] for k in tied_groups},
                    "needs_human": True,
                    "tied_values": {k: unique_vals[k] for k in tied_groups},
                }
            else:
                for model in sorted(
                    values.keys(),
                    key=lambda m: next(
                        (
                            i
                            for i, p in enumerate(MODEL_PRIORITY)
                            if m == p or m.startswith(p + "_")
                        ),
                        999,
                    ),
                ):
                    if values[model] is not None:
                        merged[field] = values[model]
                        break
                field_details[field] = {
                    "agreement": "none",
                    "all_values": values,
                    "needs_human": True,
                }

    has_conflicts = any(d.get("needs_human") for d in field_details.values())
    merged["_consensus"] = field_details
    merged["_needs_human"] = has_conflicts
    merged["_model_count"] = len(valid)
    return merged


def cross_model_review(
    providers: list[VLMProvider],
    image_path: str,
    merged: dict,
    ocr_text: str = "",
) -> dict:
    """Have each model review the merged extraction. Apply majority corrections."""
    review_data = {k: v for k, v in merged.items() if not k.startswith("_")}
    review_json = json.dumps(review_data, indent=2, default=str)

    prompt = f"""You are reviewing an extraction from a scanned lab document.

OCR text (for reference):
{ocr_text[:2000] if ocr_text else "(none)"}

Current extraction:
{review_json}

Compare EACH field against the OCR text. Output corrected JSON.
Add "review_notes" listing any corrections and why.
Output ONLY valid JSON."""

    reviews = extract_parallel(providers, image_path, prompt)
    valid_reviews = {k: v for k, v in reviews.items() if v is not None}

    if not valid_reviews:
        return merged

    corrected = dict(merged)
    corrections_applied = []

    for field in review_data:
        if field.startswith("_"):
            continue
        corrections = {}
        for model, review in valid_reviews.items():
            if review and field in review:
                key = json.dumps(review[field], sort_keys=True, default=str)
                corrections.setdefault(key, []).append(model)

        if corrections:
            best_key = max(corrections, key=lambda k: len(corrections[k]))
            if len(corrections[best_key]) >= 2:
                new_val = json.loads(best_key)
                old_val = corrected.get(field)
                if json.dumps(new_val, default=str) != json.dumps(old_val, default=str):
                    corrected[field] = new_val
                    corrections_applied.append(field)

    corrected["_review_round"] = {
        "models_reviewed": list(valid_reviews.keys()),
        "corrections_applied": corrections_applied,
    }
    return corrected
