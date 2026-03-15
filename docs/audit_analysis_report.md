# LabClaw Pipeline Audit Report / 全流程审计报告

**Generated**: 2026-03-14
**Lab**: MGH Shen Lab (神经科学)
**Documents**: 279 scanned lab supply documents

## Pipeline Architecture / 流程架构

```
Raw Scan (279 images)
  → Stage 1: Qwen3-VL-4B OCR (local GPU, RTX 5090)
  → Stage 2: Gemini 2.5 Flash structured extraction (Instructor + Pydantic)
  → Stage 3: Auto-approve (confidence >= 0.95) or → Review Queue
  → Stage 4: Opus 4.6 visual verification (279/279 complete)
  → Stage 5: Audit log generation
```

## Overall Results / 总体结果

| Metric | Count | Rate |
|--------|-------|------|
| Total documents | 279 | 100% |
| Correct (no errors) | 149 | 53.4% |
| Minor errors only | 52 | 18.6% |
| **Critical errors** | **78** | **28.0%** |

### Auto-approval vs Actual Accuracy / 自动审批 vs 实际准确率

| Status | Count | Actual Critical Errors | False Positive Rate |
|--------|-------|----------------------|---------------------|
| Auto-approved (conf >= 0.95) | 211 | 52 | **24.6%** |
| Sent to review (conf < 0.95) | 67 | 26 | — |
| Empty | 1 | 0 | — |

**关键发现**: 211个自动批准的文档中，有52个(24.6%)存在严重错误。置信度校准严重不足。

## Confidence Calibration / 置信度校准分析

| Confidence Range | Total | Correct | Critical | Accuracy |
|-----------------|-------|---------|----------|----------|
| 0.95-1.0 | 211 | 121 | 52 | 57.3% |
| 0.9-0.95 | 52 | 24 | 18 | 46.2% |
| 0.8-0.9 | 5 | 1 | 3 | 20.0% |
| 0.7-0.8 | 4 | 0 | 2 | 0.0% |
| 0.5-0.7 | 2 | 0 | 1 | 0.0% |
| 0.0-0.5 | 4 | 2 | 2 | 50.0% |

**问题**: 高置信度(0.95-1.0)文档的实际准确率只有57.3%，说明LLM的自我评估不可靠。

## Error Categories / 错误分类 (Top 10)

| Category | Docs Affected | Description |
|----------|--------------|-------------|
| document_type_misclassification | 41 | COA→packing_list, shipping label→package |
| order_number_error | 33 | PO number digits wrong, confused with tracking# |
| vendor_identification_error | 30 | Address as vendor, typos, wrong company |
| lot_batch_confusion | 20 | VCAT codes as lot#, dates as lot#, batch/lot swap |
| reference_number_error | 17 | Delivery#/invoice# confused or wrong |
| date_interpretation_error | 14 | Handwritten dates, format confusion |
| quantity_error | 14 | 0 quantity, wrong units (1000 vs 1) |
| description_error | 12 | Truncated, DNA sequences mangled |
| items_extraction_error | 8 | Empty items array, duplicate items |
| catalog_number_error | 7 | Extra spaces, wrong codes |

## Deep Analysis: Root Causes / 深度分析：根因

### 1. Document Type Misclassification (41 docs, 14.7%)

**根因**: OCR文本缺乏视觉布局信息。Gemini只看文本，不看图片。

- COA (Certificate of Analysis) 被误分为 packing_list 或 invoice
- Shipping labels 被分为 "package"（不是有效类型）
- MTA (Material Transfer Agreement) 完全无法识别

**修复方案**:
- 将文档分类作为独立步骤，先分类再提取
- 增加 COA、MTA、shipping_label 为有效文档类型
- 对分类使用视觉模型而非纯文本

### 2. PO/Order Number Errors (33 docs, 11.8%)

**根因**: 多个数字字段在同一文档中出现，LLM混淆了PO number、order number、tracking number。

