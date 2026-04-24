import { listPapers, getPaper } from "./supabase.js";
import { S2_PAPER_API, DOMAINS } from "./config.js";

const state = {
  mode: "feed",
  domain: "all",
  source: [],
  year: "",
  paperType: [],
  sortBy: "published_at",
  search: "",
};

const $ = (sel) => document.querySelector(sel);

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
  const authors = (p.authors || []).slice(0, 3).map((a) => a.name).join(", ");
  const moreAuthors = p.authors && p.authors.length > 3 ? ` · +${p.authors.length - 3}` : "";
  const tasks = (p.tasks || []).slice(0, 4).map((t) => `<span class="task-tag">${t}</span>`).join("");
  const pdfIcon = p.open_access_pdf ? "🔓" : "";
  const cite = p.citation_count > 0 ? `<span class="citation">📊 ${p.citation_count}</span>` : "";

  return `<article class="paper-card" data-id="${p.id}">
    <h3 class="paper-title">${pdfIcon} ${esc(p.title)}</h3>
    <div class="paper-meta">
      <span class="venue-badge tier-${tierCls}">${esc(p.venue || "—")}</span>
      <span>${p.year || ""}</span>
      ${cite}
      <span>${(p.domains || []).map(d => DOMAINS[d]?.icon || "").join(" ")}</span>
    </div>
    <div class="paper-authors">${esc(authors)}${moreAuthors}</div>
    ${tasks ? `<div class="paper-tasks">${tasks}</div>` : ""}
  </article>`;
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

async function openDetail(id) {
  const panel = $("#detail-panel");
  const body = panel.querySelector(".detail-body");
  $(".layout").classList.add("has-detail");
  panel.hidden = false;
  body.innerHTML = `<div class="loading">加载详情...</div>`;

  const paper = await getPaper(id);
  if (!paper) { body.innerHTML = "论文不存在"; return; }

  // 实时从 Semantic Scholar 拉完整摘要 + 引用关系（s2 来源）
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

// ========== 初始化 ==========
reload();
