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
} = {}) {
  const params = {
    select: "*",
    order: `${sortBy}.desc.nullslast`,
    limit: String(limit),
    offset: String(offset),
  };
  // mode: feed=arxiv, curated=s2+pubmed, trending 在别的 endpoint
  if (mode === "feed") params.source = "eq.arxiv";
  else if (mode === "curated") params.source = "in.(s2,pubmed)";

  if (source.length) params.source = `in.(${source.join(",")})`;
  if (domain !== "all") params.domains = `cs.{${domain}}`;
  if (year) params.year = `eq.${year}`;
  if (paperType.length) params.paper_type = `in.(${paperType.join(",")})`;
  if (search) params.title = `ilike.*${search}*`;

  return restGet("papers", params);
}

export async function getPaper(id) {
  const rows = await restGet("papers", { select: "*", id: `eq.${id}`, limit: 1 });
  return rows[0] || null;
}
