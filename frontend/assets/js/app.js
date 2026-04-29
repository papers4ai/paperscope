import { listPapers, getPaper, listVenues, fetchDashboardStats, fetchTrendingTopics,
         signInWithEmail, signUpWithEmail, signInWithGitHub, signOut,
         onAuthStateChange, handleOAuthCallback, getStoredSession } from "./supabase.js";
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

// ── 标签系统 ──────────────────────────────────────────────────────────────
let favTags = JSON.parse(localStorage.getItem("paperscope_tags") || "[]");
// paperTags: { paperId: [tagId, ...] }
let paperTags = JSON.parse(localStorage.getItem("paperscope_paper_tags") || "{}");
let activeTagFilter = null; // null = 全部
let _tagPickerCloseHandler = null;

const TAG_PALETTE = ["#818cf8","#34d399","#fb923c","#f472b6","#60a5fa","#a78bfa","#fbbf24","#f87171","#2dd4bf","#e879f9"];

function saveTags() {
  localStorage.setItem("paperscope_tags", JSON.stringify(favTags));
  localStorage.setItem("paperscope_paper_tags", JSON.stringify(paperTags));
}

function createTag(name, color) {
  const id = "tag_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6);
  favTags.push({ id, name, color });
  saveTags();
  return id;
}

function deleteTag(tagId) {
  favTags = favTags.filter(t => t.id !== tagId);
  for (const pid in paperTags) {
    paperTags[pid] = paperTags[pid].filter(t => t !== tagId);
    if (!paperTags[pid].length) delete paperTags[pid];
  }
  if (activeTagFilter === tagId) activeTagFilter = null;
  saveTags();
}

function togglePaperTag(paperId, tagId) {
  if (!paperTags[paperId]) paperTags[paperId] = [];
  const idx = paperTags[paperId].indexOf(tagId);
  if (idx >= 0) {
    paperTags[paperId].splice(idx, 1);
    if (!paperTags[paperId].length) delete paperTags[paperId];
  } else {
    paperTags[paperId].push(tagId);
  }
  saveTags();
}

function getTagsForPaper(paperId) {
  return (paperTags[paperId] || []).map(tid => favTags.find(t => t.id === tid)).filter(Boolean);
}

/** 渲染左侧标签侧栏 */
function renderTagSidebar(showCreateForm = false, selectedColor = TAG_PALETTE[0]) {
  const sidebar = $("#fav-tag-sidebar");
  // 统计每个标签下的论文数
  const counts = {};
  favTags.forEach(t => { counts[t.id] = 0; });
  Object.values(paperTags).forEach(tids => tids.forEach(tid => {
    if (counts[tid] !== undefined) counts[tid]++;
  }));

  const allCount = favorites.size;
  const tagItems = favTags.map(t => `
    <div class="fav-tag-item${activeTagFilter === t.id ? " active" : ""}" data-tag-id="${t.id}">
      <span class="fav-tag-dot" style="background:${t.color}"></span>
      <span class="fav-tag-name" title="${esc(t.name)}">${esc(t.name)}</span>
      <span class="fav-tag-count">${counts[t.id] || 0}</span>
      <button class="fav-tag-del" data-del-tag="${t.id}" title="Delete tag">✕</button>
    </div>`).join("");

  const createFormHtml = showCreateForm ? `
    <div class="fav-tag-create-form" id="fav-tag-create-form">
      <input type="text" id="fav-tag-name-input" placeholder="${t('tagNamePlaceholder')}" maxlength="20" autocomplete="off">
      <div class="fav-tag-color-row" id="fav-tag-color-row">
        ${TAG_PALETTE.map(c => `<span class="fav-tag-color-swatch${c === selectedColor ? " selected" : ""}" data-color="${c}" style="background:${c}"></span>`).join("")}
      </div>
      <div class="fav-tag-create-actions">
        <button class="fav-tag-create-confirm" id="fav-tag-create-confirm">${t('confirmTag')}</button>
        <button class="fav-tag-create-cancel" id="fav-tag-create-cancel">${t('cancelTag')}</button>
      </div>
    </div>` : `<button class="fav-tag-new-btn" id="fav-tag-new-btn">${t('addNewTag')}</button>`;

  sidebar.innerHTML = `
    <div class="fav-tag-sidebar-title">Tags</div>
    <div class="fav-tag-item${activeTagFilter === null ? " active" : ""}" data-tag-id="__all__">
      <span class="fav-tag-dot" style="background:var(--text-muted)"></span>
      <span class="fav-tag-name">${t('allFavorites')}</span>
      <span class="fav-tag-count">${allCount}</span>
    </div>
    ${tagItems}
    ${createFormHtml}
  `;

  // 绑定事件
  sidebar.querySelectorAll(".fav-tag-item").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".fav-tag-del")) return;
      const tid = el.dataset.tagId;
      activeTagFilter = (tid === "__all__") ? null : tid;
      renderFavModalBody();
      renderTagSidebar();
    });
  });

  sidebar.querySelectorAll(".fav-tag-del").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const tid = btn.dataset.delTag;
      const tag = favTags.find(t => t.id === tid);
      if (!tag) return;
      if (!confirm(t('deleteTagConfirm').replace('{name}', tag.name))) return;
      deleteTag(tid);
      renderFavModalBody();
      renderTagSidebar();
    });
  });

  const newBtn = sidebar.querySelector("#fav-tag-new-btn");
  if (newBtn) {
    newBtn.addEventListener("click", () => renderTagSidebar(true));
  }

  // 颜色选择
  let _currentColor = selectedColor;
  sidebar.querySelectorAll(".fav-tag-color-swatch").forEach(swatch => {
    swatch.addEventListener("click", () => {
      _currentColor = swatch.dataset.color;
      sidebar.querySelectorAll(".fav-tag-color-swatch").forEach(s => s.classList.toggle("selected", s.dataset.color === _currentColor));
    });
  });

  const confirmBtn = sidebar.querySelector("#fav-tag-create-confirm");
  const cancelBtn  = sidebar.querySelector("#fav-tag-create-cancel");
  const nameInput  = sidebar.querySelector("#fav-tag-name-input");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", () => {
      const name = (nameInput?.value || "").trim();
      if (!name) { nameInput?.focus(); return; }
      createTag(name, _currentColor);
      renderTagSidebar(false);
      renderFavModalBody();
    });
  }
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => renderTagSidebar(false));
  }
  if (nameInput) {
    nameInput.focus();
    nameInput.addEventListener("keydown", e => {
      if (e.key === "Enter") confirmBtn?.click();
      if (e.key === "Escape") cancelBtn?.click();
    });
  }
}

