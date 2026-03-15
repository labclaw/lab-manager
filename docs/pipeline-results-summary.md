# Lab-Manager Pipeline 全流程分析报告

**生成时间**: 2026-03-14
**数据来源**: MGH Shen Lab 扫描文档 OCR + 结构化提取 + PostgreSQL 数据库
**OCR 模型**: Qwen/Qwen3-VL-4B-Instruct

---

## 一、实验室概况

基于 279 份采购文档的分析，这是 **Massachusetts General Hospital (MGH) 的 Shen Lab**（PI: Shiqian Shen），隶属于麻醉科 (Anesthesia Department)，位于 Charlestown Navy Yard 149 号楼 6501E 室。

这是一个典型的**神经科学 + 神经免疫学实验室**，研究方向涵盖：

1. **神经环路操控与光遗传学**：大量采购 AAV 病毒载体（DIO-FLEX 系统）、光遗传工具（eOPN3）、GRIN 透镜（Thorlabs）、Neuropixels 探头（IMEC）
2. **神经炎症与 cGAS-STING 通路**：采购 STING 抑制剂 H-151、cGAS/STING/IRF-3 抗体、大量 STING/cGAS/Ifnb/Tnf/Il6 等炎症因子的 qPCR 引物
3. **小胶质细胞 (Microglia) 研究**：Anti-Iba1 抗体、TMEM119 抗体、CD68 抗体、CSF1R 抑制剂 Pexidartinib (PLX3397)
4. **线粒体功能研究**：mito-EGFP 病毒载体、NDUFA-mCherry 构建体、Tom20 抗体
5. **肠脑轴 / 微生物组研究**：QIAamp PowerFecal Pro DNA Kit、16S rRNA 引物、E. coli Nissle 1917、吲哚硫酸钾 (Indoxyl sulfate)
6. **小鼠在体实验**：立体定位注射设备（Harvard Apparatus）、灌胃针、Meloxicam 镇痛药、MetaBond 牙科水泥、脑切片模具、isoflurane 相关耗材

---

## 二、数据库总体统计

| 指标 | 数值 |
|------|------|
| 总文档数 | 279 |
| 总提取物品条目数 | 400 |
| 独立 PO 编号数 | 206 |
| 独立供应商数（原始） | 122 |
| 去重后实际供应商数 | ~80（同一供应商存在多种名称变体） |
| 状态: approved | 211 (75.6%) |
| 状态: needs_review | 67 (24.0%) |
| 状态: empty | 1 (0.4%) |

---

## 三、供应商分析

### 主要供应商（合并同名变体后排序）

| 排名 | 供应商 | 文档数 | 名称变体 | 主要产品类别 |
|------|--------|--------|----------|-------------|
| 1 | **Sigma-Aldrich / MilliporeSigma** | ~52 | Sigma-Aldrich, Sigma-Aldrich Inc., SIGMA-ALDRICH, EMD Millipore Corporation, Millipore Sigma, MilliporeSigma Corporation, EMD MILLIPORE CORPORATION | 化学试剂、抗体、过滤器材 |
| 2 | **Bio-Rad Laboratories** | ~15 | Bio-Rad Laboratories Inc., BIO-RAD | 电泳试剂盒(TGX FastCast)、封闭液(EveryBlot) |
| 3 | **Thermo Fisher / Fisher Scientific / Invitrogen / Life Technologies** | ~14 | FISHER SCIENTIFIC CO, Fisher Scientific, ThermoFisher SCIENTIFIC, Thermo Fisher SCIENTIFIC, invitrogen, Life Technologies Corporation, THERMO FISHER SCIENTIFIC CHEMICALS INC. | PCR 耗材、引物定制、细胞培养 |
| 4 | **MedChemExpress (MCE)** | ~9 | MedChem Express, MedChemExpress LLC, MEDCHEMEEXPRESS LLC | qPCR Master Mix (SYBR Green)、H-151、Pexidartinib |
| 5 | **abcam** | 8 | abcam | 抗体 (Iba1, GSDMD, GSDME, GLP-1R, GRIM19, TIMP3) |
| 6 | **BioLegend** | 7 | BioLegend Inc | 流式抗体 (CD45, PD-1, CD68, CD9)、功能抗体 |
| 7 | **GOLDBIO** | ~7 | GOLDBIO, GOLD BIO | DNA Ladder、qPCR Master Mix、D-Luciferin |
| 8 | **Cell Signaling Technology (CST)** | 6 | Cell Signaling TECHNOLOGY | 信号通路抗体 (cGAS, STING, IRF-3, Tom20) |
| 9 | **Genesee Scientific** | ~8 | Genesee Scientific, Genesee Scientific LLC | PCR 管、手套、实验耗材 |
| 10 | **Addgene** | 6 | addgene | AAV 质粒/病毒 (GCaMP6f, hM4D(Gi), FLEX-DTR, SaCas9) |
| 11 | **Staples** | ~6 | Staples, Staples™ | 办公用品 |
| 12 | **WESTNET** | ~7 | WESTNET inc., WESTNET | Corning 产品分销 (冻存管、细胞滤器) |
| 13 | **Miltenyi Biotec** | ~5 | Milttenyi Biotec, Miltenyi Biotec | 磁珠分选柱 (Myelin Removal, LS+ Column) |
| 14 | **McMaster-Carr** | 3 | McMASTER-CARR | 机器视觉灯光、工程配件 |
| 15 | **Thorlabs** | 3 | THORLABS Inc. | GRIN 透镜 (2P 成像) |

