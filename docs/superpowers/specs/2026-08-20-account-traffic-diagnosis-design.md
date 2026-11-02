# 账号流量诊断设计（Account Traffic Diagnosis）

> 基于 Pi-Agent 的内容分析能力，回答两个核心问题：
> 1. 我的抖音账号为什么播放量低（自有账号诊断）。
> 2. 对标账号的数据为什么高——他是真爆了，还是粉丝基数（对标账号诊断）。
> 并支持对历史同步数据的分析。

## 1. 目标与非目标

### 目标
- 以「账号管理（`user_info`）」为账号主表锚点，把自有作品、发布记录挂回账号，实现统一账号维度。
- 提供两个诊断能力：自有账号低播放诊断、对标账号「爆款 vs 粉丝基数」判定。
- 诊断结果可存档回看（报告），同时把同一套数据通过 Pi-Agent 工具开放给对话自由提问。

### 非目标（本期不做）
- 不做时间序列快照表（历史趋势留作第二阶段）。
- 不做对标账号与 user_info 的强绑定（对标保持独立实体）。
- 不重构发布/登录链路，只新增诊断与数据关联。

## 2. 关键决策（已确认）

| 决策点 | 结论 |
|---|---|
| 架构方案 | 方案 A：后端预计算统计 + Pi-Agent 解读 |
| 自有数据源 | `publish_records` + `douyin_own_videos` 都纳入 |
| 历史数据 | 现有累计数据集合（不做快照，第二阶段再补） |
| 交互形态 | 独立「诊断」按钮 + 报告页（存档），同时 Pi-Agent 对话可调用同一套工具 |
| 账号归属 | 只有「自有」侧挂 `user_info`；对标账号保持独立 |
| 报告引擎 | 报告按钮走 Hermes 结构化调用（`call_hermes_structured`）；对话走 Pi-Agent agentic 循环 |

## 3. 总体架构与数据流

新增领域模块 `backend_app/modules/account_diagnosis/`：

```
account_diagnosis/
├── stats.py        # 确定性统计（中位数/比值/偏离度/分类），纯 Python
├── schemas.py      # 报告 JSON Schema
├── prompts.py      # 报告提示词
├── repository.py   # diagnosis_reports 表读写 + 自有账号绑定 + 数据读取
├── service.py      # 组装事实卡 → 报告引擎 → 存报告
└── __init__.py
```

### 数据流 1：报告（按钮触发，存档）

```
前端「诊断」按钮
  → POST /account-diagnosis/{target_type}/{target_id}
  → stats.py 读库算统计 → 产出「诊断事实卡」
  → call_hermes_structured（报告 Schema + 事实卡）→ 报告 JSON
  → 存 diagnosis_reports → 返回报告
```

### 数据流 2：对话（Pi-Agent 自由提问）

```
Pi-Agent 对话提问 → LLM 自主调用 get_account_diagnosis_facts 工具
  → 工具回传同一份「诊断事实卡」→ LLM 解读回答（不强制存报告）
```

两条流共用 `stats.py` 与同一份事实卡。数字只在 Python 算一次。

## 4. 数据模型变更

### 4.1 自有侧挂回 user_info（迁移式加列）

```sql
ALTER TABLE douyin_own_accounts ADD COLUMN user_info_id INTEGER;  -- 指向 user_info.id，可空
ALTER TABLE publish_records ADD COLUMN user_info_id INTEGER;      -- 指向 user_info.id，可空
```

- `publish_records`：`account_list` 存的是 `user_info.filePath`，按 filePath 反查回填；读取时兜底解析。
- `douyin_own_accounts`：新增「绑定账号」操作，用户把自有账号绑定到账号管理里的抖音账号（type=3）。

### 4.2 诊断报告表

