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
};

const $ = (sel) => document.querySelector(sel);

// ========== 精选模式 UI 切换 ==========
function setCuratedMode(on) {
  document.body.classList.toggle("mode-curated", on);
  if (on) {
    // 精选模式默认按引用数排序，更符合"精选"语义
    state.sortBy = "citation_count";
    $("#sort-by").value = "citation_count";
    refreshVenueList();
  } else {
    state.tier = "";
    state.venue = "";
    state.sortBy = "published_at";
    $("#filter-tier").value = "";
    $("#sort-by").value = "published_at";
    $("#filter-venue").innerHTML = '<option value="">全部</option>';
  }
}

async function refreshVenueList() {
  const sel = $("#filter-venue");
  sel.innerHTML = '<option value="">全部期刊/会议</option>';
  try {
    const venues = await listVenues(state.tier);
    // 按 tier 分组，用 optgroup
    const TIER_ORDER = ["T1", "视觉顶刊", "CCF-A", "机器人顶会", "医学顶会", "T2"];
    const byTier = {};
    venues.forEach(v => {
      const t = v.tier || "other";
      if (!byTier[t]) byTier[t] = [];
      byTier[t].push(v);
    });
    TIER_ORDER.forEach(t => {
      if (!byTier[t]?.length) return;
      // 若已选 tier 则不分组（只有一组）
      const group = document.createElement("optgroup");
      group.label = t;
      byTier[t].forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.venue;
        opt.textContent = `${v.venue} (${v.count})`;
        if (v.venue === state.venue) opt.selected = true;
        group.appendChild(opt);
      });
      sel.appendChild(group);
    });
  } catch (e) {
    console.warn("listVenues failed:", e);
  }
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
    el.addEventListener("click", () => openDetail(el.dataset.id));
  });
}