### 其他值得注意的供应商

- **PackGene** / **Biohippo** / **Alta Biotech** / **ALSTEM**: AAV 病毒定制生产
- **IMEC**: Neuropixels 多电极探针
- **Nikon**: 显微镜完美对焦电机鼻轮
- **Brain Research Laboratories**: 切片存储盒
- **Harvard Apparatus**: 立体定位/手术设备
- **Patterson Dental / Veterinary**: MetaBond 牙科水泥、Meloxicam 镇痛
- **Digikey / Newark**: 电子元件 (Nano 连接器)
- **B&H Photo**: 7Artisans 自动对焦适配器
- **RealSense**: Intel 深度相机 D415

---

## 四、采购物品分类

### 4.1 抗体 (32 条记录)

**神经标记物**:
- Parvalbumin (MAB1572) — EMD Millipore
- GAD67 (MAB5406) — EMD Millipore
- Anti-VGluT2 (AB2251-I) — EMD Millipore
- Anti-Iba1 (AB5076, AB178846) — abcam
- TMEM119 (98778S) — CST
- Anti-GABA (A2052) — Sigma
- Aggrecan (AB1031) — EMD Millipore
- Anti-Syntrophin (845102) — BioLegend
- Anti-LAMP1 (L1418) — Sigma

**炎症/免疫通路**:
- cGAS (79978S), STING (MABF270), IRF-3 (11904S), Phospho-STING (72971S) — CST/Millipore
- GSDMD (AB215203), GSDME (AB215191) — abcam (炎性小体/焦亡相关)
- CD45-PE/Cy7, PD-1 Ultra-LEAF, CD68 — BioLegend
- Phospho-H2A.X (80312S) — CST (DNA 损伤标记)

**其他**:
- β-Actin (AC004) — ABclonal (内参)
- Tom20 (42406S) — CST (线粒体标记)
- GLP-1R (AB218532) — abcam
- TIMP-3 (10858-1-AP, AB39184) — Proteintech/abcam
- GRIM19 (AB110240) — abcam (线粒体复合体 I)

### 4.2 病毒载体与质粒 (18 条记录)

