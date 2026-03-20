#!/bin/sh
# Bulk upload all shenlab-docs to the API
# Run inside the app container: docker compose exec app sh /app/scripts/bulk_upload.sh

API_URL="http://localhost:8000/api/v1/documents/upload"
DOCS_DIR="/app/shenlab-docs/resized"
UPLOAD_DELAY="${UPLOAD_DELAY_SECONDS:-10}"
AUTH_HEADER=""

if [ -n "${API_KEY:-}" ]; then
    AUTH_HEADER="-H X-Api-Key:${API_KEY}"
fi

if [ "${AUTH_ENABLED:-true}" = "true" ] && [ -z "${AUTH_HEADER}" ]; then
    echo "[bulk_upload] ERROR: AUTH_ENABLED=true but API_KEY is not set for bulk upload"
    exit 1
fi

TOTAL=$(ls "$DOCS_DIR"/*.jpg 2>/dev/null | wc -l)
COUNT=0
FAIL=0

echo "[bulk_upload] Starting upload of $TOTAL documents..."

for f in "$DOCS_DIR"/*.jpg; do
    COUNT=$((COUNT + 1))
    BASENAME=$(basename "$f")

    if [ -n "${AUTH_HEADER}" ]; then
        RESP=$(curl -s -w "\n%{http_code}" -X POST -H "X-Api-Key: ${API_KEY}" -F "file=@${f}" "$API_URL" 2>&1)
    else
        RESP=$(curl -s -w "\n%{http_code}" -X POST -F "file=@${f}" "$API_URL" 2>&1)
    fi
    HTTP_CODE=$(echo "$RESP" | tail -1)

    if [ "$HTTP_CODE" = "201" ]; then
        DOC_ID=$(echo "$RESP" | head -1 | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null)
        echo "[bulk_upload] ($COUNT/$TOTAL) Uploaded $BASENAME -> doc_id=$DOC_ID"
    else
        FAIL=$((FAIL + 1))
        echo "[bulk_upload] ($COUNT/$TOTAL) FAILED $BASENAME (HTTP $HTTP_CODE)"
    fi

    # Real OCR/VLM extraction is rate-limited. Keep uploads slow enough that
    # background tasks do not stampede the providers.
    sleep "$UPLOAD_DELAY"
done

echo "[bulk_upload] Done. Uploaded: $((COUNT - FAIL))/$TOTAL, Failed: $FAIL"