/** 渲染右侧论文列表（含标签 chips） */
function renderFavModalBody() {
  const body = $("#fav-modal-body");
  if (!favorites.size) {
    body.innerHTML = `<div class="loading">${t('noFavorites')}</div>`;
    return;
  }
  // 获取所有收藏论文（从缓存）
  const allCached = [...(feedPapersCache || []), ...(curatedPapersCache || [])];
  const seen = new Set();
  const allFav = [...favorites].map(id => {
    const found = allCached.find(p => p.id === id);
    return found;
  }).filter(p => p && !seen.has(p.id) && seen.add(p.id)).map(normalizePaper);

  // 按标签过滤
  const items = activeTagFilter
    ? allFav.filter(p => (paperTags[p.id] || []).includes(activeTagFilter))
    : allFav;

  if (!items.length) {
    const tagName = activeTagFilter ? (favTags.find(t => t.id === activeTagFilter)?.name || "") : "";
    body.innerHTML = `<div class="loading">${activeTagFilter ? `No favorites under tag "${esc(tagName)}".` : t('favNotLoaded')}</div>`;
    return;
  }

  body.innerHTML = items.map(p => {
    const cardHtml = paperCard(p);
    const tags = getTagsForPaper(p.id);
    const tagChips = tags.map(t => `
      <span class="paper-tag-chip" style="background:color-mix(in srgb,${t.color} 18%,transparent);color:${t.color};border:1px solid color-mix(in srgb,${t.color} 35%,transparent)">
        <span class="fav-tag-dot" style="background:${t.color};width:6px;height:6px"></span>
        ${esc(t.name)}
        <button class="paper-tag-chip-del" data-paper-id="${p.id}" data-tag-id="${t.id}" title="移除标签">✕</button>
      </span>`).join("");
    const addBtn = `<button class="paper-tag-add-btn" data-paper-id="${p.id}" title="添加标签">＋ 标签</button>`;
    const chipsRow = `<div class="paper-tag-chips" data-paper-id="${p.id}">${tagChips}${addBtn}</div>`;
    // 把 chips row 插入到卡片末尾（替换 </article> 前插入）
    return cardHtml.replace(/<\/article>\s*$/, chipsRow + "</article>");
  }).join("");

  // 卡片点击打开详情
  body.querySelectorAll(".paper-card").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".fav-btn") || e.target.closest(".paper-tag-chips")) return;
      const modal = $("#fav-modal");
      modal.hidden = true; modal.style.display = "none";
      openDetail(el.dataset.id);
    });
  });

  // 收藏按钮（取消收藏）
  body.querySelectorAll(".fav-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.fav;
      favorites.delete(id);
      saveFavorites();
      renderTagSidebar();
      renderFavModalBody();
      reload();
    });
  });

  // 移除标签 chip
  body.querySelectorAll(".paper-tag-chip-del").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePaperTag(btn.dataset.paperId, btn.dataset.tagId);
      renderTagSidebar();
      renderFavModalBody();
    });
  });

  // 添加标签按钮 → 弹出 tag picker
  body.querySelectorAll(".paper-tag-add-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openTagPicker(btn.dataset.paperId, btn, { inFavModal: true });
    });
  });
}

/** 浮动标签选择气泡 */
/**
 * 通用标签选择气泡
 * @param {string} paperId
 * @param {HTMLElement} anchorEl  气泡定位锚点
 * @param {object} opts
 *   opts.inFavModal  {boolean}  是否在收藏弹窗内（影响关闭后的刷新行为）
 *   opts.onDone      {Function} 选择/跳过后的回调
 */
