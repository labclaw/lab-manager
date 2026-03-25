# Lab Manager 部署与商业模式分析

> 2026-03-25 | 基于当前代码库 v0.1.8.2 的现状分析

---

## 一、当前架构现状

| 组件 | 技术 | 部署要求 |
|------|------|---------|
| 后端 | FastAPI + SQLModel | Python 3.12+ |
| 数据库 | PostgreSQL 17 | 有状态，需持久卷 |
| 搜索 | Meilisearch v1.12 | 有状态，需持久卷 |
| 前端 | React 19 + Vite 8 | 构建后嵌入后端静态文件 |
| 反向代理 | Caddy | 自动 HTTPS |
| AI | Gemini / Claude / GPT API | 用户自带 API Key |
| 认证 | Session Cookie + API Key | 单租户 |

**关键特征**：单租户、单实例、Docker Compose 全包、Apache 2.0 开源。

---

## 二、三种路线对比

### 路线 A：纯开源 + 自托管

用户 `git clone` 或 `docker compose up` 自己跑。

**优势**：
- 已经基本就绪（`deploy/install.sh`、DigitalOcean 一键脚本）
- Apache 2.0 许可证友好，允许商业使用
- 实验室数据敏感，自托管是很多用户的刚需
- 社区贡献可以反哺产品

**劣势**：
- 没有直接收入
- 用户需要自己维护服务器、数据库备份、升级
- 小实验室可能没有 DevOps 能力
- 支持成本可能很高（GitHub Issues 变成免费技术支持）

**适合**：大学实验室、有 IT 团队的企业、注重数据隐私的机构。

---

### 路线 B：一键部署（托管基础设施，用户独占实例）

用户点一个按钮，在云上自动创建一个独占的实例。

#### 实现方案

| 平台 | 方式 | 预估月费 | 复杂度 |
|------|------|---------|--------|
| DigitalOcean | 已有 `create-droplet.sh`，可做成 1-Click App | $24/mo (4GB) | 低 |
| Railway / Render | `railway.json` / `render.yaml` 模板 | $15-30/mo | 低 |
| Coolify / CapRover | 自托管 PaaS + 模板 | 用户自己的机器 | 中 |
| AWS Marketplace | AMI + CloudFormation | $30-50/mo | 高 |

#### 最快落地：DigitalOcean 1-Click App

已有 `deploy/digitalocean/cloud-init.yml`，只需：

1. 提交到 DigitalOcean Marketplace（审核约 2 周）
2. 用户一键创建 Droplet，自动初始化
3. 首次访问走 `/api/v1/setup/complete` 创建管理员

**无需改代码**，当前架构完全适配。

#### 进阶：Railway / Render 一键模板

添加 `railway.json` 或 `render.yaml`：
- 自动配置 PostgreSQL 插件
- 环境变量预填
- 用户只需 Fork → Deploy → 设置密码

**需要的改动**：
- Meilisearch 改为可选（Railway 上没有原生插件，需 sidecar 或降级为 PostgreSQL `tsvector`）
- 或者接受 Meilisearch 作为外部服务（Meilisearch Cloud 有免费层）

---

### 路线 C：SaaS（多租户，免费使用）

你运营基础设施，用户注册即用。

#### C1：免费 + 付费增值（Freemium）

| | 免费层 | Pro | Enterprise |
|---|--------|-----|-----------|
| 价格 | $0 | $29-49/mo | 联系销售 |
| 物料数量 | 100 | 无限 | 无限 |
| 文档扫描/月 | 20 | 500 | 无限 |
| AI 提取 | 基础 (单模型) | 多模型共识 | 自定义模型 |
| 用户数 | 2 | 10 | 无限 |
| 数据导出 | CSV | CSV + API | 全量 API |
| 存储 | 1 GB | 20 GB | 自定义 |
| 支持 | 社区 | 邮件 | 专属 |

#### C2：完全免费（靠其他方式变现）

| 变现方式 | 可行性 | 风险 |
|---------|--------|------|
| AI API 调用抽成（用户自带 Key，我们抽手续费） | 低 — 用户直接调 API 更便宜 | 用户绕过 |
| 耗材/试剂供应商广告/推荐 | 中 — 实验室采购是真实需求 | 影响用户信任 |
| 数据分析报告付费 | 中 — 采购趋势、成本优化 | 需要足够用户量 |
| 完全开源 + 赞助/捐赠 | 低 — 除非巨大社区 | 不可预测 |

#### SaaS 需要的架构改造

这是**最重要的部分**——当前代码**不支持多租户**，改造工作量大：

| 改造项 | 工作量 | 说明 |
|--------|--------|------|
| **多租户隔离** | 🔴 大 | 每个表加 `tenant_id`，所有查询加过滤，或 schema-per-tenant |
| **用户注册/登录** | 🟡 中 | 当前只有 Staff 模型 + session，需要加 OAuth / Magic Link |
| **计费系统** | 🟡 中 | Stripe 集成、用量追踪、配额限制 |
| **租户管理后台** | 🟡 中 | 租户 CRUD、用量仪表板、计费管理 |
| **数据隔离验证** | 🔴 大 | 安全审计，确保租户间完全隔离 |
| **横向扩展** | 🟡 中 | 无状态应用 + 连接池 + 文件存储改 S3 |
| **AI API Key 管理** | 🟢 小 | 租户自带 Key 或平台统一 Key + 计费 |
| **备份/恢复** | 🟡 中 | 按租户备份、数据导出 |