function paperCard(p) {
  const tierCls = (p.venue_tier || "").toLowerCase().replace(/[\s·]/g, "-");
  const domains = p.domains || [];
  const primaryDomain = domains[0] || "";
  const authors = (p.authors || []).slice(0, 3).map((a) => a.name).join(", ");
  const moreAuthors = p.authors && p.authors.length > 3 ? ` · +${p.authors.length - 3}` : "";
  const tasks = (p.tasks || []).slice(0, 4).map((t) => `<span class="task-tag">${esc(t)}</span>`).join("");
  const cite = p.citation_count > 0 ? `<span class="citation">📊 ${p.citation_count}</span>` : "";
  const abs = p.abstract_excerpt ? `<p class="paper-abstract">${esc(p.abstract_excerpt)}</p>` : "";

  const domainBadges = domains.map(d => {
    const meta = DOMAINS[d];
    if (!meta) return "";
    return `<span class="paper-domain-badge ${d}">${meta.icon} ${meta.label}</span>`;
  }).join("");
  const typeBadge = p.paper_type ? `<span class="paper-type ${esc(p.paper_type)}">${esc(p.paper_type)}</span>` : "";

  return `<article class="paper-card domain-${primaryDomain}" data-id="${p.id}">
    <div class="paper-domains">${domainBadges}${typeBadge}</div>
    <h3 class="paper-title">${esc(p.title)}</h3>
    <div class="paper-meta">
      <span class="venue-badge tier-${tierCls}">${esc(p.venue || "—")}</span>
      ${p.year ? `<span>${p.year}</span>` : ""}
      ${cite}
      ${p.open_access_pdf ? `<span title="开放获取">🔓</span>` : ""}
    </div>
    <div class="paper-authors">${esc(authors)}${moreAuthors}</div>
    ${abs}
    ${tasks ? `<div class="paper-tasks">${tasks}</div>` : ""}
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

  const paper = await getPaper(id);
  if (!paper) { body.innerHTML = "论文不存在"; return; }

  let refs = null, cites = null, fullAbstract = paper.abstract_excerpt || "";
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
    ${paper.open_access_pdf ? `<p><a href="${paper.open_access_pdf}" target="_blank">🔓 打开 PDF</a></p>` : ""}
    ${paper.arxiv_url ? `<p><a href="${paper.arxiv_url}" target="_blank">arXiv 原文</a></p>` : ""}
    <h4>摘要</h4>
    <p>${esc(fullAbstract)}</p>
    <h4>作者</h4>
    <p>${(paper.authors || []).map(a => esc(a.name)).join(", ")}</p>
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
  renderSubdomain();
  try {
    const stats = await fetchDashboardStats();
    renderStats(stats);
    renderTrends(stats.trends);
  } catch (e) {
    console.warn("dashboard stats failed:", e);
  }
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
  const html = trends.map(t => {
    const total = Object.values(t.counts).reduce((a, b) => a + b, 0);
    const bars = ["world_model", "physical_ai", "medical_ai"].map(d => {
      const w = max > 0 ? (t.counts[d] / max * 100) : 0;
      return w > 0 ? `<div class="trend-bar ${d}" style="width:${w}%" title="${d}: ${t.counts[d]}"></div>` : "";
    }).join("");
    return `<div class="trend-row">
      <span class="trend-year-label">${t.year}</span>
      <div class="trend-bars">${bars}</div>
      <span class="trend-count">${total.toLocaleString("en-US")}</span>
    </div>`;
  }).join("");
  $("#chart-trends").innerHTML = html || `<div class="loading">暂无数据</div>`;
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
  if (state.domain === "all") { sec.hidden = true; return; }
  sec.hidden = false;
  const tasks = domainTasks[state.domain] || [];
  if (!tasks.length) { $("#subdomain-grid").innerHTML = ""; return; }
  $("#subdomain-grid").innerHTML = tasks.map(task => `
    <div class="subdomain-item ${state.task === task ? "active" : ""}" data-task="${esc(task)}">
      <span class="name">${esc(tn(task))}</span>
    </div>
  `).join("");
}

// ========== 加载数据 ==========
async function reload() {
  $("#paper-list").innerHTML = `<div class="loading">加载中...</div>`;
  try {
    const papers = await listPapers(state);
    render(papers);
  } catch (e) {
    $("#paper-list").innerHTML = `<div class="loading">加载失败: ${esc(e.message)}<br><br>请检查 Supabase 配置是否已注入到 window.__PAPERSCOPE_CONFIG__</div>`;
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
    renderSubdomain();
    reload();
  })
);

// 热门话题：领域 tab 切换 + 展开
$("#chart-trending").addEventListener("click", (e) => {
  const tab = e.target.closest(".hot-tab");
  if (tab) { hotExpanded = false; renderHotTopics(tab.dataset.domain); return; }
  if (e.target.id === "hot-show-all") { hotExpanded = !hotExpanded; renderHotTopics(hotDomain); }
});

// 细分方向：点击 task 筛选
$("#subdomain-grid").addEventListener("click", (e) => {
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

$("#filter-year").addEventListener("change", (e) => { state.year = e.target.value; reload(); });
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

document.querySelectorAll("[data-switch-domain]").forEach((c) =>
  c.addEventListener("click", () => {
    const d = c.dataset.switchDomain;
    document.querySelectorAll(".domain-tab").forEach(x =>
      x.classList.toggle("active", x.dataset.domain === d));
    state.domain = d;
    reload();
    document.querySelector(".paper-list").scrollIntoView({ behavior: "smooth", block: "start" });
  })
);

document.querySelectorAll("input[name='type']").forEach((i) =>
  i.addEventListener("change", () => {
    state.paperType = [...document.querySelectorAll("input[name='type']:checked")].map(x => x.value);
    reload();
  })
);

$("#detail-close").addEventListener("click", () => {
  $(".layout").classList.remove("has-detail");
  $("#detail-panel").hidden = true;
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
reload();
loadDashboard();