- PO-108037796 vs PO-10803796（多了一位数字）
- Tracking number 被提取为 PO number
- 有时PO number字段为空但文档中有明确的PO

**修复方案**:
- 每个供应商有固定的PO格式 → 用正则验证
- 增加交叉验证：PO number格式 vs vendor已知格式

### 3. Vendor Name Issues (30 docs, 10.8%)

**根因**: OCR文本中有多个公司名（发件人、收件人、代理商），LLM无法区分。

- 地址被提取为vendor name: "529 N. Baldwin Park Blvd, City of Industry, CA 91746"
- 模板文字被提取: "PROVIDER: Organization providing the ORIGINAL MATERIAL"
- 大小写/拼写不一致: "Milttenyi" vs "Miltenyi", "xife technologies" vs "Life Technologies"
- 错误的公司: "DC Dental" 实际是 "Supply Clinic"

**修复方案**:
- 维护已知vendor别名列表
- 提取后与vendor DB做fuzzy match验证
- 如果vendor name不在已知列表中，标记为needs_review

### 4. Lot/Batch Number Confusion (20 docs, 7.2%)

**根因**: 实验室文档中有大量编号（VCAT、REF、LOT、BATCH、catalog），OCR文本中无明确标签。

- VCAT codes (e.g., "VCAT: RGF-3050") 被提取为 lot number
- 日期 "2026. 35" 被提取为 lot number
- Batch和lot互换

**修复方案**:
- 定义每种编号的格式规则
- VCAT codes 应该是reference，不是lot number
- 纯数字日期格式 → 不应是lot number

### 5. Quantity Errors (14 docs, 5.0%)

**根因**: 单位和数量解析混乱。

- "1000 µL" 被解析为 quantity=1000（实际是1 x 1000µL）
- Quantity=0 明显是错误
- 单位丢失

### 6. DNA Sequence / Primer Issues

**特殊问题**: Shen Lab订购了大量DNA primers，序列在OCR后容易出错。

- 碱基丢失或多出: "GGGGTTGCGCTCGTTGC" 可能不完整
- 引物名与序列混在一起

## Document Type Accuracy / 文档类型准确率

| Type | Total | Correct | Critical | Accuracy |
|------|-------|---------|----------|----------|
| packing_list | 236 | 134 | 58 | 56.8% |
| invoice | 17 | 8 | 6 | 47.1% |
| package | 15 | 3 | 9 | 20.0% |
| shipping_label | 4 | 1 | 2 | 25.0% |

**注意**: "package" 不应该是一个文档类型 — 这些大部分是被错误分类的COA或shipping label。

## Recommendations for Scaling to More Labs / 扩展到更多实验室的建议

### Immediate Fixes (本轮必须修复)

1. **降低自动批准阈值** → 0.98 或完全取消自动批准，全部送review queue
2. **增加文档类型** → COA, MTA, shipping_label, quote, receipt
3. **PO格式验证** → 正则表达式 per vendor
4. **Vendor名称规范化** → fuzzy matching + alias DB

### Architecture Changes (架构改进)

1. **Two-stage extraction**: 先分类文档类型，再按类型提取字段
2. **Visual classification**: 用视觉模型(而不是纯文本)做文档分类
3. **Cross-field validation**: 提取后自动验证字段一致性
4. **Vendor-specific templates**: 已知供应商用定制提取模板

### For New Labs (新实验室接入)

1. 先跑小批量(50张)建立baseline accuracy
2. 根据该lab的供应商列表定制vendor DB
3. 全部送human review，直到accuracy > 90%
4. 记录每种错误的修复方法，建立knowledge base
5. 逐步放宽auto-approve阈值

## Files / 生成的文件

| File | Description |
|------|-------------|
| `docs/audit_log.json` | Full per-document audit trace (279 entries, 7 stages each) |
| `docs/audit_summary.json` | Aggregate statistics and error patterns |
| `docs/audit_analysis_report.md` | This report |
| `/tmp/review_batch_0-7.json` | Opus 4.6 raw review results |