**预估工期**：2-3 个月（1-2 人全职），才能达到生产级多租户。

---

## 三、推荐策略：分阶段演进

### 阶段 1（现在 → 1 个月）：开源 + 一键部署

**做什么**：
1. ✅ 已有：Docker Compose、install.sh、DigitalOcean 脚本
2. 添加 Railway / Render 一键部署模板
3. 提交 DigitalOcean Marketplace
4. 完善文档（README 中文版、部署视频）
5. GitHub Release 自动发布 Docker 镜像（✅ 已有 workflow）

**不改架构**，只补部署入口。低成本获取早期用户和反馈。

### 阶段 2（1-3 个月）：验证需求

**做什么**：
1. 收集用户反馈：自托管 vs 托管需求比例
2. 统计 Docker 拉取量、GitHub Stars
3. 跑一个 **托管 Demo 实例**（只读，展示功能）
4. 如果有付费意愿信号 → 进入阶段 3

**关键指标**：
- GitHub Stars > 500 → 社区有兴趣
- 有 > 10 个用户要求 "我不想自己部署" → SaaS 有需求
- 有用户愿意付费 → Freemium 可行

### 阶段 3（3-6 个月）：按需选择

**如果自托管用户多** → 做 Coolify/CapRover 模板 + 付费支持计划

**如果 SaaS 需求明确** → 最小多租户改造：
1. Schema-per-tenant（PostgreSQL schema 隔离，改动最小）
2. 注册 + Stripe 集成
3. 先邀请制内测 10 个实验室

---

## 四、架构改造优先级（如果走 SaaS）

### 最小可行 SaaS：Schema-per-tenant

当前单租户架构改造为多租户，**最安全的路径**是 schema-per-tenant：

```
PostgreSQL
├── public schema          → 租户注册表、计费表
├── tenant_abc123 schema   → 该租户的全部业务表
├── tenant_def456 schema   → 另一个租户
└── ...
```

**优势**：
- 每个租户的数据物理隔离（不同 schema）
- 现有查询几乎不用改（只需在连接时 `SET search_path`）
- 备份/删除/迁移按 schema 操作
- 安全审计简单

**劣势**：
- 迁移需要对每个 schema 执行
- 租户数上限约 1000-5000（之后需分库）
- 连接池管理复杂度上升

**需要改的代码**：
1. 请求中间件：从 session 读取 `tenant_id` → `SET search_path TO tenant_xxx`
2. 租户注册流程：创建 schema + 执行 Alembic 迁移
3. `config.py`：添加租户相关配置
4. 文件存储：`uploads/{tenant_id}/` 路径隔离
5. Meilisearch：index 名加 tenant 前缀

### 认证改造

当前：Staff 模型 + session cookie

SaaS 需要：
```
Account（租户） → 多个 User → 对应 Staff（业务角色）
```

推荐：
- 自建认证（已有 bcrypt + session 基础）+ OAuth (Google) 可选
- 或用 Clerk / Auth0 / Supabase Auth 外包认证

---

## 五、成本估算

### 自托管（用户承担）

| 配置 | 月费 | 适合 |
|------|------|------|
| DigitalOcean 4GB | $24 | 小实验室 (1-5 人) |
| DigitalOcean 8GB | $48 | 中型实验室 (5-20 人) |
| 自有服务器 | $0 | 有 IT 团队 |

### SaaS（我们承担）

| 项目 | 10 租户 | 100 租户 | 1000 租户 |
|------|---------|----------|-----------|
| 数据库 (RDS/Supabase) | $25/mo | $100/mo | $500/mo |
| 应用服务器 | $20/mo | $60/mo | $200/mo |
| Meilisearch | $0 (自托管) | $30/mo | $100/mo |
| 文件存储 (S3) | $1/mo | $10/mo | $100/mo |
| AI API 调用 | 用户自带 | 用户自带 | 混合 |
| **总计** | **~$46/mo** | **~$200/mo** | **~$900/mo** |

Freemium 盈亏平衡点：约 10 个 Pro ($29) 用户 = $290/mo 覆盖 100 租户基础设施。

---

## 六、结论与建议

| 维度 | 建议 |
|------|------|
| **短期** | 纯开源 + 一键部署，零成本获取用户 |
| **中期** | 根据数据决定是否做 SaaS |
| **架构** | 如果做 SaaS，用 schema-per-tenant，改动最小 |
| **变现** | Freemium 最直观，免费层够用但有限制 |
| **风险** | 不要过早投入多租户改造，先验证需求 |
| **最大杠杆** | AI 文档提取是差异化功能，围绕它设计付费点 |

**一句话**：先把开源社区做起来，用户数据会告诉你该不该做 SaaS。
