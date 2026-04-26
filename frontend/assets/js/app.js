import { listPapers, getPaper, listVenues, fetchDashboardStats, fetchTrendingTopics } from "./supabase.js";
import { S2_PAPER_API, DOMAINS } from "./config.js";

const state = {
  mode: "feed",
  domain: "all",
  source: [],
  year: "",
  paperType: [],
  sortBy: "published_at",
  search: "",
  tier: "",
  venue: "",
  hasCode: false,
  task: "",
  month: "",
  favorites: false,
};

// 收藏存储
let favorites = new Set(JSON.parse(localStorage.getItem("paperscope_favs") || "[]"));
function saveFavorites() {
  localStorage.setItem("paperscope_favs", JSON.stringify([...favorites]));
  updateFavCount();
}
function updateFavCount() {
  const el = document.querySelector("#fav-count");
  if (el) el.textContent = favorites.size;
  const el2 = document.querySelector("#fav-modal-count");
  if (el2) el2.textContent = favorites.size;
}

// 静态 arxiv 数据 (速览模式)
let feedPapersCache = null;
async function loadFeedPapers() {
  if (feedPapersCache) return feedPapersCache;
  const r = await fetch("data/papers.json");
  if (!r.ok) throw new Error("papers.json 加载失败");
  feedPapersCache = await r.json();
  return feedPapersCache;
}

const $ = (sel) => document.querySelector(sel);

// ========== 精选模式 UI 切换 ==========
function setCuratedMode(on) {
  document.body.classList.toggle("mode-curated", on);
  if (on) {
    state.sortBy = "citation_count";
    $("#sort-by").value = "citation_count";
    refreshVenueList();
    renderVenuePicker(state.domain);
  } else {
    state.tier = "";
    state.venue = "";
    state.sortBy = "published_at";
    $("#filter-tier").value = "";
    $("#sort-by").value = "published_at";
    $("#filter-venue").innerHTML = '<option value="">全部</option>';
  }
}

// ========== 精选主区域：领域 × 期刊会议选择器 ==========
async function renderVenuePicker(domain) {
  const body = $("#venue-picker-body");
  if (!body) return;
  // 同步 domain 按钮高亮
  document.querySelectorAll(".vpd-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.domain === domain));

  const catalog = await loadVenuesByDomain();
  const domains = domain === "all"
    ? ["world_model", "physical_ai", "medical_ai"]
    : [domain];

  // 取已有入库数量
  let counts = {};
  try {
    const list = await listVenues("");
    counts = Object.fromEntries(list.map(v => [v.venue, v.count]));
  } catch {}

  let html = "";
  domains.forEach(d => {
    const groups = catalog[d] || [];
    if (!groups.length) return;
    if (domain === "all") {
      const dm = DOMAINS[d] || {};
      html += `<div class="vpc-domain-title ${d}">${dm.icon || ""} ${dm.label || d}</div>`;
    }
    groups.forEach(g => {
      html += `<div class="vpc-group">
        <div class="vpc-category">${esc(g.category)}</div>
        <div class="vpc-chips">
          ${g.venues.map(v => {
            const cnt = counts[v] || 0;
            const active = state.venue === v ? "active" : "";
            const hasCnt = cnt > 0;
            return `<button class="vpc-chip ${active} ${hasCnt ? "has-papers" : ""}" data-venue="${esc(v)}" data-domain="${d}" title="${esc(v)} · ${hasCnt ? cnt + " 篇" : "暂无数据"}">
              ${esc(v)}${hasCnt ? `<span class="vpc-cnt">${cnt}</span>` : ""}
            </button>`;
          }).join("")}
        </div>
      </div>`;
    });
  });
  body.innerHTML = html || `<div class="loading">暂无数据</div>`;
}



let venuesByDomainCache = null;
async function loadVenuesByDomain() {
  if (venuesByDomainCache) return venuesByDomainCache;
  try {
    venuesByDomainCache = await fetch("data/venues_by_domain.json").then(r => r.json());
  } catch { venuesByDomainCache = {}; }
  return venuesByDomainCache;
}

async function refreshVenueList() {
  const sel = $("#filter-venue");
  sel.innerHTML = '<option value="">全部期刊/会议</option>';
  const catalog = await loadVenuesByDomain();
  // 取实际数据库里有论文的 venue → 计数（用于在选项中标注篇数）
  let counts = {};
  try {
    const venuesWithCounts = await listVenues(state.tier);
    counts = Object.fromEntries(venuesWithCounts.map(v => [v.venue, v.count]));
  } catch (e) { console.warn("listVenues failed:", e); }

  // 决定要展示的领域分组：state.domain==='all' 时合并三个领域
  const domains = state.domain === "all"
    ? ["world_model", "physical_ai", "medical_ai"]
    : [state.domain];

  domains.forEach(d => {
    const groups = catalog[d] || [];
    if (state.domain === "all" && groups.length) {
      const header = document.createElement("optgroup");
      header.label = `── ${DOMAINS[d]?.label || d} ──`;
      header.disabled = true;
      sel.appendChild(header);
    }
    groups.forEach(g => {
      const og = document.createElement("optgroup");
      og.label = g.category;
      g.venues.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v;
        const c = counts[v];
        opt.textContent = c ? `${v} (${c})` : v;
        if (v === state.venue) opt.selected = true;
        og.appendChild(opt);
      });
      sel.appendChild(og);
    });
  });
}