function openTagPicker(paperId, anchorEl, opts = {}) {
  closeTagPicker();

  const assigned = paperTags[paperId] || [];
  const popup = document.createElement("div");
  popup.className = "tag-picker-popup";
  popup.id = "tag-picker-popup";

  const tagRows = favTags.map(t => `
    <div class="tag-picker-item" data-tag-id="${t.id}">
      <span class="fav-tag-dot" style="background:${t.color}"></span>
      <span>${esc(t.name)}</span>
      ${assigned.includes(t.id) ? `<span class="tag-picker-check">✓</span>` : ""}
    </div>`).join("");

  const emptyHint = !favTags.length
    ? `<div class="tag-picker-empty">${t('noTagsYet')}</div>` : "";

  const skipRow = !opts.inFavModal
    ? `<div class="tag-picker-item tag-picker-skip" id="tag-picker-skip-btn" style="border-top:1px solid var(--border);margin-top:.3rem;padding-top:.35rem;color:var(--text-muted)">${t('skipTag')}</div>`
    : "";

  popup.innerHTML = emptyHint + tagRows +
    `<div class="tag-picker-item tag-picker-new" id="tag-picker-new-btn" style="border-top:1px solid var(--border);margin-top:.3rem;padding-top:.35rem;color:var(--accent)">${t('addNewTag')}</div>` +
    skipRow;

  document.body.appendChild(popup);

  // 定位气泡
  const rect = anchorEl.getBoundingClientRect();
  const popupW = 172;
  let left = rect.left;
  if (left + popupW > window.innerWidth - 10) left = window.innerWidth - popupW - 10;
  if (left < 10) left = 10;
  let top = rect.bottom + 6;
  // 若超出屏幕底部，改为向上弹出
  if (top + 160 > window.innerHeight - 10) top = rect.top - 160;
  popup.style.top = top + "px";
  popup.style.left = left + "px";

  const done = (tagId) => {
    closeTagPicker();
    if (opts.inFavModal) { renderTagSidebar(); renderFavModalBody(); }
    opts.onDone?.(tagId);
  };

  popup.querySelectorAll(".tag-picker-item[data-tag-id]").forEach(item => {
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      togglePaperTag(paperId, item.dataset.tagId);
      done(item.dataset.tagId);
    });
  });

  popup.querySelector("#tag-picker-new-btn")?.addEventListener("click", (e) => {
    e.stopPropagation();
    closeTagPicker();
    if (opts.inFavModal) {
      renderTagSidebar(true);
    } else {
      // 在主列表中：打开收藏弹窗并进入新建标签状态
      openFavModal();
      renderTagSidebar(true);
    }
  });

  popup.querySelector("#tag-picker-skip-btn")?.addEventListener("click", (e) => {
    e.stopPropagation();
    done(null);
  });

  // 点击外部关闭
  setTimeout(() => {
    _tagPickerCloseHandler = (e) => {
      if (!popup.contains(e.target)) {
        closeTagPicker();
        opts.onDone?.(null);
      }
    };
    document.addEventListener("click", _tagPickerCloseHandler, { once: false });
  }, 10);
}

/**
 * 收藏一篇论文并立即弹出标签选择气泡
 * @param {string} paperId
 * @param {HTMLElement} btnEl  ☆ 按钮元素（用于定位气泡）
 * @param {Function} onFaved   收藏成功后更新 UI 的回调 (btn, id) => void
 */
function addToFavWithTagPicker(paperId, btnEl, onFaved) {
  favorites.add(paperId);
  saveFavorites();
  onFaved?.(btnEl, paperId);
  openTagPicker(paperId, btnEl, {
    inFavModal: false,
    onDone: () => { /* 标签已选或跳过，不需额外操作 */ }
  });
}

function closeTagPicker() {
  const existing = document.getElementById("tag-picker-popup");
  if (existing) existing.remove();
  if (_tagPickerCloseHandler) {
    document.removeEventListener("click", _tagPickerCloseHandler);
    _tagPickerCloseHandler = null;
  }
}

// 可用年份（由 meta.json 决定，自动扩展；初始值兜底）
let availableYears = [2023, 2024, 2025, 2026, 2027];

// 静态 arxiv 数据 (速览模式)
let feedPapersCache = null;
async function loadFeedPapers() {
  if (feedPapersCache) return feedPapersCache;
  const results = await Promise.all(
    availableYears.map(y => fetch(`data/papers_${y}.json`).then(r => r.ok ? r.json() : []).catch(() => []))
  );
  feedPapersCache = results.flat();
  return feedPapersCache;
}

// 静态精选数据 (精选模式)
// 数据按领域拆成 3 个文件（各 ~15-50 MB），并行加载后合并去重
let curatedPapersCache = null;
async function loadCuratedPapers() {
  if (curatedPapersCache) return curatedPapersCache;

  // 三个领域均按年份拆分（使用 meta.json 中的可用年份）
  const CURATED_DOMAINS = ["world_model", "physical_ai", "medical_ai"];
  const files = CURATED_DOMAINS.flatMap(d =>
    availableYears.map(y => `data/papers_curated_${d}_${y}.json`)
  );
  const results = await Promise.all(
    files.map(f =>
      fetch(f).then(r => r.ok ? r.json() : []).catch(() => [])
    )
  );

  // 合并并按 id 去重（跨领域论文会在多个文件中出现）
  const seen = new Set();
  const merged = [];
  for (const list of results) {
    for (const p of list) {
      if (p.id && !seen.has(p.id)) {
        seen.add(p.id);
        merged.push(p);
      }
    }
  }

  curatedPapersCache = merged.map(normalizeCurated);

  // 更新 footer 最新数据时间（由 meta.json 负责，这里不再重复计算）

  return curatedPapersCache;
}

function normalizeCurated(p) {
  return {
    ...p,
    _domains: p._domains || [],
    _tasks:   p._tasks   || [],
    has_code: p.has_code === true || !!(p.code),
    authors:  (p.authors || []).map(a => typeof a === "string" ? a : (a.name || "")),
    _isCurated: true,
  };
}

const $ = (sel) => document.querySelector(sel);