- **Cre 依赖系统 (DIO/FLEX)**: 多个 AAV-DIO/FLEX 构建体
- **光遗传工具**: eOPN3-mScarlet (Viral Vector Facility, Zurich)
- **DREADD**: hM4D(Gi)-mCherry (Addgene #50477, AAV8)
- **钙成像**: GCaMP6f (Addgene #100834, AAV9)
- **CRISPR**: SaCas9 系统 (Addgene #159914, #124844)
- **线粒体标记**: mito-EGFP (Biohippo), NDUFA-mCherry (PackGene)
- **白喉毒素受体**: FLEX-DTR-GFP (Addgene #124364, 用于细胞消融)
- **AAV capsid 工程**: iCAP-AAV9-X1.1 (Addgene #196836), kiCAP-AAV-BI30 (Addgene #183749)

### 4.3 分子生物学试剂

- **qPCR**: SYBR Green Master Mix (MCE HY-K0501, 5 份), PowerUp SYBR (Thermo A25742), Goof-Proof qPCR (GoldBio), Lambda qMX-Green
- **定制引物 (Invitrogen)**: STING, cGAS, TBK1, Ifnb, Tnf, Il6, Nos2, Ccl2, Ccl5, Cxcl9, Cxcl10, Ifi44, Actb, 16S rRNA — 明确指向 **cGAS-STING 通路和神经炎症** 研究
- **DNA/凝胶**: DNA Ladder (GoldBio), TGX FastCast 凝胶 (Bio-Rad, 多次采购), APS
- **DNA 提取**: QIAamp PowerFecal Pro DNA Kit (Qiagen) — 粪便微生物组
- **DNA 聚合酶**: PrimeSTAR Max (Takara)
- **ROX 参考染料**: Life Technologies

### 4.4 药理学化合物

| 化合物 | 目录号 | 供应商 | 靶点 |
|--------|--------|--------|------|
| MCC950 sodium | T6887 | TargetMol | NLRP3 炎性小体抑制剂 |
| H-151 | HY-112693 | MCE | STING 抑制剂 |
| Pexidartinib (PLX3397) | HY-16749 | MCE | CSF1R 抑制剂 (小胶质细胞清除) |
| Compound 21 | HB4888 | C21 | DREADD 配体 |
| CNQX | C239 | Sigma | AMPA/Kainate 受体拮抗剂 |
| D-Luciferin | LUCNA-100 | GoldBio | 生物发光底物 |
| Protease Inhibitor Cocktail | 11836170001 | Sigma | 蛋白酶抑制 |

### 4.5 设备与硬件

- **神经记录**: Neuropixels 2.0 多通道探针 NP2013 (IMEC)
- **光学/成像**: Nikon Perfect Focus 电机鼻轮, GRIN 透镜 (Thorlabs), 7Artisans 镜头适配器
- **深度相机**: Intel RealSense D415
- **计算**: Intel Core 14th Gen Creator PC
- **存储**: Seagate One Touch 2TB 外置硬盘 (x2)
- **机器视觉**: McMaster-Carr 红色 LED 光源、180 度旋转支架
- **手术工具**: 灌胃针 (GavageNeedle.Com), 33G 注射针 (Air-Tite), 50mL 注射器 (Medline)
- **Nano 连接器**: 36 Position Dual Row Male (DigiKey) — 可能用于电极接口

### 4.6 耗材与一般实验用品

- PCR 管 (Genesee), 冻存管 (Corning/WESTNET), 离心管 (Greiner)
- 手套 (Genesee Scientific Nitrile), 移液器吸头 (Rainin 200ul/1000ul)
- 细胞培养板 (Alkali Scientific), 流式管 (Pluriselect)
- 载玻片储存盒 (Brain Research Labs)
- 切片器脑模具 (Ted Pella, Adult Mouse Coronal)
- 标签纸 (Staples)

### 4.7 化学试剂

- NaCl, NaH2PO4, MgSO4, NaHCO3, Na Pyruvate (基础缓冲液配制)
- HEPES, EGTA, PEG 400, Sucrose (超纯)
- HCl (37%), Ethanol (140 Proof & 200 Proof)
- Thiodiethylene Glycol, Luminol Sodium Salt
- APS (Ammonium Persulfate — 凝胶聚合)
- 3-Indoxyl Sulfate Potassium (x2) — 肠脑轴代谢物
- PMSF (Phenylmethanesulfonyl Fluoride) — 蛋白酶抑制剂
- Apramycin Sulfate — 抗生素选择标记

### 4.8 细胞培养

- DMEM (Fisher), FBS (GeminiBio), BSA (Boston BioProducts)
- CellBanker 1 冻存液 (Iwai)
- Cell Culture Freezing Medium (CellBiologics)
- 0.22um Vacuum Filtration System (Corning/Sigma)
- SURE 2 Supercompetent Cells (Agilent)
- E. coli Nissle 1917 (ATCC) — 益生菌菌株
- Cell Strainer 70um (Falcon)

---

## 五、时间范围与采购模式

### 订单日期范围

- **最早日期**: 2023-08（部分旧文档，有一条 2007-08 应为 OCR 误读）
- **最新日期**: 2026-03-04
- **主要覆盖范围**: 2024-01 至 2026-03（约 2 年）

### 月度采购量分布

| 时段 | 文档数 | 备注 |
|------|--------|------|
| 2023-08 ~ 2023-12 | 6 | 早期少量 |
| 2024-01 ~ 2024-06 | 36 | 启动期，6 月高峰 (18) |
| 2024-07 ~ 2024-12 | 51 | 稳定期，9/11 月高峰 |
| 2025-01 ~ 2025-06 | 34 | 持续采购 |
| 2025-07 ~ 2025-12 | 44 | 10 月高峰 (16) |
| 2026-01 ~ 2026-03 | 16 | 最近 3 个月 |

**特征**: 采购量在 2024 年中期后显著上升，提示实验室处于活跃研究阶段。秋季（9-11 月）和年初通常采购较多，可能与 grant cycle 和学期节奏相关。

### 收货人员

| 收货人 | 签收次数 | 备注 |
|--------|----------|------|
| Yuting (Gao) | 16+ | 主要收货人，也是引物定制的主要研究者 |
| (Weihua) Ding | 9+ | |
| Pei Wang | 6+ | 也有 16S rRNA 引物订单 |
| Wei (Wang) | 5+ | |
| Yung | 3 | |
| 其他 | 若干 | Ying, Kuang, Luna, Song Huang, Liuyue Yang 等 |

---

## 六、置信度与质量评估

### 提取置信度分布

| 置信度区间 | 文档数 | 占比 |
|-----------|--------|------|
| >= 0.9 (高) | 263 | 94.3% |
| 0.7 - 0.9 (中) | 9 | 3.2% |
| 0.5 - 0.7 (低) | 2 | 0.7% |
| < 0.5 (极低) | 5 | 1.8% |

**统计指标**:
- 平均置信度: 0.954
- 标准差: 0.134
- 中位数: 1.0（大多数文档为满分）

### 整体评价

**OCR 层 (Qwen3-VL-4B)**:
- 对标准打印的 packing list 效果优秀
- 对手写签名/日期的识别率较低（收货人名经常出现变体：如 "Wang Pei!" "wangpei" "Pei wang" "Wang Pei"）
- 部分 FedEx 标签、法律文件等非标准格式识别困难

**结构化提取层**:
- 94.3% 的文档获得高置信度 (>=0.9)，说明 LLM 结构化提取整体效果好
- 供应商名称标准化是最大挑战：同一供应商有 3-8 种名称变体（如 Sigma-Aldrich 有 8 种变体）
- PO 编号提取准确率高（206 个独立 PO）
- 日期解析基本准确，但有 1 条异常值 (2007-08-24)，可能是 OCR 误读或实际旧文档

---

## 七、需人工审核的 67 份文档分析

### 按置信度分层

| 置信度 | 数量 | 典型问题 |
|--------|------|----------|
| 0.0 | 4 | 非标准文档（MTA 法律协议、大学寄送单、空白页、OCR 完全失败） |
| 0.5 | 2 | 供应商识别失败（A-M Systems、UNKNOWN） |
| 0.7 | 4 | 部分信息缺失（Greiner、Sigma、A-M Systems、Nikon） |
| 0.8 | 5 | 供应商未识别（none, null, [VENDOR NAME NOT FOUND]）或信息不完整 |
| 0.9 | 52 | 高置信度但仍标记为 needs_review |

### 0.9 置信度文档仍需审核的原因分析

这 52 份文档是最值得关注的部分——它们的置信度接近满分但仍被标记为 needs_review。通过分析具体案例：

1. **供应商名称不规范** (约 15 份):
   - `null` 作为供应商名 (3 份)
   - 供应商名为标签名而非公司名（如 FedEx 标签被识别为 FedEx 供应商）
   - 细微的名称差异触发审核

2. **文档类型判定边界** (约 10 份):
   - invoice vs packing_list 的区分（如 invitrogen 的 invoice x3）
   - shipping_label 被标记审核（FedEx）
   - document_type 为 None/null

3. **多页文档的关联** (约 8 份):
   - 同一订单的多个页面（如 packing list + carton list + shipping label）
   - 不同格式的同一供应商文档

4. **缺少关键字段** (约 10 份):
   - 无 PO 编号（如 Boston BioProducts 的包裹标签、GoldBio 的某份 packing list）
   - 无日期信息
   - 无收货确认

5. **特殊文档类型** (约 9 份):
   - IMEC 的 Neuropixels 订单（高价值设备，格式特殊）
   - Viral Vector Facility（学术机构间转运）
   - ATCC 培养物运输
   - CDW/B&H Photo 电子产品

### 0.0 置信度文档（完全失败）

| ID | 文件名 | 原因 |
|----|--------|------|
| 93 | 141807_024.jpg | MTA (Material Transfer Agreement) 文档，非采购单 |
| 94 | 142450.jpg | 法律协议文档 |
| 265 | 153916_014.jpg | OCR 输出不足以提取任何结构化信息 |
| 272 | 153916_021.jpg | Universite Laval 寄送单，法语文档 |

---

## 八、发现与建议

### 关键发现

1. **研究方向清晰**: Shen Lab 的核心方向是 **cGAS-STING 通路在神经炎症中的作用**，结合小胶质细胞操控（CSF1R 抑制剂）、光遗传学、DREADD 化学遗传学、Neuropixels 电生理记录，以及肠脑轴微生物组研究。

2. **供应商去重是当务之急**: 122 个原始供应商名中，实际独立供应商约 80 个。Sigma-Aldrich/Merck 体系（8 种变体，~52 份文档）占总采购的 18.6%，亟需供应商名称标准化。

3. **Pipeline 整体效果**:
   - 279 份文档中 211 份 (75.6%) 直接 approved
   - 263 份 (94.3%) 高置信度
   - 400 个物品条目被成功提取
   - 这对于一个 4B 参数的本地 VLM 来说是相当好的结果

4. **手写识别薄弱**: 收货人签名产生 29 种变体（实际约 10 个人），手写日期偶有误读。

5. **非标准文档处理**: MTA、法律协议、FedEx 标签等非采购文档共约 6 份，应在前处理阶段过滤。

### 对产品化的建议

1. **供应商标准化模块**: 建立供应商别名库，将 "Sigma-Aldrich" / "SIGMA-ALDRICH" / "Sigma-Aldrich, Inc." 等自动映射到标准名
2. **文档分类前置**: 在 OCR 之前或之后增加文档类型分类器，过滤非采购文档
3. **Human-in-the-loop 重点**: 67 份 needs_review 中，52 份实际是 0.9 置信度，可以进一步细化阈值（如 0.95 以上自动通过），减少人工审核负担
4. **手写 OCR 增强**: 对签名区域单独处理，或提供收货人下拉选择
5. **多页文档关联**: 同一 PO 的多页文档应自动关联为一个逻辑订单

---

## 九、附录：数据质量指标

| 指标 | 值 |
|------|-----|
| OCR 模型平均处理时间 | ~11s / 页 |
| 空白/无效文档 | 1 (0.4%) |
| PO 编号提取率 | 206/279 (73.8%) — 部分文档本身无 PO |
| 供应商名称提取率 | 273/279 (97.8%) — 6 份为 null/none/空 |
| 至少一个物品提取成功 | ~270/279 (96.8%) |
| 批次号 (lot number) 提取率 | ~40% — 许多 packing list 不含批次信息 |
| 收货人提取率 | ~60/279 (21.5%) — 仅手写签收的文档有此信息 |