```sql
CREATE TABLE IF NOT EXISTS diagnosis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,          -- 'own' | 'benchmark'
    target_id INTEGER NOT NULL,         -- user_info.id 或 douyin_benchmark_accounts.id
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | success | failed
    facts_json TEXT,                    -- 事实卡（诊断时快照）
    report_json TEXT,                   -- 报告 JSON
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

## 5. 统计口径（stats.py，确定性计算）

### 5.1 自有账号「为什么播放量低」

对 `target_id`（user_info.id）聚合自有作品 + 发布记录：

- 作品数、播放中位数、播放均值、最高/最低播放作品标题。
- 2s 跳出率中位数、完播率中位数（仅 douyin_own_videos 有）。
- 点赞率 = 赞/播。
- 低播放清单：播放 < 中位数 × 0.5 的作品。
- 四层诊断标签（规则先判，LLM 再解释）：曝光不足 / 前2秒留不住 / 内容留存弱 / 互动转化弱。

### 5.2 对标账号「爆款 vs 粉丝基数」

- 点赞率 `like_rate = like_count / followers_count`。
- 偏离度 `deviation_x = like_count / 账号点赞中位数`。
- 账号点赞中位数/均值/最高。

默认分类阈值（可调）：

| deviation_x | like_rate | 结论 |
|---|---|---|
| ≥ 5x | 任意 | 爆款（显著脱离粉丝基数） |
| 2–5x | 高 | 表现突出（半爆） |
| 0.5–2x | 正常 | 粉丝基数正常发挥 |
| < 0.5x | — | 低于自身基线 |

## 6. 报告 Schema（节选，完整见 schemas.py）

### 6.1 own_account 报告
`summary, traffic_conclusion, diagnosis_layers(4 层判断), key_metrics, low_performing_videos, improvement_actions, confidence`

### 6.2 benchmark_account 报告
`summary, viral_conclusion, per_video_classification, key_metrics, takeaways, confidence`

## 7. 报告引擎与 Pi-Agent 工具

- 报告引擎：复用 `backend_app/agent/structured_runner.py` 的 `call_hermes_structured`。
- Pi-Agent 工具：`get_account_diagnosis_facts(target_type, target_id)` → 返回事实卡。
  - 在 `electron/pi-agent-sidecar.mjs` 中新增 `defineTool`，回传本机后端 `/account-diagnosis/facts/...`。

## 8. 路由

```
POST /account-diagnosis/{target_type}/{target_id}      # 触发报告诊断（同步跑）
GET  /account-diagnosis/reports                        # 报告列表
GET  /account-diagnosis/reports/<id>                   # 报告详情
GET  /account-diagnosis/facts/{target_type}/{target_id} # 事实卡（报告与 Pi-Agent 共用）
POST /own/accounts/bind                                # 自有账号绑定 user_info
GET  /own/accounts                                     # 自有账号列表（含绑定状态）
```

其中 `target_type ∈ {own, benchmark}`；`own` 的 `target_id` 为 `user_info.id`，`benchmark` 的为 `douyin_benchmark_accounts.id`。

## 9. 前端

- 账号管理页：抖音账号行加「诊断」入口（自有诊断）。
- 对标账号页（BenchmarkManagement）：每个对标账号加「诊断」入口（对标诊断）。
- 新增报告展示：诊断结果卡片/弹窗 + 报告列表。
- Pi-Agent 对话（BenchmarkManagement 内）自动获得新工具。

## 10. 错误处理

- 数据不足（无作品/无粉丝数）时，返回可读提示，不抛 500。
- 报告引擎失败时，报告置 `failed` + `error_message`，前端可重试。
- 绑定操作校验目标 user_info 账号存在且 type=3（抖音）。

## 11. 测试

- `tests/test_account_diagnosis.py`：
  - stats 统计口径（中位数、点赞率、偏离度、分类阈值边界）。
  - 绑定与回填逻辑（filePath → user_info.id）。
  - facts/report 的 schema 校验。
  - 数据不足时的降级行为。
