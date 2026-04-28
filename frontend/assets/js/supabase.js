// 轻量 Supabase REST 封装 (避免引入完整 SDK，保持前端体积小)。
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js";

// ==================== Auth ====================

const AUTH_STORAGE_KEY = "paperscope_session";

/** 从 localStorage 读取当前 session */
export function getStoredSession() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || "null");
  } catch { return null; }
}

/** 持久化 session */
function saveSession(session) {
  if (session) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  } else {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }
  _notifyAuthChange(session ? session.user : null);
}

/** 内部 auth 状态变更通知 */
const _authListeners = [];
function _notifyAuthChange(user) {
  _authListeners.forEach(fn => fn(user));
}

/** 注册 auth 状态变更回调（用户登入/登出时触发） */
export function onAuthStateChange(callback) {
  _authListeners.push(callback);
  // 立即触发一次，传递当前状态
  const sess = getStoredSession();
  callback(sess ? sess.user : null);
}

/**
 * 邮箱 + 密码登录
 * @returns {user, access_token, ...}
 */
export async function signInWithEmail(email, password) {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: SUPABASE_ANON_KEY,
    },
    body: JSON.stringify({ email, password }),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error_description || data.msg || "登录失败");
  saveSession(data);
  return data;
}

/**
 * 邮箱注册
 */
export async function signUpWithEmail(email, password) {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: SUPABASE_ANON_KEY,
    },
    body: JSON.stringify({ email, password }),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error_description || data.msg || "注册失败");
  if (data.access_token) saveSession(data);
  return data;
}

/**
 * GitHub OAuth —— 跳转到 Supabase 授权页面
 * 授权成功后 GitHub 会回调到 redirect_to，带上 #access_token=...
 */
export function signInWithGitHub() {
  const redirectTo = encodeURIComponent(window.location.origin + window.location.pathname);
  window.location.href = `${SUPABASE_URL}/auth/v1/authorize?provider=github&redirect_to=${redirectTo}`;
}

/**
 * 登出
 */
export async function signOut() {
  const sess = getStoredSession();
  if (sess?.access_token) {
    await fetch(`${SUPABASE_URL}/auth/v1/logout`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${sess.access_token}`,
      },
    }).catch(() => {});
  }
  saveSession(null);
}

/**
 * 处理 OAuth 回调：页面 URL hash 里含 access_token 时调用
 * 返回解析到的 session 或 null
 */
export function handleOAuthCallback() {
  const hash = window.location.hash.slice(1);
  if (!hash) return null;
  const params = Object.fromEntries(hash.split("&").map(p => p.split("=")));
  if (!params.access_token) return null;

  // 构造 session 对象
  const session = {
    access_token: params.access_token,
    refresh_token: params.refresh_token || "",
    token_type: params.token_type || "bearer",
    expires_in: Number(params.expires_in || 3600),
    user: params.user ? JSON.parse(decodeURIComponent(params.user)) : null,
  };

  // 如果没有 user 字段，用 access_token 去拉用户信息
  if (!session.user) {
    fetch(`${SUPABASE_URL}/auth/v1/user`, {
      headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${session.access_token}` },
    })
      .then(r => r.json())
      .then(u => { session.user = u; saveSession(session); })
      .catch(() => {});
  }

  saveSession(session);
  // 清掉 URL hash，避免刷新后重复处理
  history.replaceState(null, "", window.location.pathname + window.location.search);
  return session;
}

// ==================== REST helpers ====================

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

// 仅取行数，不拉数据。利用 PostgREST 的 Content-Range header
async function restCount(path, params = {}) {
  const url = new URL(`${SUPABASE_URL}/rest/v1/${path}`);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  url.searchParams.set("select", "id");
  url.searchParams.set("limit", "1");
  const r = await fetch(url, {
    headers: {
      apikey: SUPABASE_ANON_KEY,
      Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
      Prefer: "count=exact",
    },
  });
  if (!r.ok) throw new Error(`Supabase ${r.status}: ${await r.text()}`);
  const cr = r.headers.get("Content-Range") || "0-0/0";
  return parseInt(cr.split("/")[1], 10) || 0;
}

export async function listPapers({
  mode = "feed", domain = "all", source = [], year = "",
  paperType = [], sortBy = "published_at", limit = 50, offset = 0, search = "",
  tier = "", venue = "", hasCode = false, task = "",
} = {}) {
  const params = {
    select: "*",
    order: `${sortBy}.desc.nullslast`,
    limit: String(limit),
    offset: String(offset),
  };
  if (mode === "feed") params.source = "eq.arxiv";
  else if (mode === "curated") params.source = "in.(s2,pubmed)";

  if (source.length) params.source = `in.(${source.join(",")})`;
  if (domain !== "all") params.domains = `cs.{${domain}}`;
  if (year) params.year = `eq.${year}`;
  if (paperType.length) params.paper_type = `in.(${paperType.join(",")})`;
  if (search) params.title = `ilike.*${search}*`;
  if (tier)  params.venue_tier = `eq.${tier}`;
  if (venue) params.venue = `eq.${venue}`;
  if (hasCode) params.code_links = "neq.{}";
  if (task) params.tasks = `cs.{${task}}`;

  return restGet("papers", params);
}

// 速览仪表盘：4 张统计卡 + 年份×领域 趋势
export async function fetchDashboardStats() {
  const baseFeed = { source: "eq.arxiv" };
  const domains = ["world_model", "physical_ai", "medical_ai"];
  const years = [2023, 2024, 2025, 2026];

  const totalP = restCount("papers", baseFeed);
  const domainCountsP = Promise.all(
    domains.map(d => restCount("papers", { ...baseFeed, domains: `cs.{${d}}` }))
  );
  const recentP = restCount("papers", {
    ...baseFeed,
    published_at: `gte.${new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10)}`,
  });
  const recentDomainP = Promise.all(
    domains.map(d => restCount("papers", {
      ...baseFeed,
      domains: `cs.{${d}}`,
      published_at: `gte.${new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10)}`,
    }))
  );
  const trendsP = Promise.all(
    years.flatMap(y => domains.map(d =>
      restCount("papers", { ...baseFeed, year: `eq.${y}`, domains: `cs.{${d}}` })
        .then(count => ({ year: y, domain: d, count }))
    ))
  );

  const [total, domainCounts, recentTotal, recentDomain, trendsFlat] =
    await Promise.all([totalP, domainCountsP, recentP, recentDomainP, trendsP]);

  const trends = years.map(y => ({
    year: y,
    counts: Object.fromEntries(domains.map((d, i) => [d, trendsFlat.find(t => t.year === y && t.domain === d)?.count || 0])),
  }));

  return {
    total,
    domains: Object.fromEntries(domains.map((d, i) => [d, domainCounts[i]])),
    recent: {
      total: recentTotal,
      domains: Object.fromEntries(domains.map((d, i) => [d, recentDomain[i]])),
    },
    trends,
  };
}

// 取热门 task 标签：随机抽样近期论文，前端聚合
export async function fetchTrendingTopics(domain = null, limit = 5) {
  const params = {
    select: "tasks,domains",
    source: "eq.arxiv",
    limit: "500",
    order: "published_at.desc.nullslast",
  };
  if (domain) params.domains = `cs.{${domain}}`;
  const rows = await restGet("papers", params);
  const counter = {};
  rows.forEach(r => (r.tasks || []).forEach(t => { counter[t] = (counter[t] || 0) + 1; }));
  return Object.entries(counter)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
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
