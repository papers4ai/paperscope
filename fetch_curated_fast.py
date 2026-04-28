#!/usr/bin/env python3
"""
精选论文快速抓取器 v4 — OpenAlex + Semantic Scholar 双源异步并行版
==================================================================

核心逻辑
--------
1. 维护两张白名单：
   - ALL_VENUES（OpenAlex 期刊/AAAI）：用 Source ID 精确过滤，cursor 翻页
   - S2_VENUES（顶会：NeurIPS/ICML/ICLR/CVPR/ICCV/ECCV/ICRA/IROS 等）：
     Semantic Scholar paper/search/bulk，venue= 过滤，token 翻页

2. 领域标注（_domains）分两层：
   - 第一层：venue 预归属（如 ICRA → physical_ai；NeurIPS → [] 不预设）
   - 第二层：cleaning 模块关键词规则（title + abstract 全文匹配）
     → 综合型会议（NeurIPS/ICML/CVPR）无命中则丢弃（不强行分域）

3. 子任务标注（_tasks）、论文类型（type）、代码链接（code）：
   统一由 cleaning 模块处理。

4. 异步并行：
   - OpenAlex：Semaphore(8)，每页 200 条，翻页间隔 0.11s
   - S2：Semaphore(2)，每页 500 条，翻页间隔 1.2s（免费 100 req/min）

5. 增量合并：以论文 ID 为 key，已有论文跳过，只追加新增，
   同时更新引用数。

用法
----
    pip install aiohttp
    python fetch_curated_fast.py --year-from 2023          # 首次全量
    python fetch_curated_fast.py --year-from 2026          # 每月增量
    python fetch_curated_fast.py --year-from 2023 --venue NeurIPS  # 调试单个 venue
    python fetch_curated_fast.py --year-from 2023 --dry-run
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    print("请先安装依赖: pip install aiohttp")
    sys.exit(1)

# ── 可选：复用 cleaning 模块进行二次领域/任务标注 ──────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
try:
    from cleaning import (
        check_domains_all,
        tag_tasks_all,
        extract_code_links,
        classify_paper_type,
    )
    HAS_CLEANING = True
except ImportError:
    HAS_CLEANING = False
    print("[warn] cleaning 模块未找到，跳过关键词二次标注")


# ═══════════════════════════════════════════════════════════════════════════════
# 顶会/顶刊白名单
# ═══════════════════════════════════════════════════════════════════════════════
#
# 每条记录说明：
#   tier    — 会议/期刊级别，用于前端筛选标签
#   domains — 预归属领域（不依赖关键词，直接打标）
#             同一 venue 可属于多个领域（例如 NeurIPS 三个领域都有相关论文）
#
# 添加新 venue：
#   1. 在 KNOWN_SOURCE_IDS 填入 OpenAlex Source ID
#      （查询地址：https://openalex.org/sources?filter=display_name.search:<名称>）
#   2. 在 ALL_VENUES 添加对应配置即可

KNOWN_SOURCE_IDS: Dict[str, str] = {
    # ══════════════════════════════════════════════════════════════════════════
    # 所有 ID 均通过以下命令验证（2025-04 重新核对）：
    #   curl -s "https://api.openalex.org/sources/<ID>" | python3 -c
    #     "import json,sys; d=json.load(sys.stdin); print(d['display_name'], d['works_count'])"
    #
    # ⚠ 重要说明：NeurIPS / ICML / ICLR / CVPR / ICCV / ECCV / ICRA / IROS /
    #   ACL / EMNLP 等顶会在 OpenAlex 中主要以 arXiv 预印本索引，
    #   没有稳定覆盖全年的单一 Source ID，因此这些顶会通过 fetch_curated.py
    #   (DBLP / CVF / OpenReview) 抓取，本脚本只处理以下期刊和 AAAI。
    # ══════════════════════════════════════════════════════════════════════════

    # ── 顶会（OpenAlex 有稳定单一 Source ID 的） ──────────────────────────────
    "AAAI":              "S4210191458",  # Proceedings of the AAAI Conf on AI     | 25,109 ✓

    # ── AI / CV 顶刊 ──────────────────────────────────────────────────────────
    "TPAMI":             "S199944782",   # IEEE Trans. Pattern Analysis & Machine Intelligence | 12,151
    "IJCV":              "S25538012",    # International Journal of Computer Vision             | 3,837
    "TIP":               "S4210173141",  # IEEE Transactions on Image Processing               | 12,902
    "JMLR":              "S118988714",   # Journal of Machine Learning Research                | 1,411

    # ── 综合科学顶刊 ──────────────────────────────────────────────────────────
    "Nature":            "S137773608",   # Nature                               | 448,199 ✓
    "Science":           "S3880285",     # Science                              | verified ✓
    "PNAS":              "S125754415",   # Proc. National Academy of Sciences   | 170,221
    "Nature Machine Intelligence": "S2912241403",  # Nature Machine Intelligence  | 1,221
    "Nature Communications":       "S64187185",    # Nature Communications        | 87,537

    # ── 医学顶刊 ──────────────────────────────────────────────────────────────
    "Nature Medicine":   "S203256638",   # Nature Medicine       | 16,237
    "Nature Methods":    "S127827428",   # Nature Methods        | 8,336
    "The Lancet":        "S49861241",    # The Lancet            | 475,370
    "JAMA":              "S172573765",   # JAMA                  | 268,743
    "BMJ":               "S192814187",   # BMJ                   | 308,640
    "Cell":              "S110447773",   # Cell                  | 26,887
    "TMI":               "S58069681",    # IEEE Trans. Medical Imaging | 8,659
    "Radiology":         "S50280174",    # Radiology             | 62,848
    "Bioinformatics":    "S52395412",    # Bioinformatics        | 19,318

    # ── 机器人顶刊 ────────────────────────────────────────────────────────────
    "Science Robotics":  "S4210213233",  # Science Robotics                       | 926
    "TRO":               "S144620930",   # IEEE Transactions on Robotics          | 4,127
    "RA-L":              "S4210169774",  # IEEE Robotics and Automation Letters   | 10,773
    "IJRR":              "S73484101",    # Int'l Journal of Robotics Research     | 3,209
}

ALL_VENUES: Dict[str, dict] = {
    # ══════════════════════════════════════════════════════════════════════════
    # 只包含在 KNOWN_SOURCE_IDS 中有验证可用 Source ID 的 venue。
    # 顶会通过 S2_VENUES + Semantic Scholar API 抓取（见下方）。
    # ══════════════════════════════════════════════════════════════════════════

    # ── AAAI（唯一在 OpenAlex 有完整稳定索引的 AI 顶会） ──────────────────────
    "AAAI":     {"tier": "CCF-A",  "domains": [], "default_domain": "world_model"},

    # ── AI / CV 顶刊（关键词决定领域，兜底 world_model） ──────────────────────
    "TPAMI":    {"tier": "T1",     "domains": [], "default_domain": "world_model"},
    "IJCV":     {"tier": "T1",     "domains": [], "default_domain": "world_model"},
    "TIP":      {"tier": "T1",     "domains": [], "default_domain": "world_model"},
    "JMLR":     {"tier": "T1",     "domains": [], "default_domain": "world_model"},

    # ── 综合科学顶刊（关键词决定领域，兜底 world_model） ──────────────────────
    "Nature":                      {"tier": "T1", "domains": [], "default_domain": "world_model"},
    "Nature Machine Intelligence": {"tier": "T1", "domains": [], "default_domain": "world_model"},
    "Nature Communications":       {"tier": "T1", "domains": [], "default_domain": "world_model"},

    # ── 机器人顶刊（固定 Physical AI） ──────────────────────────────────────
    "Science Robotics": {"tier": "T1", "domains": ["physical_ai"]},
    "TRO":      {"tier": "T1",     "domains": ["physical_ai"]},
    "IJRR":     {"tier": "T1",     "domains": ["physical_ai"]},
    "RA-L":     {"tier": "T2",     "domains": ["physical_ai"]},

    # ── 医学顶刊（固定 Medical AI） ─────────────────────────────────────────
    "Science":           {"tier": "T1", "domains": ["medical_ai"]},
    "PNAS":              {"tier": "T1", "domains": ["medical_ai"]},
    "Nature Medicine":   {"tier": "T1", "domains": ["medical_ai"]},
    "Nature Methods":    {"tier": "T1", "domains": ["medical_ai"]},
    "The Lancet":        {"tier": "T2", "domains": ["medical_ai"]},
    "JAMA":              {"tier": "T2", "domains": ["medical_ai"]},
    "BMJ":               {"tier": "T2", "domains": ["medical_ai"]},
    "Cell":              {"tier": "T2", "domains": ["medical_ai"]},
    "TMI":               {"tier": "T3", "domains": ["medical_ai"]},
    "Radiology":         {"tier": "T3", "domains": ["medical_ai"]},
    "Bioinformatics":    {"tier": "T3", "domains": ["medical_ai"]},
}


# ═══════════════════════════════════════════════════════════════════════════════
# Semantic Scholar 顶会白名单
# ═══════════════════════════════════════════════════════════════════════════════
#
# s2_name  — Semantic Scholar 数据库中该会议的规范名称
#            通过以下命令验证：
#            curl -s "https://api.semanticscholar.org/graph/v1/paper/search/bulk\
#              ?venue=<名称>&year=2024&fields=venue&limit=1" | python3 -c
#              "import json,sys; d=json.load(sys.stdin); print(d.get('total'), d['data'][0].get('venue'))"
#
# domains  — 同 ALL_VENUES：专业会议固定领域，综合型会议 [] 靠关键词
# default_domain — None 表示无关键词命中时直接丢弃（不做兜底归属）
#                  这样从 NeurIPS/CVPR 只保留三个领域真正相关的论文

S2_VENUES: Dict[str, dict] = {
    # ── AI / ML 综合顶会（关键词决定领域，无命中则丢弃） ─────────────────────
    "NeurIPS": {
        "s2_name":      "Neural Information Processing Systems",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": None,   # 不相关论文直接丢弃
    },
    "ICML": {
        "s2_name":      "International Conference on Machine Learning",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": None,
    },
    "ICLR": {
        "s2_name":      "International Conference on Learning Representations",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": None,
    },
    # ── CV 顶会（关键词决定领域，兜底 world_model：CV 论文与 WM 高度相关） ──
    "CVPR": {
        "s2_name":      "Computer Vision and Pattern Recognition",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": "world_model",
    },
    "ICCV": {
        "s2_name":      "International Conference on Computer Vision",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": "world_model",
    },
    "ECCV": {
        "s2_name":      "European Conference on Computer Vision",
        "tier":         "CCF-B",
        "domains":      [],
        "default_domain": "world_model",
    },
    "SIGGRAPH": {
        "s2_name":      "SIGGRAPH",   # S2 索引名；ACM Trans. Graph. 同刊论文另算
        "tier":         "CCF-A",
        "domains":      ["world_model"],   # 图形/视觉生成
    },
    "SIGGRAPH Asia": {
        "s2_name":      "SIGGRAPH Asia",
        "tier":         "CCF-A",
        "domains":      ["world_model"],
    },
    "ACM MM": {
        "s2_name":      "ACM Multimedia",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": "world_model",  # 多媒体/视频生成，兜底 world_model
    },

    # ── NLP 顶会（关键词决定领域，无命中丢弃） ────────────────────────────────
    "ACL": {
        "s2_name":      "Annual Meeting of the Association for Computational Linguistics",
        "tier":         "CCF-A",
        "domains":      [],
        "default_domain": None,
    },
    "EMNLP": {
        "s2_name":      "Conference on Empirical Methods in Natural Language Processing",
        "tier":         "CCF-B",
        "domains":      [],
        "default_domain": None,
    },
    "NAACL": {
        "s2_name":      "North American Chapter of the Association for Computational Linguistics",
        "tier":         "CCF-B",
        "domains":      [],
        "default_domain": None,
    },

    # ── 机器人顶会（固定 Physical AI） ───────────────────────────────────────
    "ICRA": {
        "s2_name":      "International Conference on Robotics and Automation",
        "tier":         "CCF-B",
        "domains":      ["physical_ai"],
    },
    "IROS": {
        "s2_name":      "IROS",   # S2 内部使用缩写; 全称 "Intelligent Robots and Systems" 同样有效
        "tier":         "CCF-C",
        "domains":      ["physical_ai"],
    },
    "CoRL": {
        "s2_name":      "Conference on Robot Learning",
        "tier":         "T2",
        "domains":      ["physical_ai"],
    },
    "RSS": {
        "s2_name":      "Robotics: Science and Systems",
        "tier":         "T2",
        "domains":      ["physical_ai"],
    },

    # ── 医学顶会（固定 Medical AI） ──────────────────────────────────────────
    "MICCAI": {
        "s2_name":      "Medical Image Computing and Computer-Assisted Intervention",
        "tier":         "CCF-B",
        "domains":      ["medical_ai"],
    },
    "MIDL": {
        "s2_name":      "MIDL",   # S2 使用缩写（全称返回 0）
        "tier":         "T3",
        "domains":      ["medical_ai"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# 全局常量
# ═══════════════════════════════════════════════════════════════════════════════

# ── OpenAlex ────────────────────────────────────────────────────────────────
BASE = "https://api.openalex.org"
OA_HEADERS = {
    "User-Agent": "Paperscope/4.0 (mailto:admin@paperscope.dev)",
    # 明确排除 Brotli 压缩，aiohttp 默认不支持 br 解码
    "Accept-Encoding": "gzip, deflate",
}
OA_CONCURRENCY = 8    # 同时飞行的 venue 协程数（OpenAlex 允许 10 req/s）
OA_PER_PAGE    = 200  # 每页最大条数（OpenAlex 上限）
OA_REQUEST_GAP = 0.11 # 翻页间隔（秒）

# ── Semantic Scholar ─────────────────────────────────────────────────────────
S2_BASE        = "https://api.semanticscholar.org/graph/v1"
S2_HEADERS     = {
    "User-Agent": "Paperscope/4.0 (mailto:admin@paperscope.dev)",
    "Accept-Encoding": "gzip, deflate",
}
# API Key 优先从环境变量读取，其次可在此处硬编码（可提升限额至 1000 req/min）
_S2_API_KEY = os.environ.get("S2_API_KEY", "")
if _S2_API_KEY:
    S2_HEADERS["x-api-key"] = _S2_API_KEY
    S2_CONCURRENCY = 8    # 有 Key：并发提升
    S2_REQUEST_GAP = 0.15 # 有 Key：请求间隔缩短
else:
    S2_CONCURRENCY = 2    # 免费限额约 100 req/min，保守并发
    S2_REQUEST_GAP = 1.2  # 翻页间隔（秒）：2 并发 × 1.2s ≈ 100 req/min
S2_PER_PAGE    = 1000 # bulk 端点单次最大 1000
S2_FIELDS      = "title,abstract,year,venue,citationCount,externalIds,authors,publicationDate"

# ── 通用 ─────────────────────────────────────────────────────────────────────
# 兼容旧代码：部分地方仍使用 HEADERS / CONCURRENCY / PER_PAGE / REQUEST_GAP
HEADERS     = OA_HEADERS
CONCURRENCY = OA_CONCURRENCY
PER_PAGE    = OA_PER_PAGE
REQUEST_GAP = OA_REQUEST_GAP

OUTPUT = "output/papers_curated.json"


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """从 OpenAlex 倒排索引重建摘要文本。

    OpenAlex 不直接返回摘要字符串，而是返回 {word: [位置列表]} 的倒排索引。
    按位置排序后拼接即可还原原始摘要。
    """
    if not inverted_index:
        return ""
    pairs: List[Tuple[int, str]] = [
        (pos, word)
        for word, positions in inverted_index.items()
        for pos in positions
    ]
    pairs.sort()
    return " ".join(w for _, w in pairs)


def normalize(item: dict, venue_name: str, venue_cfg: dict) -> Optional[dict]:
    """将 OpenAlex /works 单条记录转换为 Paperscope 统一格式。

    字段说明：
      id            — 优先用 arxiv:{arxiv_id}，无 arXiv 版本则用 openalex:{oa_id}
      _domains      — 第一层：venue 预归属；第二层：cleaning 模块关键词匹配（可追加）
      _tasks        — 细粒度研究方向标签（WorldModel / VidGen / PINN / MedImg 等）
      type          — Method / Dataset / Survey（基于标题摘要关键词判断）
      has_code/code — 从摘要提取 GitHub / HuggingFace 链接
    """
    title = (item.get("title") or "").strip()
    if not title:
        return None

    # ── ID ──────────────────────────────────────────────────────────────────
    oa_id = item.get("id", "").split("/")[-1]
    doi = item.get("doi") or ""
    arxiv_id: Optional[str] = None
    if doi and "arxiv" in doi.lower():
        raw = doi.split("arXiv.")[-1] if "arXiv." in doi else doi.split("arxiv.")[-1]
        arxiv_id = re.sub(r"v\d+$", "", raw)

    uid = f"arxiv:{arxiv_id}" if arxiv_id else f"openalex:{oa_id}"

    # ── 摘要 ─────────────────────────────────────────────────────────────────
    abstract = reconstruct_abstract(item.get("abstract_inverted_index"))

    # ── 作者 ─────────────────────────────────────────────────────────────────
    authors = [
        a["author"]["display_name"]
        for a in (item.get("authorships") or [])
        if a.get("author", {}).get("display_name")
    ]

    # ── URL ──────────────────────────────────────────────────────────────────
    loc = item.get("primary_location") or {}
    pdf_url = (
        loc.get("pdf_url")
        or (item.get("open_access") or {}).get("oa_url")
        or (f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None)
    )
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None

    # ── 日期 ─────────────────────────────────────────────────────────────────
    pub_date = item.get("publication_date") or ""
    year  = int(pub_date[:4])  if len(pub_date) >= 4 else None
    month = int(pub_date[5:7]) if len(pub_date) >= 7 else None

    # ── 领域分配策略 ────────────────────────────────────────────────────────
    # venue 预归属（硬编码）：专业 venue（MICCAI/ICRA 等）直接确定领域
    venue_domains: List[str] = list(venue_cfg.get("domains", []))
    default_domain: Optional[str] = venue_cfg.get("default_domain")

    p: dict = {
        "id":             uid,
        "title":          title,
        "abstract":       abstract,
        "authors":        authors,
        "published":      pub_date,
        "year":           year,
        "month":          month,
        "pdf_url":        pdf_url,
        "arxiv_url":      arxiv_url,
        "doi":            doi or None,
        "venue":          venue_name,
        "venue_tier":     venue_cfg.get("tier", ""),
        "citation_count": item.get("cited_by_count") or 0,
        "_domains":       venue_domains,   # 先用 venue 预归属，后面可能被覆盖
        "_tasks":         [],
        "type":           "Method",
        "has_code":       False,
        "code":           None,
    }

    # ── 关键词二次分类（仅对 domains=[] 的综合型 venue 生效） ──────────────
    if HAS_CLEANING:
        try:
            tasks, _ = tag_tasks_all(title, abstract)
            p["_tasks"] = tasks
            p["type"] = classify_paper_type(title, abstract)
            links = extract_code_links(f"{title} {abstract}")
            if links:
                p["code"] = links[0]
                p["has_code"] = True

            # 只有 venue 未预设领域时，才用关键词检测结果覆盖
            if not venue_domains:
                detected, _ = check_domains_all(title, abstract)
                if detected:
                    p["_domains"] = detected          # 关键词命中 → 使用关键词结果
                elif default_domain:
                    p["_domains"] = [default_domain]  # 兜底：避免论文无领域
        except Exception:
            # cleaning 报错不影响主流程，保留 venue 预归属
            pass

    return p


def normalize_s2(item: dict, venue_name: str, venue_cfg: dict) -> Optional[dict]:
    """将 Semantic Scholar paper/search/bulk 单条记录转换为 Paperscope 统一格式。

    与 normalize() 的主要区别：
      - abstract 直接是字符串（不是倒排索引）
      - arxiv ID 来自 externalIds.ArXiv
      - 使用 s2:<paperId> 作为无 arXiv 版本的兜底 ID
    """
    title = (item.get("title") or "").strip()
    if not title:
        return None

    # ── ID ───────────────────────────────────────────────────────────────────
    ext_ids   = item.get("externalIds") or {}
    arxiv_id  = ext_ids.get("ArXiv")
    s2_id     = item.get("paperId", "")
    uid = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{s2_id}"

    # ── 摘要 ─────────────────────────────────────────────────────────────────
    abstract = (item.get("abstract") or "").strip()

    # ── 作者 ─────────────────────────────────────────────────────────────────
    authors = [
        a.get("name", "")
        for a in (item.get("authors") or [])
        if a.get("name")
    ]

    # ── 日期 ─────────────────────────────────────────────────────────────────
    pub_date = item.get("publicationDate") or ""
    year_val = item.get("year")
    year  = year_val if year_val else (int(pub_date[:4]) if len(pub_date) >= 4 else None)
    month = int(pub_date[5:7]) if len(pub_date) >= 7 else None

    # ── URL ──────────────────────────────────────────────────────────────────
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None
    pdf_url   = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None

    # ── 领域分配（与 normalize() 逻辑一致） ──────────────────────────────────
    venue_domains: List[str] = list(venue_cfg.get("domains", []))
    default_domain: Optional[str] = venue_cfg.get("default_domain")

    p: dict = {
        "id":             uid,
        "title":          title,
        "abstract":       abstract,
        "authors":        authors,
        "published":      pub_date,
        "year":           year,
        "month":          month,
        "pdf_url":        pdf_url,
        "arxiv_url":      arxiv_url,
        "doi":            ext_ids.get("DOI"),
        "venue":          venue_name,
        "venue_tier":     venue_cfg.get("tier", ""),
        "citation_count": item.get("citationCount") or 0,
        "_domains":       venue_domains,
        "_tasks":         [],
        "type":           "Method",
        "has_code":       False,
        "code":           None,
    }

    if HAS_CLEANING:
        try:
            tasks, _ = tag_tasks_all(title, abstract)
            p["_tasks"] = tasks
            p["type"] = classify_paper_type(title, abstract)
            links = extract_code_links(f"{title} {abstract}")
            if links:
                p["code"] = links[0]
                p["has_code"] = True

            if not venue_domains:
                detected, _ = check_domains_all(title, abstract)
                if detected:
                    p["_domains"] = detected
                elif default_domain:
                    p["_domains"] = [default_domain]
                else:
                    return None   # 无领域命中且无兜底 → 丢弃（对 NeurIPS/ICML 等生效）
        except Exception:
            if not venue_domains and not default_domain:
                return None   # cleaning 出错时也执行同样的丢弃策略
    else:
        # 没有 cleaning 模块时：综合型 venue（无预设域）全部丢弃
        if not venue_domains and not default_domain:
            return None

    return p


# ═══════════════════════════════════════════════════════════════════════════════
# Semantic Scholar 异步抓取
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_s2_venue(
    session: "aiohttp.ClientSession",
    venue_name: str,
    venue_cfg: dict,
    year_from: int,
) -> List[dict]:
    """通过 Semantic Scholar paper/search/bulk 抓取单个顶会的论文。

    使用 token 游标翻页（类似 OpenAlex cursor），无最大 10000 条限制。
    每次请求最多返回 S2_PER_PAGE 条，翻页间隔 S2_REQUEST_GAP 秒。
    """
    s2_name = venue_cfg["s2_name"]
    papers: List[dict] = []
    token: Optional[str] = None
    current_year = date.today().year
    page = 0

    while True:
        params: dict = {
            "venue":  s2_name,
            "year":   f"{year_from}-{current_year}",
            "fields": S2_FIELDS,
            "limit":  S2_PER_PAGE,
        }
        if token:
            params["token"] = token

        try:
            async with session.get(
                f"{S2_BASE}/paper/search/bulk",
                params=params,
                headers=S2_HEADERS,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                if r.status == 429:
                    wait = int(r.headers.get("Retry-After", "10"))
                    print(f"  [{venue_name}] S2 rate-limit, waiting {wait}s…")
                    await asyncio.sleep(wait)
                    continue
                if r.status == 400:
                    text = await r.text()
                    print(f"  [{venue_name}] S2 bad request: {text[:200]}")
                    break
                if r.status >= 500:
                    print(f"  [{venue_name}] S2 server error {r.status}, retrying…")
                    await asyncio.sleep(5)
                    continue
                data = await r.json()
        except asyncio.TimeoutError:
            print(f"  [{venue_name}] S2 timeout, retrying…")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            print(f"  [{venue_name}] S2 error: {e}")
            break

        results = data.get("data", [])
        page += 1
        kept = 0
        for item in results:
            p = normalize_s2(item, venue_name, venue_cfg)
            if p:
                papers.append(p)
                kept += 1

        token = data.get("token")
        total = data.get("total", "?")
        if page == 1:
            print(f"    {venue_name}: total={total}, page 1 → {kept}/{len(results)} kept")

        if not token or not results:
            break

        await asyncio.sleep(S2_REQUEST_GAP)

    return papers


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAlex 异步抓取
# ═══════════════════════════════════════════════════════════════════════════════

async def resolve_source_id(
    session: "aiohttp.ClientSession", venue_name: str
) -> Optional[str]:
    """获取 venue 的 OpenAlex Source ID。

    优先从 KNOWN_SOURCE_IDS 查表（无网络开销），
    查不到则调用 OpenAlex sources API 模糊搜索并返回第一条结果。
    """
    if venue_name in KNOWN_SOURCE_IDS:
        return KNOWN_SOURCE_IDS[venue_name]

    url = f"{BASE}/sources"
    params = {"filter": f"display_name.search:{venue_name}", "per_page": 5}
    try:
        async with session.get(url, params=params, headers=HEADERS) as r:
            data = await r.json()
            results = data.get("results", [])
            if results:
                sid = results[0]["id"].split("/")[-1]
                print(f"  Auto-resolved {venue_name} → {sid}")
                return sid
    except Exception as e:
        print(f"  [warn] resolve {venue_name}: {e}")
    return None


async def fetch_venue(
    session: "aiohttp.ClientSession",
    venue_name: str,
    venue_cfg: dict,
    source_id: str,
    year_from: int,
) -> List[dict]:
    """抓取单个 venue 从 year_from 至今的全部论文。

    使用 cursor 翻页（而非 page 翻页），无最大 10000 条的限制。
    过滤条件：primary_location.source.id 精确匹配，避免关键词模糊噪声。
    """
    papers: List[dict] = []
    cursor = "*"
    select_fields = (
        "id,doi,title,abstract_inverted_index,authorships,"
        "publication_date,primary_location,open_access,cited_by_count"
    )
    filt = (
        f"primary_location.source.id:{source_id},"
        f"from_publication_date:{year_from}-01-01"
    )

    while True:
        params = {
            "filter":   filt,
            "per_page": PER_PAGE,
            "cursor":   cursor,
            "select":   select_fields,
        }
        try:
            async with session.get(
                f"{BASE}/works",
                params=params,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                if r.status == 429:
                    print(f"  [{venue_name}] rate limit, waiting 5s…")
                    await asyncio.sleep(5)
                    continue
                if r.status >= 500:
                    print(f"  [{venue_name}] server error {r.status}, retrying…")
                    await asyncio.sleep(3)
                    continue
                data = await r.json()
        except asyncio.TimeoutError:
            print(f"  [{venue_name}] timeout, retrying…")
            await asyncio.sleep(3)
            continue
        except Exception as e:
            print(f"  [{venue_name}] error: {e}")
            break

        results = data.get("results", [])
        for item in results:
            p = normalize(item, venue_name, venue_cfg)
            if p:
                papers.append(p)

        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor or not results:
            break

        await asyncio.sleep(REQUEST_GAP)

    return papers


# ═══════════════════════════════════════════════════════════════════════════════
# 主协程
# ═══════════════════════════════════════════════════════════════════════════════

def _merge_papers(existing: Dict[str, dict], new_papers: List[dict]) -> int:
    """将 new_papers 合并进 existing 字典，返回新增数量。"""
    added = 0
    for p in new_papers:
        pid = p["id"]
        if pid not in existing:
            existing[pid] = p
            added += 1
        else:
            # 只更新引用数（其他字段保持首次抓取值）
            existing[pid]["citation_count"] = max(
                existing[pid].get("citation_count", 0),
                p.get("citation_count", 0),
            )
    return added


async def run(
    year_from: int,
    venue_filter: Optional[str],
    dry_run: bool,
    oa_only: bool = False,
    s2_only: bool = False,
) -> None:
    # ── 决定本次抓取哪些 venue ────────────────────────────────────────────────
    ALL_COMBINED = {**ALL_VENUES, **S2_VENUES}

    if venue_filter:
        if venue_filter in ALL_VENUES:
            oa_venues  = {} if s2_only else {venue_filter: ALL_VENUES[venue_filter]}
            s2_venues_ = {}
        elif venue_filter in S2_VENUES:
            oa_venues  = {}
            s2_venues_ = {} if oa_only else {venue_filter: S2_VENUES[venue_filter]}
        else:
            print(f"Unknown venue: {venue_filter}")
            print(f"Available: {', '.join(ALL_COMBINED)}")
            return
    else:
        oa_venues  = {} if s2_only else ALL_VENUES
        s2_venues_ = {} if oa_only else S2_VENUES

    # ── 加载已有数据（增量模式） ──────────────────────────────────────────────
    existing: Dict[str, dict] = {}
    if os.path.exists(OUTPUT):
        try:
            for p in json.load(open(OUTPUT, encoding="utf-8")):
                existing[p["id"]] = p
            print(f"Loaded {len(existing)} existing papers from {OUTPUT}")
        except Exception as e:
            print(f"[warn] could not load existing: {e}")

    total_new = 0

    # ════════════════════════════════════════════════════════════════════════
    # 阶段 A：OpenAlex 期刊 + AAAI
    # ════════════════════════════════════════════════════════════════════════
    if oa_venues:
        connector_oa = aiohttp.TCPConnector(limit=OA_CONCURRENCY * 2)
        async with aiohttp.ClientSession(connector=connector_oa) as session:

            # A1：并行解析 Source ID
            print(f"\n[A1] Resolving OpenAlex Source IDs for {len(oa_venues)} venues…")
            id_tasks = {
                name: asyncio.create_task(resolve_source_id(session, name))
                for name in oa_venues
            }
            source_ids: Dict[str, str] = {}
            for name, task in id_tasks.items():
                sid = await task
                if sid:
                    source_ids[name] = sid
                else:
                    print(f"  [skip] {name}: Source ID not found")

            # A2：并行抓取
            print(f"\n[A2] Fetching OpenAlex papers (concurrency={OA_CONCURRENCY})…")
            sem_oa = asyncio.Semaphore(OA_CONCURRENCY)

            async def fetch_oa(name: str, cfg: dict, sid: str) -> None:
                nonlocal total_new
                async with sem_oa:
                    t0 = time.time()
                    papers = await fetch_venue(session, name, cfg, sid, year_from)
                    elapsed = time.time() - t0
                    new = _merge_papers(existing, papers)
                    total_new += new
                    print(f"  ✓ {name:30s} {len(papers):5d} papers  ({new:4d} new)  {elapsed:.1f}s")

            await asyncio.gather(*[
                fetch_oa(name, oa_venues[name], sid)
                for name, sid in source_ids.items()
            ])

    # ════════════════════════════════════════════════════════════════════════
    # 阶段 B：Semantic Scholar 顶会
    # ════════════════════════════════════════════════════════════════════════
    if s2_venues_:
        connector_s2 = aiohttp.TCPConnector(limit=S2_CONCURRENCY * 2)
        async with aiohttp.ClientSession(connector=connector_s2) as session:

            print(f"\n[B] Fetching S2 conference papers (concurrency={S2_CONCURRENCY})…")
            sem_s2 = asyncio.Semaphore(S2_CONCURRENCY)

            async def fetch_s2(name: str, cfg: dict) -> None:
                nonlocal total_new
                async with sem_s2:
                    t0 = time.time()
                    papers = await fetch_s2_venue(session, name, cfg, year_from)
                    elapsed = time.time() - t0
                    new = _merge_papers(existing, papers)
                    total_new += new
                    print(f"  ✓ {name:30s} {len(papers):5d} papers  ({new:4d} new)  {elapsed:.1f}s")

            await asyncio.gather(*[
                fetch_s2(name, s2_venues_[name])
                for name in s2_venues_
            ])

    # ── 统计摘要 ─────────────────────────────────────────────────────────────
    all_papers = sorted(
        existing.values(),
        key=lambda p: p.get("citation_count", 0),
        reverse=True,
    )
    domain_counts = Counter(d for p in all_papers for d in (p.get("_domains") or []))
    venue_counts  = Counter(p.get("venue") for p in all_papers if p.get("venue"))

    print(f"\n{'='*60}")
    print(f"Total: {len(all_papers)} papers  ({total_new} new)")
    print(f"By domain: {dict(domain_counts)}")
    print(f"Top venues: {venue_counts.most_common(10)}")

    if dry_run:
        print("[dry-run] File not written.")
        return

    # ── 写出 ─────────────────────────────────────────────────────────────────
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUTPUT)
    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"Wrote {len(all_papers)} papers → {OUTPUT} ({size_mb:.2f} MB)")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    all_venue_names = list(ALL_VENUES) + list(S2_VENUES)
    ap = argparse.ArgumentParser(
        description="Paperscope 精选论文快速抓取器（OpenAlex + Semantic Scholar 双源异步版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例：
  python fetch_curated_fast.py --year-from 2023          # 首次全量（约 20-60 分钟）
  python fetch_curated_fast.py --year-from 2026          # 每月增量（约 3-10 分钟）
  python fetch_curated_fast.py --year-from 2023 --venue NeurIPS   # 单 venue 调试
  python fetch_curated_fast.py --year-from 2023 --venue CVPR
  python fetch_curated_fast.py --year-from 2023 --dry-run

OpenAlex 期刊/AAAI ({len(ALL_VENUES)} 个):
  {', '.join(ALL_VENUES)}

Semantic Scholar 顶会 ({len(S2_VENUES)} 个):
  {', '.join(S2_VENUES)}
        """,
    )
    ap.add_argument(
        "--year-from", type=int, default=date.today().year - 1,
        help="起始年份（默认：去年）"
    )
    ap.add_argument(
        "--venue", default=None,
        help=f"只抓单个 venue（调试用）。可选: {', '.join(all_venue_names)}"
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="只统计，不写文件"
    )
    ap.add_argument(
        "--oa-only", action="store_true",
        help="只跑 OpenAlex（跳过 Semantic Scholar）"
    )
    ap.add_argument(
        "--s2-only", action="store_true",
        help="只跑 Semantic Scholar 顶会（跳过 OpenAlex）"
    )
    args = ap.parse_args()

    # 处理 --oa-only / --s2-only（修改 venue_filter 实现）
    if args.oa_only and args.s2_only:
        print("--oa-only 和 --s2-only 不能同时使用")
        sys.exit(1)

    print(f"Paperscope 精选抓取器 v4（OpenAlex + Semantic Scholar）")
    print(f"  年份范围   : {args.year_from} → {date.today().year}")
    print(f"  Venue 范围 : {args.venue or f'全部 ({len(all_venue_names)} 个)'}")
    print(f"  OpenAlex   : {'跳过' if args.s2_only else f'{OA_CONCURRENCY} 并发，每页 {OA_PER_PAGE} 条'}")
    print(f"  S2 顶会    : {'跳过' if args.oa_only else f'{S2_CONCURRENCY} 并发，每页 {S2_PER_PAGE} 条'}")
    print(f"  输出文件   : {OUTPUT}\n")

    asyncio.run(run(
        year_from=args.year_from,
        venue_filter=args.venue,
        dry_run=args.dry_run,
        oa_only=args.oa_only,
        s2_only=args.s2_only,
    ))


if __name__ == "__main__":
    main()
