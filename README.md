# Paperscope — AI Research Hub

> 自动采集、分类、展示 **World Model / Physical AI / Medical AI** 三大领域的最新论文
>
> 数据源：arXiv 预印本 · OpenAlex 期刊 · Semantic Scholar 顶会

---

## 目录

1. [项目结构](#1-项目结构)
2. [两条数据管道](#2-两条数据管道)
3. [精选抓取逻辑详解](#3-精选抓取逻辑详解)
4. [领域分类逻辑](#4-领域分类逻辑)
5. [顶会/顶刊白名单（39 个）](#5-顶会顶刊白名单39-个)
6. [快速开始](#6-快速开始)
7. [日常操作流程](#7-日常操作流程)
8. [添加新 Venue](#8-添加新-venue)
9. [修复旧数据领域标注](#9-修复旧数据领域标注)
10. [GitHub Actions 自动化](#10-github-actions-自动化)
11. [环境变量](#11-环境变量)

---

## 1. 项目结构

```
paperscope/
│
├── fetch_curated_fast.py   ★ 精选论文抓取器（OpenAlex 期刊 + S2 顶会）
├── reclassify_domains.py   ★ 一次性修复旧数据领域标注
├── config.py                  三大领域关键词 + 任务标签定义
│
├── cleaning/                  领域分类 + 任务标注模块
│   ├── __init__.py            check_domains_all / tag_tasks_all / classify_paper_type
│   └── llm_classify.py        LLM 辅助分类（可选）
│
├── backend/                   arXiv 速览数据管道
│   ├── main.py                入口：增量/全量抓取 arXiv
│   ├── scrapers/              arXiv / PubMed / Semantic Scholar 抓取器
│   ├── pipeline/              分类、趋势、周报生成
│   ├── config/                领域配置
│   └── db/                    Supabase 数据库接口
│
├── scripts/
│   ├── sync_curated.py        把 output/papers_curated.json 同步到 frontend/data/
│   └── update_papers.py       把 output/papers.json 同步到 frontend/data/
│
├── frontend/                  静态前端（直接部署，无需构建）
│   ├── index.html
│   ├── assets/css/app.css
│   ├── assets/js/app.js
│   └── data/
│       ├── papers.json             速览数据（arXiv，每日更新）
│       └── papers_curated.json     精选数据（顶会/顶刊，每周更新，已去 abstract）
│
├── output/                    本地中间产物（不提交 git）
│   ├── papers.json
│   └── papers_curated.json    完整版（含 abstract），约 230 MB
│
└── requirements.txt
```

> **说明**：`output/papers_curated.json` 是含 abstract 的完整版（~230 MB），
> `frontend/data/papers_curated.json` 是去掉 abstract 的瘦身版（~88 MB，符合 GitHub 限制）。
> 通过 `scripts/sync_curated.py` 自动完成瘦身和同步。

---

## 2. 两条数据管道

### 速览管道（arXiv 预印本，每日）

```
backend/main.py
  └─ 搜索 arXiv（关键词 + 类别过滤）
  └─ output/papers.json（26,000+ 篇预印本）
      ↓
scripts/update_papers.py
      ↓
frontend/data/papers.json
      ↓
GitHub Actions daily-update.yml（每天 UTC 02:05）
```

### 精选管道（顶会/顶刊，每周）

```
fetch_curated_fast.py
  ├─ [阶段 A] OpenAlex API — 22 个期刊（Source ID 精确过滤，cursor 翻页）
  └─ [阶段 B] Semantic Scholar API — 17 个顶会（venue= 过滤，token 翻页）
      ↓
output/papers_curated.json（完整版，含 abstract，~230 MB）
      ↓
scripts/sync_curated.py（去掉 abstract，瘦身到 ~88 MB）
      ↓
frontend/data/papers_curated.json
      ↓
GitHub Actions sync_curated_weekly.yml（每周一 UTC 03:00）
```

---

## 3. 精选抓取逻辑详解

### 为什么两个数据源？

| 数据源 | 适合的 venue | 原因 |
|--------|------------|------|
| **OpenAlex** | TPAMI / Nature / TMI / RA-L 等**期刊** | 有稳定 Source ID，可精确过滤全量 |
| **Semantic Scholar** | NeurIPS / CVPR / ICRA / MICCAI 等**顶会** | OpenAlex 对顶会以 arXiv 预印本收录，Source ID 无效；S2 提供 `venue=` 直接过滤 |

### OpenAlex：Source ID + cursor 翻页

```bash
# 查询 Source ID
curl "https://api.openalex.org/sources?filter=display_name.search:TPAMI&per_page=3"

# 验证（确认 works_count > 0）
curl "https://api.openalex.org/sources/S199944782" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['display_name'], d['works_count'])"
```

过滤条件：`primary_location.source.id:S199944782,from_publication_date:2023-01-01`
翻页：`cursor=*` 无上限（每页 200 条），8 并发，间隔 0.11s

### Semantic Scholar：venue= + token 翻页

```bash
# 验证 venue 名称（total > 0 表示有效）
curl "https://api.semanticscholar.org/graph/v1/paper/search/bulk\
?venue=Neural+Information+Processing+Systems&year=2024&fields=venue&limit=1"
```

翻页：`token` 游标，每页最多 1000 条，2 并发，间隔 1.2s（免费 100 req/min）

### 增量合并

以 `arxiv:{arxiv_id}` 或 `s2:{paperId}` 为主键去重：
- 新论文：直接追加
- 已有论文：只更新 `citation_count`（引用数持续增长）

---

## 4. 领域分类逻辑

每篇论文的 `_domains` 字段由**两层**决定：

### 第一层：Venue 预归属

| `domains` 配置 | `default_domain` | 行为 |
|---------------|-----------------|------|
| `["physical_ai"]` | — | 固定领域，不跑关键词（ICRA / IROS 等专业会议） |
| `[]` | `"world_model"` | 关键词优先，无命中则兜底（CVPR / TPAMI 等） |
| `[]` | `None` | 关键词优先，**无命中则丢弃**（NeurIPS / ICML 等综合会议） |

### 第二层：关键词规则匹配（`cleaning/__init__.py`）

对 `title + abstract` 全文正则匹配：

- **World Model**（~40 条）：`world model / video generation / gaussian splatting / sim-to-real / neural radiance ...`
- **Physical AI**（~40 条）：`physics-informed / PINN / neural operator / robot learning / embodied AI ...`
- **Medical AI**（~60 条）：`medical imaging / tumor detection / drug discovery / protein folding / AlphaFold ...`

> ⚠️ 函数签名：`check_domains_all(title: str, abstract: str)` —— 必须传两个字符串，不能传 dict。

### 子任务标注（`_tasks`）

| 领域 | 标签 | 关键词 |
|------|------|-------|
| World Model | WorldModel / VidGen / NeRF / MBRL / Sim2Real | world model / video diffusion / gaussian splatting ... |
| Physical AI | PINN / NeuralOp / RobotLearn / Embodied | physics-informed / FNO / manipulation / humanoid ... |
| Medical AI | MedImg / Cancer / MedVLM / DrugMol / Protein | MRI / tumor / medical LLM / drug discovery / AlphaFold ... |

---

## 5. 顶会/顶刊白名单（39 个）

### OpenAlex 期刊（22 个）

| Venue | 级别 | 领域 | Source ID |
|-------|------|------|-----------|
| AAAI | CCF-A | 关键词决定 | S4210191458 |
| TPAMI | T1 | 关键词决定 | S199944782 |
| IJCV | T1 | 关键词决定 | S25538012 |
| TIP | T1 | 关键词决定 | S4210173141 |
| JMLR | T1 | 关键词决定 | S118988714 |
| Nature | T1 | 关键词决定 | S137773608 |
| Nature Machine Intelligence | T1 | 关键词决定 | S2912241403 |
| Nature Communications | T1 | 关键词决定 | S64187185 |
| Science Robotics | T1 | Physical AI | S4210213233 |
| TRO | T1 | Physical AI | S144620930 |
| IJRR | T1 | Physical AI | S73484101 |
| RA-L | T2 | Physical AI | S4210169774 |
| Science | T1 | Medical AI | S3880285 |
| PNAS | T1 | Medical AI | S125754415 |
| Nature Medicine | T1 | Medical AI | S203256638 |
| Nature Methods | T1 | Medical AI | S127827428 |
| The Lancet | T2 | Medical AI | S49861241 |
| JAMA | T2 | Medical AI | S172573765 |
| BMJ | T2 | Medical AI | S192814187 |
| Cell | T2 | Medical AI | S110447773 |
| TMI | T3 | Medical AI | S58069681 |
| Radiology | T3 | Medical AI | S50280174 |
| Bioinformatics | T3 | Medical AI | S52395412 |

### Semantic Scholar 顶会（17 个）

| Venue | 级别 | 领域 | S2 venue 字符串 |
|-------|------|------|----------------|
| NeurIPS | CCF-A | 关键词决定（无兜底） | Neural Information Processing Systems |
| ICML | CCF-A | 关键词决定（无兜底） | International Conference on Machine Learning |
| ICLR | CCF-A | 关键词决定（无兜底） | International Conference on Learning Representations |
| CVPR | CCF-A | 关键词决定（兜底 world_model） | Computer Vision and Pattern Recognition |
| ICCV | CCF-A | 关键词决定（兜底 world_model） | International Conference on Computer Vision |
| ECCV | CCF-B | 关键词决定（兜底 world_model） | European Conference on Computer Vision |
| SIGGRAPH | CCF-A | World Model | SIGGRAPH |
| SIGGRAPH Asia | CCF-A | World Model | SIGGRAPH Asia |
| ACM MM | CCF-A | 关键词决定（兜底 world_model） | ACM Multimedia |
| ACL | CCF-A | 关键词决定（无兜底） | Annual Meeting of the Association for Computational Linguistics |
| EMNLP | CCF-B | 关键词决定（无兜底） | Conference on Empirical Methods in Natural Language Processing |
| NAACL | CCF-B | 关键词决定（无兜底） | North American Chapter of the Association for Computational Linguistics |
| ICRA | CCF-B | Physical AI | International Conference on Robotics and Automation |
| IROS | CCF-C | Physical AI | IROS |
| CoRL | T2 | Physical AI | Conference on Robot Learning |
| RSS | T2 | Physical AI | Robotics: Science and Systems |
| MICCAI | CCF-B | Medical AI | Medical Image Computing and Computer-Assisted Intervention |
| MIDL | T3 | Medical AI | MIDL |

---

## 6. 快速开始

### 安装依赖

```bash
pip install -r requirements.txt

# macOS Homebrew Python 报 externally-managed-environment 时：
pip install -r requirements.txt --break-system-packages
```

### 首次全量抓取精选论文（2023 年至今）

```bash
# 在项目根目录运行，约 30–60 分钟
python fetch_curated_fast.py --year-from 2023
```

---

## 7. 日常操作流程

### 抓取 + 同步前端（标准流程）

```bash
# 第一步：抓取（全量或增量）
python fetch_curated_fast.py --year-from 2026          # 只抓今年（增量，5-10 分钟）
python fetch_curated_fast.py --year-from 2023          # 全量（30-60 分钟）

# 第二步：同步到 frontend/data/（自动去 abstract，瘦身到 ~88 MB）
python scripts/sync_curated.py --local output/papers_curated.json

# 第三步：提交推送
git add frontend/data/papers_curated.json
git commit -m "data: sync papers_curated $(date +%Y-%m-%d)"
git push
```

### 常用抓取命令

```bash
# 只跑 OpenAlex 期刊
python fetch_curated_fast.py --year-from 2023 --oa-only

# 只跑 S2 顶会
python fetch_curated_fast.py --year-from 2023 --s2-only

# 调试单个 venue（dry-run 不写文件）
python fetch_curated_fast.py --venue CVPR --year-from 2024 --dry-run
python fetch_curated_fast.py --venue "ACM MM" --year-from 2024
python fetch_curated_fast.py --venue NeurIPS --year-from 2023
```

### 速览（arXiv）数据更新

```bash
python backend/main.py                          # 增量（最近 30 天）
python backend/main.py --full --year-from 2023  # 全量重建
```

---

## 8. 添加新 Venue

### OpenAlex 期刊

```bash
# 1. 查询 Source ID
curl "https://api.openalex.org/sources?filter=display_name.search:Medical+Image+Analysis&per_page=3" \
  | python3 -c "import json,sys; [print(r['id'].split('/')[-1], r['works_count'], r['display_name']) \
    for r in json.load(sys.stdin)['results']]"

# 2. 验证
curl "https://api.openalex.org/sources/S116571295" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['display_name'], d['works_count'])"
```

在 `fetch_curated_fast.py` 中添加：
```python
# KNOWN_SOURCE_IDS：
"MIA": "S116571295",   # Medical Image Analysis | 3,958 works

# ALL_VENUES：
"MIA": {"tier": "T2", "domains": ["medical_ai"]},
```

### Semantic Scholar 顶会

```bash
# 验证 venue 名称（先试缩写，再试全称）
python3 - <<'EOF'
import urllib.request, urllib.parse, json
for name in ["AAMAS", "Autonomous Agents and Multi-Agent Systems"]:
    params = urllib.parse.urlencode({"venue": name, "year": "2024", "fields": "venue", "limit": 1})
    with urllib.request.urlopen(
        f"https://api.semanticscholar.org/graph/v1/paper/search/bulk?{params}"
    ) as r:
        d = json.loads(r.read())
    print(f"total={d.get('total')}  name={name!r}")
EOF
```

在 `fetch_curated_fast.py` 中添加：
```python
# S2_VENUES：
"AAMAS": {
    "s2_name":        "AAMAS",
    "tier":           "CCF-B",
    "domains":        [],
    "default_domain": None,   # 无命中则丢弃
},
```

---

## 9. 修复旧数据领域标注

如果发现论文被错标为多个领域（同时含 world_model + physical_ai + medical_ai）：

```bash
python reclassify_domains.py --dry-run   # 预览
python reclassify_domains.py             # 正式修复
```

**修复前后（实测）：**
```
Before: multi-domain 47%  →  After: 0.1%
```

---

## 10. GitHub Actions 自动化

### 速览每日（`.github/workflows/daily-update.yml`）
```
触发：UTC 02:05 每天  →  python backend/main.py  →  git push
```

### 精选每周同步（`.github/workflows/sync_curated_weekly.yml`）
```
触发：UTC 03:00 每周一  →  python scripts/sync_curated.py  →  git push
```

### 精选每月全量（可选）

```yaml
# .github/workflows/fetch_curated_monthly.yml
name: Monthly curated fetch
on:
  schedule:
    - cron: '0 2 1 * *'
  workflow_dispatch:
jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python fetch_curated_fast.py --year-from 2023
      - run: python scripts/sync_curated.py --local output/papers_curated.json
      - run: |
          git config user.email "actions@github.com"
          git config user.name "GitHub Actions"
          git add frontend/data/papers_curated.json
          git commit -m "data: monthly curated sync $(date +%Y-%m-%d)" || echo "no changes"
          git push
```

---

## 11. 环境变量

创建 `.env`（精选抓取不需要，仅 LLM 关键词更新和 Supabase 需要）：

```env
# LLM 关键词更新（GLM / DeepSeek / OpenAI 兼容接口均可）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4

# Supabase（用户收藏、评论等功能）
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
```

**API 免费限额：**
- OpenAlex：完全免费，10 req/s
- Semantic Scholar：免费 100 req/min；如需更高限额，在 `fetch_curated_fast.py` 中取消注释：
  ```python
  S2_HEADERS["x-api-key"] = "YOUR_S2_API_KEY"  # 提升至 1000 req/min
  ```

---

## License

MIT