// ========== 精选模式 UI 切换 ==========
function setCuratedMode(on) {
  document.body.classList.toggle("mode-curated", on);
  if (on) {
    state.year = "";   // 切换到精选时重置年份，由 venue picker 控制
    state.sortBy = "published_at";
    $("#sort-by").value = "published_at";
    // 同步 vp-year-row 高亮到"全部"
    document.querySelectorAll(".vpy-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.year === ""));
    refreshVenueList();
    renderVenuePicker(state.domain);
  } else {
    state.year = "";
    state.tier = "";
    state.venue = "";
    state.sortBy = "published_at";
    $("#filter-tier").value = "";
    $("#filter-year").value = "";
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
  if (domain === "all") {
    body.innerHTML = `<div class="vpc-hint">${t('selectDomainHint')}</div>`;
    return;
  }

  const domains = [domain];

  // 取本地精选数据中各 venue 篇数
  let counts = {};
  try {
    const all = await loadCuratedPapers();
    const pool = domain === "all" ? all : all.filter(p => (p._domains||[]).includes(domain));
    pool.forEach(p => { if (p.venue) counts[p.venue] = (counts[p.venue] || 0) + 1; });
  } catch {}

  let html = "";
  domains.forEach(d => {
    const groups = catalog[d] || [];
    if (!groups.length) return;
    groups.forEach((g, gi) => {
      const groupId = `vpc-g-${d}-${gi}`;
      // 默认展开：有选中 venue 的那组、或第一组
      const hasActive = g.venues.includes(state.venue);
      const open = hasActive || gi === 0;
      const chipsHtml = g.venues.map(v => {
        const cnt = counts[v] || 0;
        const active = state.venue === v ? "active" : "";
        const hasCnt = cnt > 0;
        return `<button class="vpc-chip ${active} ${hasCnt ? "has-papers" : ""}" data-venue="${esc(v)}" title="${esc(v)} · ${hasCnt ? cnt + t("articles") : t("noData")}">
          ${esc(v)}${hasCnt ? `<span class="vpc-cnt">${cnt}</span>` : ""}
        </button>`;
      }).join("");
      html += `<div class="vpc-group">
        <button class="vpc-category-toggle ${open ? "open" : ""}" data-target="${groupId}">
          <span>${esc(tVenueCategory(g.category))}</span>
          <span class="vpc-toggle-icon">${open ? "▲" : "▼"}</span>
        </button>
        <div class="vpc-chips ${open ? "" : "collapsed"}" id="${groupId}">${chipsHtml}</div>
      </div>`;
    });
  });
  body.innerHTML = html || `<div class="loading">${t("noData")}</div>`;
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
  sel.innerHTML = `<option value="">${t('allVenues')}</option>`;
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
      og.label = tVenueCategory(g.category);
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
    list.innerHTML = `<div class="loading">${t('noPapers')}</div>`;
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
      if (favorites.has(id)) {
        // 取消收藏
        favorites.delete(id);
        btn.classList.remove("active"); btn.textContent = "☆";
        saveFavorites();
        if (state.favorites) reload();
      } else {
        // 新增收藏 → 弹出标签选择
        addToFavWithTagPicker(id, btn, (b) => {
          b.classList.add("active"); b.textContent = "★";
          if (state.favorites) reload();
        });
      }
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
  const abs = p.abstract || p.abstract_short || p.abstract_excerpt || "";
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
  const absHtml = n.abs ? `<p class="paper-abstract">${esc(n.abs)}</p>` : "";

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
  requestAnimationFrame(() => {
    panel.classList.add("active");
    // Show mobile back button (outside panel so position:fixed works)
    const btn = $("#detail-close");
    if (btn && window.innerWidth <= 900) btn.style.display = "flex";
  });
  body.innerHTML = `<div class="loading">${t('loadingDetail')}</div>`;

  let paper = null;
  // 先在本地缓存查找（速览模式）
  if (state.mode === "feed" && feedPapersCache) {
    paper = feedPapersCache.find(x => x.id === id) || null;
    if (paper) paper = normalizePaper(paper);
  }
  // 精选模式：从精选缓存查找
  if (!paper && state.mode === "curated" && curatedPapersCache) {
    const raw = curatedPapersCache.find(x => x.id === id) || null;
    if (raw) paper = normalizePaper(raw);
  }
  // 兜底：尝试 Supabase（feed 模式且本地未命中）
  if (!paper && state.mode !== "curated") paper = await getPaper(id);
  if (!paper) { body.innerHTML = t('paperNotFound'); return; }
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
    <p><strong>${esc(paper.venue || "")}</strong> · ${paper.year || ""} ${paper.citation_count ? `· 📊 ${paper.citation_count} citations` : ""}</p>
    ${n.pdfUrl ? `<p><a href="${n.pdfUrl}" target="_blank">${t('openPDF')}</a></p>` : ""}
    ${n.arxivUrl ? `<p><a href="${n.arxivUrl}" target="_blank">${t('arxivSource')}</a></p>` : ""}
    ${n.codeUrl ? `<p><a href="${n.codeUrl}" target="_blank">💻 Code</a></p>` : ""}
    <h4>${t('abstract')}</h4>
    <p>${esc(fullAbstract)}</p>
    <h4>${t('authors')}</h4>
    <p>${esc(authorsStr)}</p>
    ${refs?.length ? `<h4>References</h4><ul class="refs-list">${refs.map(r => `<li>${esc(r.title)} · ${r.citationCount || 0} citations</li>`).join("")}</ul>` : ""}
    ${cites?.length ? `<h4>Citing Papers</h4><ul class="refs-list">${cites.map(r => `<li>${esc(r.title)} · ${r.citationCount || 0} citations</li>`).join("")}</ul>` : ""}
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
let hotLastUpdated = null;
let hotUpdateInterval = null;

// 先定义formatHotUpdateTime，避免函数提升问题
function formatHotUpdateTime() {
  if (!hotLastUpdated) return currentLang === "en" ? "Not updated yet" : "尚未更新";
  const now = new Date();
  const diff = Math.floor((now - hotLastUpdated) / 1000);
  if (diff < 60) return currentLang === "en" ? "Just updated" : "刚刚更新";
  if (diff < 3600) return currentLang === "en" ? `${Math.floor(diff / 60)} minutes ago` : `${Math.floor(diff / 60)} 分钟前更新`;
  if (diff < 86400) return currentLang === "en" ? `${Math.floor(diff / 3600)} hours ago` : `${Math.floor(diff / 3600)} 小时前更新`;
  return hotLastUpdated.toLocaleString(currentLang === "en" ? "en-US" : "zh-CN");
}

function tn(task) {
  const m = taskMeta[task];
  if (!m) return task;
  return currentLang === "en" ? (m.en || m.zh || task) : (m.zh || m.en || task);
}

function renderYearControls(years) {
  // 侧栏年份下拉
  const sel = document.getElementById("filter-year");
  if (sel) {
    const cur = sel.value;
    sel.innerHTML = `<option value="">${t('all')}</option>` +
      [...years].reverse().map(y => `<option value="${y}"${cur == y ? " selected" : ""}>${y}</option>`).join("");
  }
  // 精选年份按钮行
  const row = document.getElementById("vp-year-row");
  if (row) {
    const curYear = state.year;
    const btns = [...years].reverse().map(y =>
      `<button class="vpy-btn${curYear == y ? " active" : ""}" data-year="${y}">${y}</button>`
    ).join("");
    row.innerHTML = `<span class="vp-year-label">${t('year')}</span>` +
      `<button class="vpy-btn${!curYear ? " active" : ""}" data-year="">${t('all')}</button>` + btns;
  }
}

async function loadStaticData() {
  try {
    const [tr, tm, meta] = await Promise.all([
      fetch("data/trending.json").then(r => r.ok ? r.json() : null),
      fetch("data/task_meta.json").then(r => r.ok ? r.json() : null),
      fetch("data/meta.json").then(r => r.ok ? r.json() : null),
    ]);
    if (tr?.trends) trendingData = tr.trends;
    if (tm?.tasks) taskMeta = tm.tasks;
    if (tm?.domain_tasks && Object.keys(tm.domain_tasks).length) domainTasks = tm.domain_tasks;
    if (meta?.years?.length) {
      availableYears = meta.years;
      renderYearControls(availableYears);
    }
    const footerEl = document.getElementById("footer-last-updated");
    if (footerEl && meta?.last_updated) footerEl.textContent = meta.last_updated;
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
  const years = availableYears;
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
  $("#chart-trends").innerHTML = (rowsHtml ? legend + rowsHtml : `<div class="loading">${t("noData")}</div>`);
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
    $("#chart-trending").innerHTML = tabsHtml + `<div class="loading">${t("noData")}</div>`;
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
    ? `<button class="hot-show-all" id="hot-show-all">${hotExpanded ? t("collapse") : t("showAll").replace("{count}", items.length)}</button>`
    : "";
  $("#chart-trending").innerHTML = tabsHtml + itemsHtml + more;
}

function renderSubdomain() {
  const sec = $("#subdomain-section");
  if (state.domain === "all") {
    sec.hidden = false;
    sec.innerHTML = `<div class="subdomain-hint">
      ${t("subdomainHint")}
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
    const articlesText = t("articles");
    const newThisWeekText = fresh ? t("newThisWeek").replace("{count}", fresh) : "";
    const tip = `${currentLang === "en" ? (m.en || m.zh || task) : (m.zh || m.en || task)}（${total}${articlesText}${newThisWeekText}）`;
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
      <span class="subdomain-sub">${t("subdomainSub").replace("{count}", items.length)}</span>
      ${state.task ? `<button class="subdomain-clear" id="subdomain-clear">${t("clearFilter")}</button>` : ""}
    </div>
    <div class="subdomain-grid" id="subdomain-grid">${itemsHtml || '<div class="loading">' + t("noData") + '</div>'}</div>
  `;
}

// ========== 精选模式：本地过滤 ==========
function applyCuratedFilters(papers) {
  const s = state;
  const q = s.search.toLowerCase();
  let out = papers.filter(p => {
    if (s.domain !== "all" && !(p._domains || []).includes(s.domain)) return false;
    if (s.venue && p.venue !== s.venue) return false;
    if (s.year && String(p.year) !== String(s.year)) return false;
    if (s.paperType.length && !s.paperType.includes(p.type)) return false;
    if (s.hasCode && !p.has_code) return false;
    if (s.favorites && !favorites.has(p.id)) return false;
    if (q) {
      const hay = (p.title + " " + (p.authors||[]).join(" ")).toLowerCase();
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
  try {
    if (state.mode === "trending") {
      // 热榜模式：显示热榜视图，隐藏论文列表
      $("#trending-view").hidden = false;
      $("#paper-list").hidden = true;
      $("#dashboard").hidden = true;
      // 初始化更新时间
      if (!hotLastUpdated) {
        await refreshHotData();
      } else {
        const timeEl = document.getElementById("hot-last-updated");
        if (timeEl) timeEl.textContent = formatHotUpdateTime();
      }
    } else {
      // 其他模式：显示论文列表，隐藏热榜视图
      $("#trending-view").hidden = true;
      $("#paper-list").hidden = false;
      $("#dashboard").hidden = state.mode !== "feed";
      
      $("#paper-list").innerHTML = `<div class="loading">${t('loading')}</div>`;
      
      if (state.mode === "feed") {
        const all = (await loadFeedPapers()).map(normalizePaper);
        const filtered = applyFeedFilters(all);
        feedTotal = filtered.length;
        render(filtered.slice(0, 100));
      } else if (state.mode === "curated") {
        const all = await loadCuratedPapers();
        const filtered = applyCuratedFilters(all);
        render(filtered.slice(0, 100));
      } else {
        const papers = await listPapers(state);
        render(papers);
      }
    }
  } catch (e) {
    if (state.mode !== "trending") {
      $("#paper-list").innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    }
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
  // 折叠/展开
  const toggle = e.target.closest(".vpc-category-toggle");
  if (toggle) {
    const target = document.getElementById(toggle.dataset.target);
    const open = toggle.classList.toggle("open");
    target?.classList.toggle("collapsed", !open);
    toggle.querySelector(".vpc-toggle-icon").textContent = open ? "▲" : "▼";
    return;
  }
  // 选 venue
  const chip = e.target.closest(".vpc-chip");
  if (!chip) return;
  const v = chip.dataset.venue;
  state.venue = state.venue === v ? "" : v;
  $("#filter-venue").value = state.venue;
  document.querySelectorAll(".vpc-chip").forEach(c =>
    c.classList.toggle("active", c.dataset.venue === state.venue));
  reload();
});

function closeDetail() {
  const panel = $("#detail-panel");
  panel.classList.remove("active");
  $(".layout").classList.remove("has-detail");
  const btn = $("#detail-close");
  if (btn) btn.style.display = "";
  setTimeout(() => { panel.hidden = true; }, 300);
}
$("#detail-close").addEventListener("click", closeDetail);
$("#detail-close-desktop")?.addEventListener("click", closeDetail);

// 手机端：右滑手势关闭详情面板
(function () {
  const panel = $("#detail-panel");
  let touchStartX = 0, touchStartY = 0;
  panel.addEventListener("touchstart", (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }, { passive: true });
  panel.addEventListener("touchend", (e) => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    const dy = e.changedTouches[0].clientY - touchStartY;
    // 右滑距离 > 60px 且水平位移大于垂直位移（避免误触滚动）
    if (dx > 60 && Math.abs(dx) > Math.abs(dy)) closeDetail();
  }, { passive: true });
})();

// ========== 收藏汇总 Modal ==========
function openFavModal() {
  const modal = $("#fav-modal");
  modal.hidden = false;
  modal.style.display = "flex";
  updateFavCount();
  renderTagSidebar();
  renderFavModalBody();
}

function closeFavModal() {
  const m = $("#fav-modal");
  m.hidden = true; m.style.display = "none";
  closeTagPicker();
}

$("#btn-favorites-summary").addEventListener("click", openFavModal);
$("#fav-modal-close").addEventListener("click", closeFavModal);
$("#fav-modal").querySelector(".fav-modal-backdrop").addEventListener("click", closeFavModal);
$("#fav-clear").addEventListener("click", () => {
  if (!favorites.size) return;
  if (!confirm(t('clearFavConfirm').replace('{n}', favorites.size))) return;
  favorites.clear(); saveFavorites();
  renderTagSidebar(); renderFavModalBody(); reload();
});
// ── 导出工具函数 ──────────────────────────────────────────────────────────
function getFavItems() {
  const allCached = [...(feedPapersCache || []), ...(curatedPapersCache || [])];
  const seen = new Set();
  return [...favorites]
    .map(id => allCached.find(p => p.id === id))
    .filter(p => p && !seen.has(p.id) && seen.add(p.id));
}

function downloadBlob(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportCSV(items) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const cols = t('csvCols').split(',');
  const csvEsc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = items.map(p => {
    const authors = (p.authors || []).join("; ");
    const tags = getTagsForPaper(p.id).map(t => t.name).join("; ");
    return [
      p.title, authors, p.year ?? "", p.venue ?? "",
      tags, p.citation_count ?? "",
      p.arxiv_url ?? "", p.pdf_url ?? "", p.code ?? ""
    ].map(csvEsc).join(",");
  });
  const bom = "﻿"; // UTF-8 BOM，让 Excel 正确识别中文
  downloadBlob(bom + [cols.map(csvEsc).join(","), ...rows].join("\r\n"),
    `paperscope-favorites-${dateStr}.csv`, "text/csv;charset=utf-8");
}

function exportBibTeX(items) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const sanitizeKey = s => String(s || "").replace(/[^a-zA-Z0-9_]/g, "").slice(0, 20);
  const bibEsc = s => String(s || "").replace(/[{}&%$#_^~\\]/g, c => `\\${c}`);
  const entries = items.map(p => {
    const authors = (p.authors || []).join(" and ");
    // key = 第一作者姓+年份+id前4位
    const firstAuthor = (p.authors?.[0] || "unknown").split(/\s+/).pop();
    const key = sanitizeKey(firstAuthor) + (p.year ?? "") + sanitizeKey((p.id || "").slice(0, 5));
    const venue = p.venue || "arXiv";
    const type = (p.venue && !p.arxiv_url?.includes("arxiv")) ? "article" : "misc";
    const urlField = p.arxiv_url ? `  url          = {${p.arxiv_url}},\n` : (p.pdf_url ? `  url          = {${p.pdf_url}},\n` : "");
    const codeField = p.code ? `  note         = {Code: ${p.code}},\n` : "";
    const tagsField = getTagsForPaper(p.id).map(t => t.name);
    const keywordsField = tagsField.length ? `  keywords     = {${tagsField.join(", ")}},\n` : "";
    return `@${type}{${key},\n  title        = {${bibEsc(p.title)}},\n  author       = {${bibEsc(authors)}},\n  year         = {${p.year ?? ""}},\n  journal      = {${bibEsc(venue)}},\n${urlField}${codeField}${keywordsField}}`;
  });
  downloadBlob(entries.join("\n\n"),
    `paperscope-favorites-${dateStr}.bib`, "text/plain;charset=utf-8");
}

function exportJSON(items) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const withTags = items.map(p => ({ ...p, _tags: getTagsForPaper(p.id).map(t => t.name) }));
  downloadBlob(JSON.stringify(withTags, null, 2),
    `paperscope-favorites-${dateStr}.json`, "application/json");
}

// ── 导出按钮 & 菜单 ──────────────────────────────────────────────────────
const favExportMenu = $("#fav-export-menu");
let _exportMenuCloseHandler = null;

function closeExportMenu() {
  favExportMenu.hidden = true;
  if (_exportMenuCloseHandler) {
    document.removeEventListener("click", _exportMenuCloseHandler);
    _exportMenuCloseHandler = null;
  }
}

$("#fav-export").addEventListener("click", (e) => {
  e.stopPropagation();
  const isOpen = !favExportMenu.hidden;
  closeExportMenu();
  if (!isOpen) {
    favExportMenu.hidden = false;
    setTimeout(() => {
      _exportMenuCloseHandler = () => closeExportMenu();
      document.addEventListener("click", _exportMenuCloseHandler, { once: true });
    }, 10);
  }
});

favExportMenu.addEventListener("click", (e) => {
  e.stopPropagation();
  const item = e.target.closest(".fav-export-item");
  if (!item) return;
  const fmt = item.dataset.fmt;
  closeExportMenu();
  const items = getFavItems();
  if (!items.length) { alert(t('noExportItems')); return; }
  if (fmt === "csv")  exportCSV(items);
  if (fmt === "bib")  exportBibTeX(items);
  if (fmt === "json") exportJSON(items);
});

// ==================== Auth ====================

const authModal   = $("#auth-modal");
const authBtnEl   = $("#btn-auth");

/** 打开 / 关闭 Auth Modal */
function openAuthModal()  { authModal.hidden = false; document.body.style.overflow = "hidden"; }
function closeAuthModal() { authModal.hidden = true;  document.body.style.overflow = ""; }

// 更新顶栏按钮外观
function updateAuthButton(user) {
  if (user) {
    const avatarUrl = user.user_metadata?.avatar_url || "";
    const email     = user.email || user.user_metadata?.email || "已登录";
    const shortName = email.split("@")[0].slice(0, 12);
    authBtnEl.classList.add("logged-in");
    authBtnEl.innerHTML = `
      <span class="btn-avatar">
        ${avatarUrl ? `<img src="${avatarUrl}" alt="">` : "👤"}
      </span>
      <span>${shortName}</span>`;
  } else {
    authBtnEl.classList.remove("logged-in");
    authBtnEl.innerHTML = "登录";
  }
}

// 确保登录状态在页面加载后正确显示
function ensureAuthDisplay() {
  const sess = getStoredSession();
  if (sess?.user) {
    updateAuthButton(sess.user);
  }
}

// 监听 auth 状态变化
onAuthStateChange(user => {
  updateAuthButton(user);
  // 若 modal 已打开且用户已登录 → 切换到已登录视图
  if (user && !authModal.hidden) {
    showLoggedInView(user);
  }
});

// 处理 OAuth 回调（页面 URL hash 里携带 access_token）
handleOAuthCallback();

// 页面加载完成后再次确认登录状态显示
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", ensureAuthDisplay);
} else {
  ensureAuthDisplay();
}

// 定期检查登录状态（防止 localStorage 被意外清除）
setInterval(ensureAuthDisplay, 5000);

// 点击登录按钮
authBtnEl.addEventListener("click", () => {
  const sess = getStoredSession();
  if (sess?.user) {
    // 已登录 → 打开 modal 显示账户信息
    showLoggedInView(sess.user);
    openAuthModal();
  } else {
    showLoginView();
    openAuthModal();
  }
});

// 关闭按钮 & backdrop 点击
$("#auth-close").addEventListener("click", closeAuthModal);
$("#auth-backdrop").addEventListener("click", closeAuthModal);

// ESC 键关闭
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !authModal.hidden) closeAuthModal();
});

// ==================== About Modal ====================
const aboutModal = $("#about-modal");

function openAboutModal() {
  aboutModal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeAboutModal() {
  aboutModal.hidden = true;
  document.body.style.overflow = "";
}

$("#btn-about").addEventListener("click", openAboutModal);
$("#about-close").addEventListener("click", closeAboutModal);
$("#about-backdrop").addEventListener("click", closeAboutModal);

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !aboutModal.hidden) closeAboutModal();
});

// Tab 切换：登录 / 注册
document.querySelectorAll(".auth-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const target = tab.dataset.tab;
    document.querySelectorAll(".auth-form").forEach(f => f.classList.toggle("hidden", f.dataset.tab !== target));
    $("#auth-form-login").classList.toggle("hidden", target !== "login");
    $("#auth-form-register").classList.toggle("hidden", target !== "register");
    clearAuthErrors();
  });
});

