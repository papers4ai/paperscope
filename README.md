# 🔭 Paperscope

AI 研究论文发现与追踪平台，聚焦 **World Model · Physical AI · Medical AI** 三个方向。

## 架构

```
┌────────────────────────────────────────────────┐
│  数据源                                         │
│  arXiv · OpenAlex · Semantic Scholar · PubMed  │
└──────────────────┬─────────────────────────────┘
                   ↓ (GitHub Actions 定时抓取)
┌────────────────────────────────────────────────┐
│  Supabase (PostgreSQL)                         │
│  papers · users · favorites · notes · ...      │
└──────────────────┬─────────────────────────────┘
                   ↓ (REST / JS SDK)
┌────────────────────────────────────────────────┐
│  前端 (GitHub Pages, Vanilla JS)               │
│  速览 / 精选 / 热榜 / 我的                      │
└────────────────────────────────────────────────┘
```

## 目录结构

```
Paperscope/
├── backend/
│   ├── scrapers/         # arXiv / SS / PubMed / OpenAlex 抓取脚本
│   ├── pipeline/         # 分类 / 热榜 / 每周精选
│   ├── db/               # Supabase schema 和客户端
│   └── config/           # 领域定义 + 会议白名单
├── frontend/             # index.html + assets
├── .github/workflows/    # 定时抓取任务
└── requirements.txt
```

## 开发路线图

- **v1.0** 核心基础：三领域导航 + arXiv速览 + 精选论文 + 侧边详情面板
- **v1.1** 发现功能：热榜 + 新星论文
- **v1.2** 沉淀功能：收藏 + 笔记 + 已读 + 历史
- **v1.3** 传播功能：分享卡片 + 每周精选静态页

## 环境准备

```bash
cp .env.example .env       # 填入 Supabase / LLM / SS API Key
pip install -r requirements.txt
```

## 相关账号

- [Supabase](https://supabase.com) — 数据库 + Auth
- [Semantic Scholar API](https://www.semanticscholar.org/product/api) — 免费申请提升速率
- [Brevo](https://brevo.com) — 邮件验证（可选）