// ========== 渲染论文列表 ==========
function render(papers) {
  const list = $("#paper-list");
  if (!papers.length) {
    list.innerHTML = `<div class="loading">暂无论文</div>`;
    return;
  }
  list.innerHTML = papers.map(paperCard).join("");
  list.querySelectorAll(".paper-card").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".fav-btn")) return;
      openDetail(el.dataset.id);
    });
  });
  list.querySelectorAll(".fav-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.fav;
      if (favorites.has(id)) { favorites.delete(id); btn.classList.remove("active"); btn.textContent = "☆"; }
      else { favorites.add(id); btn.classList.add("active"); btn.textContent = "★"; }
      saveFavorites();
      if (state.favorites) reload();
    });
  });
}

function normalizePaper(p) {
  const domains = p._domains || p.domains || [];
  const tasks = p._tasks || p.tasks || [];
  const type = p.type || p.paper_type || "";
  const authors = (p.authors || []).map(a => typeof a === "string" ? a : (a.name || ""));
  const hasCode = p.has_code === true || (p.code_links && p.code_links.length > 0) || !!p.code;
  const codeUrl = p.code || (p.code_links && p.code_links[0]) || "";
  const pdfUrl = p.pdf_url || p.open_access_pdf || "";
  const arxivUrl = p.arxiv_url || "";
  const dateStr = p.published || p.published_at || "";
  const month = p.month || (dateStr ? Number(dateStr.slice(5, 7)) : null);
  const abs = p.abstract_excerpt || p.abstract || "";
  return { ...p, _n: { domains, tasks, type, authors, hasCode, codeUrl, pdfUrl, arxivUrl, month, abs, dateStr } };
}