function clearAuthErrors() {
  $("#auth-err-login").textContent = "";
  $("#auth-err-register").textContent = "";
}

function showLoginView() {
  $("#auth-logged-in").classList.add("hidden");
  $("#auth-form-login").classList.remove("hidden");
  $("#auth-form-register").classList.add("hidden");
  $("#auth-github").style.display = "";
  document.querySelector(".auth-divider").style.display = "";
  document.querySelectorAll(".auth-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === "login"));
  document.querySelector(".auth-tabs").style.display = "";
}

function showLoggedInView(user) {
  $("#auth-form-login").classList.add("hidden");
  $("#auth-form-register").classList.add("hidden");
  document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
  document.querySelector(".auth-tabs").style.display = "none";
  document.querySelector(".auth-divider").style.display = "none";
  $("#auth-github").style.display = "none";

  const avatarUrl = user.user_metadata?.avatar_url || "";
  const email = user.email || user.user_metadata?.email || "已登录";
  const avatarEl = $("#auth-avatar");
  avatarEl.innerHTML = avatarUrl ? `<img src="${avatarUrl}" alt="">` : "👤";
  $("#auth-user-email").textContent = email;
  $("#auth-logged-in").classList.remove("hidden");
}

// 登录表单提交
$("#auth-form-login").addEventListener("submit", async e => {
  e.preventDefault();
  const email = $("#auth-email-login").value.trim();
  const pass  = $("#auth-pass-login").value;
  const errEl = $("#auth-err-login");
  const btn   = e.target.querySelector(".auth-submit");
  errEl.textContent = "";
  btn.disabled = true;
  btn.textContent = "登录中...";
  try {
    const data = await signInWithEmail(email, pass);
    closeAuthModal();
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "登录";
  }
});

// 注册表单提交
$("#auth-form-register").addEventListener("submit", async e => {
  e.preventDefault();
  const email = $("#auth-email-register").value.trim();
  const pass  = $("#auth-pass-register").value;
  const errEl = $("#auth-err-register");
  const btn   = e.target.querySelector(".auth-submit");
  errEl.textContent = "";
  if (pass.length < 8) { errEl.textContent = "密码至少 8 位"; return; }
  btn.disabled = true;
  btn.textContent = "注册中...";
  try {
    const data = await signUpWithEmail(email, pass);
    if (data.access_token) {
      closeAuthModal();
    } else {
      // Supabase 默认需要邮件确认
      errEl.style.color = "var(--physical-ai)";
      errEl.textContent = "注册成功！请查收确认邮件后登录。";
    }
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "注册";
  }
});

// GitHub OAuth
$("#auth-github").addEventListener("click", () => signInWithGitHub());

// 退出登录
$("#auth-signout").addEventListener("click", async () => {
  await signOut();
  showLoginView();
});

// ========== 主题切换（黑夜 / 白天 / 跟随系统，循环切换） ==========
const themeBtn = $("#theme-toggle");
const THEME_CYCLE = ["dark", "light", "system"];
const THEME_ICON  = { dark: "🌙", light: "☀️", system: "💻" };
const THEME_LABEL = { dark: "深色", light: "浅色", system: "跟随系统" };

function applyTheme(theme) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const effectiveLight = theme === "light" || (theme === "system" && !prefersDark);
  if (effectiveLight) {
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  themeBtn.textContent = THEME_ICON[theme];
  themeBtn.title = THEME_LABEL[theme];
  localStorage.setItem("theme", theme);
}

// 点击循环：深色 → 浅色 → 跟随系统 → 深色
themeBtn.addEventListener("click", () => {
  const cur = localStorage.getItem("theme") || "system";
  const next = THEME_CYCLE[(THEME_CYCLE.indexOf(cur) + 1) % THEME_CYCLE.length];
  applyTheme(next);
});

// OS 主题变化时，若当前是"跟随系统"模式则自动更新
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if ((localStorage.getItem("theme") || "system") === "system") applyTheme("system");
});

