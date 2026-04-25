import { listPapers, getPaper, listVenues } from "./supabase.js";
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
    reload();
  })
);

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