function paperCard(p) {
  const n = p._n || normalizePaper(p)._n;
  const tierCls = (p.venue_tier || "").toLowerCase().replace(/[\s·]/g, "-");
  const primaryDomain = n.domains[0] || "";
  const authorStr = n.authors.slice(0, 3).join(", ");
  const moreAuthors = n.authors.length > 3 ? ` · +${n.authors.length - 3}` : "";
  const taskTags = n.tasks.slice(0, 4).map((t) => `<span class="task-tag">${esc(tn(t))}</span>`).join("");
  const cite = p.citation_count > 0 ? `<span class="citation">📊 ${p.citation_count}</span>` : "";
  const absHtml = n.abs ? `<p class="paper-abstract">${esc(n.abs.slice(0, 240))}${n.abs.length > 240 ? "…" : ""}</p>` : "";

  const domainBadges = n.domains.map(d => {
    const meta = DOMAINS[d];
    if (!meta) return "";
    return `<span class="paper-domain-badge ${d}">${meta.icon} ${meta.label}</span>`;
  }).join("");
  const typeBadge = n.type ? `<span class="paper-type ${esc(n.type)}">${esc(n.type)}</span>` : "";
  const fav = favorites.has(p.id);

  return `<article class="paper-card domain-${primaryDomain}" data-id="${p.id}">
    <button class="fav-btn${fav ? " active" : ""}" data-fav="${p.id}" title="收藏">${fav ? "★" : "☆"}</button>
    <div class="paper-domains">${domainBadges}${typeBadge}</div>
    <h3 class="paper-title">${esc(p.title)}</h3>
    <div class="paper-meta">
      ${p.venue ? `<span class="venue-badge tier-${tierCls}">${esc(p.venue)}</span>` : ""}
      ${n.dateStr ? `<span class="paper-date" title="发表日期">📅 ${esc(n.dateStr.slice(0, 10))}</span>` : (p.year ? `<span>${p.year}</span>` : "")}
      ${cite}
      ${n.pdfUrl ? `<a class="meta-link" href="${esc(n.pdfUrl)}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="开放获取 PDF">🔓 PDF</a>` : ""}
      ${n.hasCode && n.codeUrl ? `<a class="meta-link code-link" href="${esc(n.codeUrl)}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="开源代码">💻 Code</a>` : (n.hasCode ? `<span title="有开源代码">💻</span>` : "")}
    </div>
    <div class="paper-authors">${esc(authorStr)}${moreAuthors}</div>
    ${absHtml}
    ${taskTags ? `<div class="paper-tasks">${taskTags}</div>` : ""}
  </article>`;
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

// ========== 详情面板 ==========
async function openDetail(id) {
  const panel = $("#detail-panel");
  const body = panel.querySelector(".detail-body");
  $(".layout").classList.add("has-detail");
  panel.hidden = false;
  body.innerHTML = `<div class="loading">加载详情...</div>`;

  let paper = null;
  if (state.mode === "feed" && feedPapersCache) {
    paper = feedPapersCache.find(x => x.id === id) || null;
    if (paper) paper = normalizePaper(paper);
  }
  if (!paper) paper = await getPaper(id);
  if (!paper) { body.innerHTML = "论文不存在"; return; }
  const n = paper._n || normalizePaper(paper)._n;
  const fullAbstract0 = paper.abstract || paper.abstract_excerpt || n.abs || "";
  const authorsStr = n.authors.join(", ");

  let refs = null, cites = null, fullAbstract = fullAbstract0;
  if (paper.source === "s2") {
    try {
      const s2 = await fetch(`${S2_PAPER_API}/${paper.source_id}?fields=abstract,references.paperId,references.title,references.citationCount,citations.paperId,citations.title,citations.citationCount`).then(r => r.json());
      fullAbstract = s2.abstract || fullAbstract;
      refs = (s2.references || []).slice(0, 5);
      cites = (s2.citations || []).slice(0, 5);
    } catch {}
  }

  body.innerHTML = `
    <h2>${esc(paper.title)}</h2>
    <p><strong>${esc(paper.venue || "")}</strong> · ${paper.year || ""} ${paper.citation_count ? `· 📊 ${paper.citation_count} 引用` : ""}</p>
    ${n.pdfUrl ? `<p><a href="${n.pdfUrl}" target="_blank">🔓 打开 PDF</a></p>` : ""}
    ${n.arxivUrl ? `<p><a href="${n.arxivUrl}" target="_blank">arXiv 原文</a></p>` : ""}
    ${n.codeUrl ? `<p><a href="${n.codeUrl}" target="_blank">💻 代码</a></p>` : ""}
    <h4>摘要</h4>
    <p>${esc(fullAbstract)}</p>
    <h4>作者</h4>
    <p>${esc(authorsStr)}</p>
    ${refs?.length ? `<h4>主要参考文献</h4><ul class="refs-list">${refs.map(r => `<li>${esc(r.title)} · ${r.citationCount || 0} 引用</li>`).join("")}</ul>` : ""}
    ${cites?.length ? `<h4>被引重要论文</h4><ul class="refs-list">${cites.map(r => `<li>${esc(r.title)} · ${r.citationCount || 0} 引用</li>`).join("")}</ul>` : ""}
  `;
}

// ========== 仪表盘 (速览模式) ==========
let dashboardLoaded = false;
let trendingData = {};        // { world_model: [...], physical_ai: [...], medical_ai: [...] }
let taskMeta = {};            // { Task: {zh, en} }
let domainTasks = {           // fallback
  world_model: ["VidGen", "NeRF", "MBRL", "Sim2Real", "EmbodiedWM", "Predictive"],
  physical_ai: ["PINN", "NeuralOp", "Embodied", "RobotLearn", "FluidSim", "Climate", "3DRecon"],
  medical_ai:  ["Pathology", "MedImg", "Cancer", "MedVLM", "DrugMol", "Protein", "Clinical", "Surgery", "HealthMon"],
};
let hotDomain = "world_model";
let hotExpanded = false;

function tn(task) {
  const m = taskMeta[task];
  return m ? (m.zh || m.en || task) : task;
}

async function loadStaticData() {
  try {
    const [tr, tm] = await Promise.all([
      fetch("data/trending.json").then(r => r.ok ? r.json() : null),
      fetch("data/task_meta.json").then(r => r.ok ? r.json() : null),
    ]);
    if (tr?.trends) trendingData = tr.trends;
    if (tm?.tasks) taskMeta = tm.tasks;
    if (tm?.domain_tasks && Object.keys(tm.domain_tasks).length) domainTasks = tm.domain_tasks;
  } catch (e) {
    console.warn("static data load failed:", e);
  }
}

async function loadDashboard() {
  if (dashboardLoaded) return;
  dashboardLoaded = true;
  await loadStaticData();
  renderHotTopics(hotDomain);
  try {
    const papers = await loadFeedPapers();
    const stats = computeStaticStats(papers);
    renderStats(stats);
    renderTrends(stats.trends);
    renderSubdomain();
  } catch (e) {
    console.warn("dashboard stats failed:", e);
  }
}

function computeStaticStats(papers) {
  const domains = ["world_model", "physical_ai", "medical_ai"];
  const years = [2023, 2024, 2025, 2026];
  const recentCutoff = Date.now() - 7 * 864e5;
  const stats = {
    total: papers.length,
    domains: Object.fromEntries(domains.map(d => [d, 0])),
    recent: { total: 0, domains: Object.fromEntries(domains.map(d => [d, 0])) },
    trends: years.map(y => ({ year: y, counts: Object.fromEntries(domains.map(d => [d, 0])) })),
  };
  for (const p of papers) {
    const ds = p._domains || [];
    const isRecent = p.published && new Date(p.published).getTime() >= recentCutoff;
    if (isRecent) stats.recent.total++;
    for (const d of ds) {
      if (stats.domains[d] != null) stats.domains[d]++;
      if (isRecent && stats.recent.domains[d] != null) stats.recent.domains[d]++;
    }
    const tr = stats.trends.find(t => t.year === p.year);
    if (tr) for (const d of ds) if (tr.counts[d] != null) tr.counts[d]++;
  }
  return stats;
}

function renderStats(s) {
  const fmt = (n) => n.toLocaleString("en-US");
  const dash = $("#dashboard");
  const setCard = (key, value, recent) => {
    const card = dash.querySelector(`.stat-card[data-key="${key}"]`);
    if (!card) return;
    card.querySelector(".stat-value").textContent = fmt(value);
    const old = card.querySelector(".new-badge");
    if (old) old.remove();
    if (recent > 0) {
      const b = document.createElement("div");
      b.className = "new-badge";
      b.textContent = `+${recent}`;
      card.appendChild(b);
    }
  };
  setCard("total", s.total, s.recent.total);
  ["world_model", "physical_ai", "medical_ai"].forEach(d => {
    setCard(d, s.domains[d], s.recent.domains[d]);
  });
}

function renderTrends(trends) {
  const max = Math.max(1, ...trends.map(t => Object.values(t.counts).reduce((a, b) => a + b, 0)));
  const legend = `<div class="trend-legend">
    ${["world_model", "physical_ai", "medical_ai"].map(d =>
      `<span class="trend-legend-item"><span class="trend-legend-dot ${d}"></span>${DOMAINS[d]?.icon || ""} ${DOMAINS[d]?.label || d}</span>`
    ).join("")}
  </div>`;
  const rowsHtml = trends.map(t => {
    const total = Object.values(t.counts).reduce((a, b) => a + b, 0);
    const bars = ["world_model", "physical_ai", "medical_ai"].map(d => {
      const w = max > 0 ? (t.counts[d] / max * 100) : 0;
      return w > 0 ? `<div class="trend-bar ${d}" style="width:${w}%" title="${DOMAINS[d]?.label || d}: ${t.counts[d]} 篇"></div>` : "";
    }).join("");
    return `<div class="trend-row">
      <span class="trend-year-label">${t.year}</span>
      <div class="trend-bars">${bars}</div>
      <span class="trend-count">${total.toLocaleString("en-US")}</span>
    </div>`;
  }).join("");
  $("#chart-trends").innerHTML = (rowsHtml ? legend + rowsHtml : `<div class="loading">暂无数据</div>`);
}

function renderHotTopics(domain) {
  hotDomain = domain;
  const items = (trendingData[domain] || []).map(t => ({
    name: t.display || t.term, count: t.count, desc: t.description || ""
  }));
  const tabsHtml = `<div class="hot-tabs">
    ${["world_model", "physical_ai", "medical_ai"].map(d =>
      `<button class="hot-tab ${d === domain ? "active" : ""}" data-domain="${d}">${DOMAINS[d]?.label || d}</button>`
    ).join("")}
  </div>`;
  if (!items.length) {
    $("#chart-trending").innerHTML = tabsHtml + `<div class="loading">暂无数据</div>`;
    return;
  }
  const max = Math.max(...items.map(i => i.count), 1);
  const TOP = 4;
  const visible = hotExpanded ? items : items.slice(0, TOP);
  const itemsHtml = visible.map((it, i) => {
    const rank = i < 3 ? `rank-${i + 1}` : "rank-other";
    const w = (it.count / max * 100).toFixed(0);
    const tip = it.desc ? `title="${esc(it.desc)}"` : "";
    return `<div class="hot-item" ${tip}>
      <div class="hot-rank ${rank}">${i + 1}</div>
      <div class="hot-name">${esc(it.name)}</div>
      <div class="hot-bar-wrap"><div class="hot-bar ${domain}" style="width:${w}%"></div></div>
      <div class="hot-count">${it.count}</div>
    </div>`;
  }).join("");
  const more = items.length > TOP
    ? `<button class="hot-show-all" id="hot-show-all">${hotExpanded ? "收起 ↑" : `查看全部 ${items.length} 个 ↓`}</button>`
    : "";
  $("#chart-trending").innerHTML = tabsHtml + itemsHtml + more;
}

function renderSubdomain() {
  const sec = $("#subdomain-section");
  if (state.domain === "all") {
    sec.hidden = false;
    sec.innerHTML = `<div class="subdomain-hint">
      💡 点击上方 <b>🌍 World Model</b> / <b>🤖 Physical AI</b> / <b>🏥 Medical AI</b> 任一领域 tab，<b>或直接点击下方统计卡片</b>，可展开查看该方向的细分主题与本周新增
    </div>`;
    return;
  }
  sec.hidden = false;
  const d = state.domain;
  const meta = DOMAINS[d] || {};
  const papers = feedPapersCache || [];
  const weekAgo = Date.now() - 7 * 864e5;
  const tasks = domainTasks[d] || [];
  const pool = papers.filter(p => (p._domains || []).includes(d));
  const items = tasks.map(task => {
    let total = 0, fresh = 0;
    pool.forEach(p => {
      if ((p._tasks || []).includes(task)) {
        total++;
        if (p.published && new Date(p.published).getTime() >= weekAgo) fresh++;
      }
    });
    return { task, total, fresh };
  }).filter(x => x.total > 0).sort((a, b) => b.total - a.total);

  const itemsHtml = items.map(({ task, total, fresh }) => {
    const m = taskMeta[task] || {};
    const tip = `${m.zh || task}${m.en ? " · " + m.en : ""}（${total} 篇${fresh ? "，本周新增 " + fresh : ""}）`;
    const active = state.task === task ? "active" : "";
    const badge = fresh > 0 ? `<span class="new-badge">+${fresh}</span>` : "";
    return `<div class="subdomain-item ${active} ${d}" data-task="${esc(task)}" title="${esc(tip)}">
      <span class="name">${esc(tn(task))}</span>
      <span class="count">${total}</span>${badge}
    </div>`;
  }).join("");

  sec.innerHTML = `
    <div class="subdomain-title">
      <span class="subdomain-domain-tag ${d}">${meta.icon || ""} ${meta.label || d}</span>
      <span class="subdomain-sub">细分方向 · 共 ${items.length} 个主题 · 悬停查看说明</span>
      ${state.task ? `<button class="subdomain-clear" id="subdomain-clear">清除筛选 ✕</button>` : ""}
    </div>
    <div class="subdomain-grid" id="subdomain-grid">${itemsHtml || '<div class="loading">暂无数据</div>'}</div>
  `;
}

// ========== 速览模式：本地过滤 + 排序 ==========
function applyFeedFilters(papers) {
  const s = state;
  const q = s.search.toLowerCase();
  let out = papers.filter(p => {
    const n = p._n;
    if (s.domain !== "all" && !n.domains.includes(s.domain)) return false;
    if (s.year && String(p.year) !== String(s.year)) return false;
    if (s.month && String(n.month) !== String(s.month)) return false;
    if (s.paperType.length && !s.paperType.includes(n.type)) return false;
    if (s.hasCode && !n.hasCode) return false;
    if (s.task && !n.tasks.includes(s.task)) return false;
    if (s.favorites && !favorites.has(p.id)) return false;
    if (q) {
      const hay = (p.title + " " + n.authors.join(" ") + " " + n.abs).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  out.sort((a, b) => {
    if (s.sortBy === "citation_count") return (b.citation_count || 0) - (a.citation_count || 0);
    return String(b.published || "").localeCompare(String(a.published || ""));
  });
  return out;
}

// ========== 加载数据 ==========
let feedTotal = 0;
async function reload() {
  $("#paper-list").innerHTML = `<div class="loading">加载中...</div>`;
  try {
    if (state.mode === "feed") {
      const all = (await loadFeedPapers()).map(normalizePaper);
      const filtered = applyFeedFilters(all);
      feedTotal = filtered.length;
      render(filtered.slice(0, 100));
    } else {
      const papers = await listPapers(state);
      render(papers);
    }
  } catch (e) {
    $("#paper-list").innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
  }
}

// ========== 事件绑定 ==========
document.querySelectorAll(".mode-tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".mode-tab").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    state.mode = b.dataset.mode;
    setCuratedMode(state.mode === "curated");
    reload();
  })
);

document.querySelectorAll(".domain-tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".domain-tab").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    state.domain = b.dataset.domain;
    state.task = "";
    state.venue = "";
    renderSubdomain();
    if (state.mode === "curated") { refreshVenueList(); renderVenuePicker(state.domain); }
    reload();
  })
);

// 热门话题：领域 tab 切换 + 展开
$("#chart-trending").addEventListener("click", (e) => {
  const tab = e.target.closest(".hot-tab");
  if (tab) { hotExpanded = false; renderHotTopics(tab.dataset.domain); return; }
  if (e.target.id === "hot-show-all") { hotExpanded = !hotExpanded; renderHotTopics(hotDomain); }
});

// 细分方向：点击 task 筛选 (事件委托到 section，innerHTML 重建后仍生效)
$("#subdomain-section").addEventListener("click", (e) => {
  if (e.target.closest("#subdomain-clear")) {
    state.task = ""; renderSubdomain(); reload(); return;
  }
  const item = e.target.closest(".subdomain-item");
  if (!item) return;
  const task = item.dataset.task;
  state.task = state.task === task ? "" : task;
  renderSubdomain();
  reload();
});

$(".search").addEventListener("input", (e) => {
  clearTimeout(window.__searchTimer);
  window.__searchTimer = setTimeout(() => {
    state.search = e.target.value.trim();
    reload();
  }, 300);
});

$("#filter-year").addEventListener("change", (e) => {
  state.year = e.target.value;
  document.querySelectorAll(".vpy-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.year === state.year));
  reload();
});
$("#sort-by").addEventListener("change", (e) => { state.sortBy = e.target.value; reload(); });

// 分类筛选 → 重建 venue 列表 + 重新加载
$("#filter-tier").addEventListener("change", (e) => {
  state.tier = e.target.value;
  state.venue = "";
  $("#filter-venue").value = "";
  refreshVenueList();
  reload();
});

// 期刊/会议筛选
$("#filter-venue").addEventListener("change", (e) => {
  state.venue = e.target.value;
  reload();
});

document.querySelectorAll("input[name='source']").forEach((i) =>
  i.addEventListener("change", () => {
    state.source = [...document.querySelectorAll("input[name='source']:checked")].map(x => x.value);
    reload();
  })
);
$("#filter-has-code").addEventListener("change", (e) => {
  state.hasCode = e.target.checked;
  reload();
});
$("#filter-month").addEventListener("change", (e) => { state.month = e.target.value; reload(); });
$("#filter-favorites").addEventListener("change", (e) => { state.favorites = e.target.checked; reload(); });

document.querySelectorAll("[data-switch-domain]").forEach((c) =>
  c.addEventListener("click", () => {
    const d = c.dataset.switchDomain;
    document.querySelectorAll(".domain-tab").forEach(x =>
      x.classList.toggle("active", x.dataset.domain === d));
    state.domain = d;
    state.task = "";
    renderSubdomain();
    reload();
    document.querySelector("#subdomain-section").scrollIntoView({ behavior: "smooth", block: "start" });
  })
);

document.querySelectorAll("input[name='type']").forEach((i) =>
  i.addEventListener("change", () => {
    state.paperType = [...document.querySelectorAll("input[name='type']:checked")].map(x => x.value);
    reload();
  })
);

// venue picker 事件
$("#venue-picker-domains").addEventListener("click", e => {
  const btn = e.target.closest(".vpd-btn");
  if (!btn) return;
  state.domain = btn.dataset.domain;
  state.venue = "";
  // 同步上方 domain tab
  document.querySelectorAll(".domain-tab").forEach(x =>
    x.classList.toggle("active", x.dataset.domain === state.domain));
  renderVenuePicker(state.domain);
  refreshVenueList();
  reload();
});

// 年份快选
document.querySelector("#vp-year-row")?.addEventListener("click", e => {
  const btn = e.target.closest(".vpy-btn");
  if (!btn) return;
  state.year = btn.dataset.year;
  document.querySelectorAll(".vpy-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.year === state.year));
  // 同步 sidebar year select
  $("#filter-year").value = state.year;
  reload();
});
$("#venue-picker-body").addEventListener("click", e => {
  const chip = e.target.closest(".vpc-chip");
  if (!chip) return;
  const v = chip.dataset.venue;
  state.venue = state.venue === v ? "" : v;
  // 同步 sidebar select
  $("#filter-venue").value = state.venue;
  document.querySelectorAll(".vpc-chip").forEach(c =>
    c.classList.toggle("active", c.dataset.venue === state.venue));
  reload();
});

$("#detail-close").addEventListener("click", () => {
  $(".layout").classList.remove("has-detail");
  $("#detail-panel").hidden = true;
});

// ========== 收藏汇总 Modal ==========
function openFavModal() {
  const modal = $("#fav-modal");
  const body = $("#fav-modal-body");
  modal.hidden = false;
  modal.style.display = "flex";
  updateFavCount();
  if (!favorites.size) {
    body.innerHTML = `<div class="loading">还没有收藏的论文。点击论文卡片右上角的 ☆ 进行收藏。</div>`;
    return;
  }
  const all = feedPapersCache || [];
  const items = [...favorites].map(id => all.find(p => p.id === id)).filter(Boolean).map(normalizePaper);
  if (!items.length) {
    body.innerHTML = `<div class="loading">收藏的论文不在当前数据集中。</div>`;
    return;
  }
  body.innerHTML = items.map(paperCard).join("");
  body.querySelectorAll(".paper-card").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".fav-btn")) return;
      modal.hidden = true;
      openDetail(el.dataset.id);
    });
  });
  body.querySelectorAll(".fav-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.fav;
      favorites.delete(id);
      saveFavorites();
      openFavModal();
      reload();
    });
  });
}
$("#btn-favorites-summary").addEventListener("click", openFavModal);
$("#fav-modal-close").addEventListener("click", () => { { const m=$("#fav-modal"); m.hidden=true; m.style.display="none"; } });
$("#fav-modal").querySelector(".fav-modal-backdrop").addEventListener("click", () => { { const m=$("#fav-modal"); m.hidden=true; m.style.display="none"; } });
$("#fav-clear").addEventListener("click", () => {
  if (!favorites.size) return;
  if (!confirm(`确定清空全部 ${favorites.size} 个收藏？`)) return;
  favorites.clear(); saveFavorites(); openFavModal(); reload();
});
$("#fav-export").addEventListener("click", () => {
  const all = feedPapersCache || [];
  const items = [...favorites].map(id => all.find(p => p.id === id)).filter(Boolean);
  const blob = new Blob([JSON.stringify(items, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `paperscope-favorites-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
});

$("#btn-auth").addEventListener("click", () => {
  alert("Week 3 功能：Supabase Auth 邮箱登录 + GitHub OAuth，尚未实现");
});

// ========== 主题切换 ==========
const themeBtn = $("#theme-toggle");
const savedTheme = localStorage.getItem("theme") || "dark";
if (savedTheme === "light") {
  document.documentElement.setAttribute("data-theme", "light");
  themeBtn.textContent = "☀️";
}
themeBtn.addEventListener("click", () => {
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  if (isLight) {
    document.documentElement.removeAttribute("data-theme");
    themeBtn.textContent = "🌙";
    localStorage.setItem("theme", "dark");
  } else {
    document.documentElement.setAttribute("data-theme", "light");
    themeBtn.textContent = "☀️";
    localStorage.setItem("theme", "light");
  }
});

// ========== 初始化 ==========
updateFavCount();
reload();
loadDashboard();