// 热榜手动刷新按钮
$("#hot-refresh-btn")?.addEventListener("click", async () => {
  const btn = $("#hot-refresh-btn");
  btn.style.transform = "rotate(360deg)";
  await refreshHotData();
  setTimeout(() => { btn.style.transform = ""; }, 500);
});

// ========== 语言切换 ==========
const langToggleBtn = $("#lang-toggle");

function updateLangButton() {
  langToggleBtn.textContent = currentLang === "en" ? "🌐 EN" : "🌐 中文";
}

function toggleLanguage() {
  const newLang = currentLang === "en" ? "zh" : "en";
  setLanguage(newLang);
  updateLangButton();
  document.documentElement.lang = newLang;
  // Re-render JS-built sections so dynamic t() calls pick up the new language
  renderSubdomain();
  if (hotDomain) renderHotTopics(hotDomain);
  if (state.mode === "trending" && hotLastUpdated) {
    const timeEl = document.getElementById("hot-last-updated");
    if (timeEl) timeEl.textContent = formatHotUpdateTime();
  }
}



langToggleBtn?.addEventListener("click", toggleLanguage);

// ========== Sidebar Toggle ==========
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarContent = document.getElementById("sidebar-content");

sidebarToggle?.addEventListener("click", () => {
  sidebarContent?.classList.toggle("open");
});

// ========== 热榜定时更新 ==========

async function refreshHotData() {
  try {
    const tr = await fetch("data/trending.json?t=" + Date.now()).then(r => r.ok ? r.json() : null);
    if (tr?.trends) {
      trendingData = tr.trends;
      hotLastUpdated = new Date();
      if (state.mode === "trending") {
        renderHotTopics(hotDomain);
        const timeEl = document.getElementById("hot-last-updated");
        if (timeEl) timeEl.textContent = formatHotUpdateTime();
      }
    }
  } catch (e) {
    console.warn("刷新热榜数据失败", e);
  }
}

function startHotUpdateInterval() {
  if (hotUpdateInterval) clearInterval(hotUpdateInterval);
  hotUpdateInterval = setInterval(() => {
    if (state.mode === "trending") {
      refreshHotData();
    }
  }, 86400000); // 每24小时更新一次
}

// 初始化主题
applyTheme(localStorage.getItem("theme") || "system");

// ========== 初始化 ==========
updateFavCount();
// 初始化语言（默认英文）
updateLangButton();
updateUI();
reload();
loadDashboard();
startHotUpdateInterval();
