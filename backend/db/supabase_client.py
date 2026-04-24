"""Supabase 客户端封装。

用服务端 KEY (service_role) 做写入，前端用 anon key。
"""

from __future__ import annotations
import os
from functools import lru_cache
from supabase import Client, create_client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> Client:
    """后端服务用的 client，使用 service_role key (绕过 RLS)。"""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY 未设置 (检查 .env)")
    return create_client(url, key)


def upsert_papers(papers: list[dict], chunk: int = 500) -> int:
    """批量写入/更新 papers 表。返回写入条数。"""
    if not papers:
        return 0
    client = get_client()
    total = 0
    for i in range(0, len(papers), chunk):
        batch = papers[i : i + chunk]
        client.table("papers").upsert(batch, on_conflict="id").execute()
        total += len(batch)
    return total


def snapshot_stats(rows: list[dict]) -> int:
    """写入每周引用快照 (paper_id, snapshot_date, citation_count)。"""
    if not rows:
        return 0
    client = get_client()
    client.table("paper_stats").upsert(
        rows, on_conflict="paper_id,snapshot_date"
    ).execute()
    return len(rows)
