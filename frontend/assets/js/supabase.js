// 轻量 Supabase REST 封装 (避免引入完整 SDK，保持前端体积小)。
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";

async function restGet(path, params = {}) {
  const url = new URL(`${SUPABASE_URL}/rest/v1/${path}`);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const r = await fetch(url, {
    headers: {
      apikey: SUPABASE_ANON_KEY,
      Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
    },
  });
  if (!r.ok) throw new Error(`Supabase ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function listPapers({
  mode = "feed", domain = "all", source = [], year = "",
  paperType = [], sortBy = "published_at", limit = 50, offset = 0, search = "",
  tier = "", venue = "",
} = {}) {
  const params = {
    select: "*",
    order: `${sortBy}.desc.nullslast`,
    limit: String(limit),
    offset: String(offset),
  };
  // mode: feed=arxiv, curated=s2+pubmed
  if (mode === "feed") params.source = "eq.arxiv";
  else if (mode === "curated") params.source = "in.(s2,pubmed)";

  if (source.length) params.source = `in.(${source.join(",")})`;
  if (domain !== "all") params.domains = `cs.{${domain}}`;
  if (year) params.year = `eq.${year}`;
  if (paperType.length) params.paper_type = `in.(${paperType.join(",")})`;
  if (search) params.title = `ilike.*${search}*`;
  if (tier)  params.venue_tier = `eq.${tier}`;
  if (venue) params.venue = `eq.${venue}`;

  return restGet("papers", params);
}

// 获取精选论文中的 venue 列表（按 tier 过滤），用于下拉联动
export async function listVenues(tier = "") {
  const params = {
    select: "venue,venue_tier",
    source: "in.(s2,pubmed)",
    limit: "1000",
    "venue": "not.is.null",
  };
  if (tier) params.venue_tier = `eq.${tier}`;
  const rows = await restGet("papers", params);
  // 按 tier 分组，统计每个 venue 的数量
  const map = {};
  rows.forEach(r => {
    if (!r.venue) return;
    if (!map[r.venue]) map[r.venue] = { venue: r.venue, tier: r.venue_tier, count: 0 };
    map[r.venue].count++;
  });
  return Object.values(map).sort((a, b) => b.count - a.count);
}

export async function getPaper(id) {
  const rows = await restGet("papers", { select: "*", id: `eq.${id}`, limit: 1 });
  return rows[0] || null;
}
