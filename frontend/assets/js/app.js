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

// 可用年份（由 meta.json 决定；初始值兜底，过滤掉未来年份）
const _currentYear = new Date().getFullYear();
let availableYears = [2023, 2024, 2025, 2026, 2027].filter(y => y <= _currentYear);

// 静态 arxiv 数据 (速览模式)
// 优先加载最近 2 年并立即返回，旧年份后台补全后回调触发重渲染
let feedPapersCache = null;
let _feedFullyLoaded = false;

function _normalizeId(id) {
  // "2406.14806v1" → "2406.14806"；其他格式（arxiv:xxx, s2:xxx 等）不变
  return id ? String(id).replace(/v\d+$/, "") : id;
}

function _dedupeById(arr) {
  const seen = new Set();
  return arr.filter(p => {
    if (!p || !p.id) return false;
    const key = _normalizeId(p.id);
    return !seen.has(key) && seen.add(key);
  });
}

async function loadFeedPapers(onBackgroundDone) {
  if (feedPapersCache && _feedFullyLoaded) return feedPapersCache;
  if (feedPapersCache) return feedPapersCache; // 后台还在加载，返回已有数据

  const sorted = [...availableYears].sort((a, b) => b - a); // 最新年份优先
  const priority = sorted.slice(0, 2);   // e.g. [2026, 2025]
  const rest     = sorted.slice(2);      // e.g. [2024, 2023]

  const firstBatch = await Promise.all(
    priority.map(y => fetch(`data/papers_${y}.json`).then(r => r.ok ? r.json() : []).catch(() => []))
  );
  feedPapersCache = _dedupeById(firstBatch.flat());

  if (rest.length) {
    Promise.all(
      rest.map(y => fetch(`data/papers_${y}.json`).then(r => r.ok ? r.json() : []).catch(() => []))
    ).then(results => {
      feedPapersCache = _dedupeById([...feedPapersCache, ...results.flat()]);
      _feedFullyLoaded = true;
      if (typeof onBackgroundDone === "function") onBackgroundDone();
    });
  } else {
    _feedFullyLoaded = true;
  }

  return feedPapersCache;
}

// 静态精选数据 (精选模式)
// 按选中领域按需加载，缓存分领域存储，避免一次下载所有 ~220MB
const CURATED_DOMAINS_ALL = ["world_model", "physical_ai", "medical_ai"];
const _curatedCache = {};       // domain-key → paper[]
const _curatedLoaded = {};      // domain-key → bool

function _mergeCurated(lists) {
  const seen = new Set();
  const merged = [];
  for (const list of lists) {
    for (const p of list) {
      if (p.id && !seen.has(p.id)) { seen.add(p.id); merged.push(p); }
    }
  }
  return merged.map(normalizeCurated);
}

async function loadCuratedPapers(domain = "all") {
  const key = domain;
  if (_curatedCache[key] && _curatedLoaded[key]) return _curatedCache[key];
  if (_curatedCache[key]) return _curatedCache[key];

  const domainsToLoad = domain === "all" ? CURATED_DOMAINS_ALL : [domain];
  const files = domainsToLoad.flatMap(d =>
    availableYears.map(y => `data/papers_curated_${d}_${y}.json`)
  );
  const results = await Promise.all(
    files.map(f => fetch(f).then(r => r.ok ? r.json() : []).catch(() => []))
  );

  _curatedCache[key] = _mergeCurated(results);
  _curatedLoaded[key] = true;
  return _curatedCache[key];
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
    $("#filter-venue").innerHTML = `<option value="">${t('allVenues')}</option>`;
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
  const unique = _dedupeById(papers);
  if (!unique.length) {
    list.innerHTML = `<div class="loading">${t('noPapers')}</div>`;
    return;
  }
  list.innerHTML = unique.map(paperCard).join("");
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
let radarData = {};           // { world_model: {points, scores}, ... }
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
    if (tr?.radar)  radarData   = tr.radar;
    if (tr?.stats)  { renderStats(tr.stats); renderTrends(tr.stats.trends); }
    if (tm?.tasks) taskMeta = tm.tasks;
    if (tm?.domain_tasks && Object.keys(tm.domain_tasks).length) domainTasks = tm.domain_tasks;
    if (meta?.years?.length) {
      availableYears = meta.years.filter(y => y <= _currentYear);
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
  // Mark data as freshly loaded and show time
  hotLastUpdated = new Date();
  const timeEl = document.getElementById("hot-last-updated");
  if (timeEl) timeEl.textContent = formatHotUpdateTime();
  renderHotTopics(hotDomain);
  renderRadar();
  renderTopicCards();
  renderSubdomain();
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
    setCard(d, s.domains[d], s.recent[d]);
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

// ── Radar chart (data-driven) ─────────────────────────────────────────────────
function renderRadar() {
  const domains = [
    { id: "world_model",  sel: ".world-model-radar",  color: "#6366f1" },
    { id: "physical_ai",  sel: ".physical-ai-radar",   color: "#10b981" },
    { id: "medical_ai",   sel: ".medical-ai-radar",    color: "#f43f5e" },
  ];
  domains.forEach(({ id, sel }) => {
    const el = document.querySelector(sel);
    if (!el) return;
    const pts = radarData[id]?.points;
    if (pts) el.setAttribute("points", pts);
  });
}

// ── Topic cards (data-driven) ─────────────────────────────────────────────────
const DOMAIN_META = {
  world_model:  { label: "World Model",  icon: "🌍", cls: "world-model-topic",  color: "#6366f1" },
  physical_ai:  { label: "Physical AI",  icon: "🤖", cls: "physical-ai-topic",  color: "#10b981" },
  medical_ai:   { label: "Medical AI",   icon: "🏥", cls: "medical-ai-topic",   color: "#f43f5e" },
};
const TOPIC_ICONS = ["🎬","✨","🌊","🦾","💊","🩻","🔬","🧠","⚡","🛸"];

function renderTopicCards() {
  const grid = document.querySelector(".topics-grid");
  if (!grid) return;
  if (!Object.keys(trendingData).length) return; // not loaded yet

  const maxCount = Math.max(
    ...Object.values(trendingData).flatMap(ts => ts.map(t => t.count)), 1
  );

  const cards = [];
  ["world_model", "physical_ai", "medical_ai"].forEach(domain => {
    const topics = (trendingData[domain] || []).slice(0, 2);
    const meta = DOMAIN_META[domain];
    topics.forEach((topic, i) => {
      const heat = Math.round(topic.count / maxCount * 100);
      const tag = i === 0 ? t("coreHotspot") : t("emergingHotspot");
      const icon = TOPIC_ICONS[cards.length % TOPIC_ICONS.length];
      cards.push(`
        <div class="topic-card ${meta.cls}">
          <div class="topic-header">
            <span class="topic-icon">${icon}</span>
            <div class="topic-title-row">
              <h3>${esc(topic.display)}</h3>
              <span class="topic-tag">${tag}</span>
            </div>
          </div>
          <div class="topic-metrics">
            <span class="metric">🔥 <span data-i18n="heatIndex">${t("heatIndex")}</span>: ${heat}/100</span>
            <span class="metric">📄 ${topic.count} ${t("articles")}</span>
          </div>
          <div class="topic-keywords">
            ${topic.term.split(" ").map(w => `<span>${esc(w)}</span>`).join("")}
          </div>
        </div>`);
    });
  });

  grid.innerHTML = cards.join("");
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
      document.body.classList.remove("mode-deadlines");
      stopDdlTicker();
      stopDdlRefresh();
      // 热榜模式：显示热榜视图，隐藏论文列表
      $("#trending-view").hidden = false;
      $("#paper-list").hidden = true;
      $("#dashboard").hidden = true;
      $("#deadlines-view").hidden = true;
      // 初始化更新时间
      if (!hotLastUpdated) {
        await refreshHotData();
      } else {
        const timeEl = document.getElementById("hot-last-updated");
        if (timeEl) timeEl.textContent = formatHotUpdateTime();
      }
    } else if (state.mode === "deadlines") {
      document.body.classList.add("mode-deadlines");
      $("#trending-view").hidden = true;
      $("#paper-list").hidden = true;
      $("#dashboard").hidden = true;
      $("#deadlines-view").hidden = false;
      await loadAndRenderDeadlines();
    } else {
      document.body.classList.remove("mode-deadlines");
      stopDdlTicker();
      stopDdlRefresh();
      // 其他模式：显示论文列表，隐藏热榜视图
      $("#trending-view").hidden = true;
      $("#paper-list").hidden = false;
      $("#dashboard").hidden = state.mode !== "feed";
      $("#deadlines-view").hidden = true;

      const _loadingHint = state.mode === "feed"
        ? (currentLang === "zh" ? "加载中（最新数据优先）..." : "Loading recent papers first…")
        : (currentLang === "zh" ? "加载中..." : "Loading…");
      $("#paper-list").innerHTML = `<div class="loading">${_loadingHint}</div>`;

      if (state.mode === "feed") {
        const all = (await loadFeedPapers(() => {
          // 旧年份后台加载完成后，仅在仍处于 feed 模式时静默刷新
          if (state.mode === "feed") {
            const f2 = applyFeedFilters(feedPapersCache.map(normalizePaper));
            feedTotal = f2.length;
            render(f2.slice(0, 100));
          }
        })).map(normalizePaper);
        const filtered = applyFeedFilters(all);
        feedTotal = filtered.length;
        render(filtered.slice(0, 100));
      } else if (state.mode === "curated") {
        const all = await loadCuratedPapers(state.domain);
        const filtered = applyCuratedFilters(all);
        render(filtered.slice(0, 100));
      } else {
        const papers = await listPapers(state);
        render(papers);
      }
    }
  } catch (e) {
    if (state.mode !== "trending" && state.mode !== "deadlines") {
      $("#paper-list").innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    }
  }
}

// ========== CCF Deadlines ==========

let deadlinesCache = null;
let ddlActiveRank = "";
let ddlCheckedSubs = new Set(); // empty = all checked
let ddlHideExpired = true;
let ddlSearch = "";
let ddlPage = 0;
const DDL_PAGE_SIZE = 10;
let ddlTickTimer = null;
let ddlRefreshTimer = null;
let ddlSubsBuiltLang = "";
const DDL_REFRESH_INTERVAL = 30 * 60 * 1000; // 30 minutes

const DDL_SUB_NAMES = {
  AI: "Artificial Intelligence", CG: "Graphics & Multimedia",
  CT: "Computing Theory", DB: "Database / Data Mining",
  DS: "Computer Architecture", HI: "Human-Computer Interaction",
  MX: "Interdisciplinary", NW: "Network Systems",
  SC: "Security", SE: "Software Engineering",
};
const DDL_SUB_NAMES_ZH = {
  AI: "人工智能", CG: "计算机图形学与多媒体",
  CT: "计算机科学理论", DB: "数据库/数据挖掘/内容检索",
  DS: "计算机体系结构/并行与分布计算/存储系统", HI: "人机交互与普适计算",
  MX: "交叉/综合/新兴", NW: "计算机网络",
  SC: "网络与信息安全", SE: "软件工程/系统软件/程序设计语言",
};
function ddlSubName(s) {
  return (currentLang === "zh" ? DDL_SUB_NAMES_ZH[s] : DDL_SUB_NAMES[s]) || s;
}

async function loadAndRenderDeadlines() {
  if (!deadlinesCache) {
    try {
      const data = await fetch("data/deadlines.json?v=" + Date.now()).then(r => r.ok ? r.json() : null);
      deadlinesCache = data;
    } catch (e) {
      $("#deadlines-list").innerHTML = `<div class="loading">Failed to load</div>`;
      return;
    }
  }
  if (!deadlinesCache) {
    $("#deadlines-list").innerHTML = `<div class="loading">${t("noDeadlines")}</div>`;
    return;
  }
  buildSubCheckboxes();
  renderDeadlines();
  startDdlTicker();
  startDdlRefresh();
}

function startDdlTicker() {
  if (ddlTickTimer) return;
  ddlTickTimer = setInterval(tickCountdowns, 1000);
}

function stopDdlTicker() {
  if (ddlTickTimer) { clearInterval(ddlTickTimer); ddlTickTimer = null; }
}

function startDdlRefresh() {
  if (ddlRefreshTimer) return;
  ddlRefreshTimer = setInterval(async () => {
    deadlinesCache = null;
    ddlSubsBuiltLang = "";
    await loadAndRenderDeadlines();
  }, DDL_REFRESH_INTERVAL);
}

function stopDdlRefresh() {
  if (ddlRefreshTimer) { clearInterval(ddlRefreshTimer); ddlRefreshTimer = null; }
}

function tickCountdowns() {
  const now = new Date();
  document.querySelectorAll(".ddl-cd-live").forEach(el => {
    const dl = new Date(el.dataset.deadline);
    const ms = dl - now;
    if (ms <= 0) { el.textContent = "Expired"; return; }
    if (ms < 86400000) {
      // < 24h: show hh:mm:ss
      const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
      const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
      const s = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
      el.textContent = `${h}h ${m}m ${s}s`;
    } else {
      const days = Math.floor(ms / 86400000);
      const hours = Math.floor((ms % 86400000) / 3600000);
      el.textContent = `${days}d ${hours}h`;
    }
  });
}

function buildSubCheckboxes() {
  if (ddlSubsBuiltLang === currentLang) return;
  ddlSubsBuiltLang = currentLang;
  const container = $("#ddl-sub-filter");
  container.innerHTML = "";
  const subs = [...new Set((deadlinesCache.conferences || []).map(c => c.sub))].filter(Boolean).sort();
  if (ddlCheckedSubs.size === 0) subs.forEach(s => ddlCheckedSubs.add(s));

  // Select-all row
  const allLabel = document.createElement("label");
  allLabel.className = "ddl-check-label ddl-check-all";
  const allCb = document.createElement("input");
  allCb.type = "checkbox"; allCb.id = "ddl-cb-all";
  allCb.checked = ddlCheckedSubs.size === subs.length;
  allCb.addEventListener("change", () => {
    if (allCb.checked) {
      subs.forEach(s => ddlCheckedSubs.add(s));
    } else {
      ddlCheckedSubs.clear();
    }
    container.querySelectorAll(".ddl-sub-cb").forEach(cb => { cb.checked = allCb.checked; });
    ddlPage = 0; renderDeadlines();
  });
  allLabel.appendChild(allCb);
  allLabel.appendChild(document.createTextNode(" " + (currentLang === "zh" ? "全选" : "Select All")));
  container.appendChild(allLabel);

  // Grid of sub checkboxes
  const grid = document.createElement("div");
  grid.className = "ddl-sub-grid";
  subs.forEach(s => {
    const label = document.createElement("label");
    label.className = "ddl-check-label";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.className = "ddl-sub-cb"; cb.dataset.sub = s;
    cb.checked = ddlCheckedSubs.has(s);
    cb.addEventListener("change", () => {
      if (cb.checked) ddlCheckedSubs.add(s); else ddlCheckedSubs.delete(s);
      const allCheck = document.getElementById("ddl-cb-all");
      if (allCheck) allCheck.checked = ddlCheckedSubs.size === subs.length;
      ddlPage = 0; renderDeadlines();
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(" " + ddlSubName(s)));
    grid.appendChild(label);
  });
  container.appendChild(grid);
}

function ddlProgressBar(absDl, dl, now) {
  const start = absDl ? absDl.getTime() : dl.getTime() - 90 * 86400000;
  const end = dl.getTime();
  const span = end - start;
  if (span <= 0) return "";

  const nowMs = now.getTime();
  const pos = Math.min(100, Math.max(0, (nowMs - start) / span * 100));
  const absPos = absDl ? Math.min(100, Math.max(0, (absDl.getTime() - start) / span * 100)) : null;

  const fmtShort = d => { const m = d.getMonth()+1; const day = d.getDate(); return `${m<10?"0"+m:m}/${day<10?"0"+day:day}`; };
  const fmtFull = d => {
    const pad = n => String(n).padStart(2,"0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  const tipAlign = pct => pct < 20 ? " tip-left" : pct > 80 ? " tip-right" : "";

  const absDot = absPos !== null
    ? `<div class="ddl-pb-dot ddl-pb-abstract${tipAlign(absPos)}" style="left:${absPos}%" data-tip="Abstract: ${fmtFull(absDl)}"></div>`
    : "";
  const nowDot = `<div class="ddl-pb-dot ddl-pb-now${tipAlign(pos)}" style="left:${pos}%" data-tip="${fmtFull(now)}"></div>`;
  const endDot = `<div class="ddl-pb-dot ddl-pb-end" style="left:100%" data-tip="Deadline: ${fmtFull(dl)}"><span class="ddl-pb-end-label">${fmtShort(dl)}</span></div>`;

  return `<div class="ddl-progress">
    <div class="ddl-pb-track">
      <div class="ddl-pb-past" style="width:${pos}%"></div>
      <div class="ddl-pb-future" style="left:${pos}%;width:${100-pos}%"></div>
      ${absDot}${nowDot}${endDot}
    </div>
  </div>`;
}

function renderDeadlines() {
  const now = new Date();
  const q = ddlSearch.toLowerCase();
  const all = (deadlinesCache?.conferences || []).filter(c => {
    if (ddlActiveRank === "N") { if (["A","B","C"].includes(c.ccf)) return false; }
    else if (ddlActiveRank && c.ccf !== ddlActiveRank) return false;
    if (ddlCheckedSubs.size > 0 && !ddlCheckedSubs.has(c.sub)) return false;
    if (ddlHideExpired && new Date(c.deadline) < now) return false;
    if (q && !c.title.toLowerCase().includes(q) && !c.full_name.toLowerCase().includes(q)) return false;
    return true;
  });
  // upcoming (soonest first) then expired (most recent first)
  const upcoming = all.filter(c => new Date(c.deadline) >= now);
  const expired  = all.filter(c => new Date(c.deadline) < now).reverse();
  const confs = [...upcoming, ...expired];

  const list = $("#deadlines-list");
  const pagination = $("#ddl-pagination");

  if (!confs.length) {
    list.innerHTML = `<div class="loading">${t("noDeadlines")}</div>`;
    pagination.innerHTML = "";
    return;
  }

  const totalPages = Math.ceil(confs.length / DDL_PAGE_SIZE);
  ddlPage = Math.min(ddlPage, totalPages - 1);
  const page = confs.slice(ddlPage * DDL_PAGE_SIZE, (ddlPage + 1) * DDL_PAGE_SIZE);

  list.innerHTML = page.map(c => {
    const dl = new Date(c.deadline);
    const diffMs = dl - now;
    const diffDays = Math.floor(diffMs / 86400000);
    const absDl = c.abstract_deadline ? new Date(c.abstract_deadline) : null;
    const expired = diffMs < 0;

    let cdCls = expired ? "ddl-expired" : diffDays <= 7 ? "ddl-urgent" : diffDays <= 30 ? "ddl-soon" : "ddl-ok";
    const urgencyCls = expired ? "" : diffDays <= 7 ? " is-urgent" : diffDays <= 30 ? " is-soon" : " is-ok";

    let cdText;
    if (expired) {
      cdText = `${Math.abs(diffDays)}d ago`;
    } else if (diffMs < 86400000) {
      const h = String(Math.floor(diffMs / 3600000)).padStart(2, "0");
      const m = String(Math.floor((diffMs % 3600000) / 60000)).padStart(2, "0");
      const s = String(Math.floor((diffMs % 60000) / 1000)).padStart(2, "0");
      cdText = `${h}h ${m}m ${s}s`;
    } else {
      cdText = `${diffDays}d ${Math.floor((diffMs % 86400000) / 3600000)}h`;
    }

    const rankCls = `ccf-rank-${(c.ccf||"").toLowerCase()}`;
    const ccfBadge = c.ccf && ["A","B","C"].includes(c.ccf)
      ? `<span class="ddl-rank ${rankCls}">CCF ${esc(c.ccf)}</span>`
      : `<span class="ddl-rank ccf-rank-none">Non-CCF</span>`;
    const fmtDt = d => {
      const yyyy = d.getFullYear(), mm = String(d.getMonth()+1).padStart(2,"0"), dd = String(d.getDate()).padStart(2,"0");
      const hh = String(d.getHours()).padStart(2,"0"), mi = String(d.getMinutes()).padStart(2,"0");
      return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
    };
    const liveAttr = !expired ? ` data-deadline="${c.deadline}"` : "";

    return `<div class="ddl-card${expired ? " ddl-card-expired" : urgencyCls}">
      <div class="ddl-card-main">
        <div class="ddl-card-info">
          <div class="ddl-name">${esc(c.title)} <span class="ddl-year">${c.year}</span></div>
          ${c.date || c.place ? `<div class="ddl-meta">${[c.date, c.place].filter(Boolean).map(esc).join(" · ")}</div>` : ""}
          <div class="ddl-fullname">${esc(c.full_name)}</div>
          <div class="ddl-badges">
            ${ccfBadge}
            <span class="ddl-sub-tag">${esc(c.sub)}</span>
            ${c.comment ? `<span class="ddl-note"><span class="ddl-note-prefix">NOTE:</span> ${esc(c.comment)}</span>` : ""}
          </div>
          <div class="ddl-sub-plain">${esc(ddlSubName(c.sub))}</div>
        </div>
        <div class="ddl-card-timing">
          <div class="ddl-countdown ${cdCls}"><span class="ddl-cd-live"${liveAttr}>${cdText}</span></div>
          ${absDl ? `<div class="ddl-timing-row"><span class="ddl-label">Abstract</span> ${fmtDt(absDl)} <span class="ddl-tz">${esc(c.timezone)}</span></div>` : ""}
          <div class="ddl-timing-row"><span class="ddl-label">Deadline</span> ${fmtDt(dl)} <span class="ddl-tz">${esc(c.timezone)}</span></div>
          ${c.link ? `<div class="ddl-timing-row"><span class="ddl-label">Website</span> <a href="${esc(c.link)}" target="_blank" rel="noopener" class="ddl-site-link">${esc(c.link.replace(/^https?:\/\//,""))}</a></div>` : ""}
        </div>
      </div>
      ${ddlProgressBar(absDl, dl, now)}
    </div>`;
  }).join("");

  // Pagination bar with page number buttons
  const goTo = p => { ddlPage = p; renderDeadlines(); $("#deadlines-view").scrollIntoView({behavior:"smooth", block:"start"}); };
  const MAX_BTNS = 7;
  let pages = [];
  if (totalPages <= MAX_BTNS) {
    pages = Array.from({length: totalPages}, (_, i) => i);
  } else {
    // always show first, last, current ±1, with ellipsis
    const set = new Set([0, totalPages-1, ddlPage, ddlPage-1, ddlPage+1].filter(p => p >= 0 && p < totalPages));
    pages = [...set].sort((a,b) => a-b);
  }
  let pgHtml = `<button class="ddl-pg-btn" ${ddlPage===0?"disabled":""} data-p="${ddlPage-1}">&#8592;</button>`;
  let prev = -1;
  for (const p of pages) {
    if (prev !== -1 && p > prev + 1) pgHtml += `<span class="ddl-pg-ellipsis">…</span>`;
    pgHtml += `<button class="ddl-pg-btn${p===ddlPage?" active":""}" data-p="${p}">${p+1}</button>`;
    prev = p;
  }
  pgHtml += `<button class="ddl-pg-btn" ${ddlPage>=totalPages-1?"disabled":""} data-p="${ddlPage+1}">&#8594;</button>`;
  pgHtml += currentLang === "en"
    ? `<span class="ddl-pg-total">${confs.length} total</span>`
    : `<span class="ddl-pg-total">共 ${confs.length} 条</span>`;
  pagination.innerHTML = pgHtml;
  pagination.querySelectorAll(".ddl-pg-btn[data-p]").forEach(btn => {
    if (!btn.disabled) btn.addEventListener("click", () => goTo(+btn.dataset.p));
  });

  // Mobile: tap dot to toggle tooltip; tap elsewhere to dismiss
  pagination.closest("#deadlines-view").querySelectorAll(".ddl-pb-dot[data-tip]").forEach(dot => {
    dot.addEventListener("click", e => {
      e.stopPropagation();
      const active = dot.classList.contains("tip-active");
      document.querySelectorAll(".ddl-pb-dot.tip-active").forEach(d => d.classList.remove("tip-active"));
      if (!active) dot.classList.add("tip-active");
    });
  });
  if (!window._ddlDotDismiss) {
    window._ddlDotDismiss = true;
    document.addEventListener("click", () => {
      document.querySelectorAll(".ddl-pb-dot.tip-active").forEach(d => d.classList.remove("tip-active"));
    });
  }

  tickCountdowns();
}

// Deadlines filter events
document.querySelectorAll(".ddl-rank-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ddl-rank-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    ddlActiveRank = btn.dataset.rank;
    ddlPage = 0;
    if (deadlinesCache) renderDeadlines();
  });
});

$("#ddl-hide-expired")?.addEventListener("change", e => {
  ddlHideExpired = e.target.checked;
  ddlPage = 0;
  if (deadlinesCache) renderDeadlines();
});

$("#ddl-search")?.addEventListener("input", e => {
  ddlSearch = e.target.value.trim();
  ddlPage = 0;
  if (deadlinesCache) renderDeadlines();
});

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

// ── Client-side trending computation (mirrors gen_trending.py) ────────────────

const _T_STOP = new Set([
  "a","an","the","and","or","of","in","on","at","to","for","with","by","from",
  "this","that","is","are","was","were","be","been","have","has","do","does",
  "we","our","it","its","they","which","as","such","can","also","not","but",
  "than","based","proposed","approach","method","model","models","paper",
  "propose","presents","present","show","shows","use","using","used","results",
  "demonstrate","work","however","state","art","two","three","new","novel",
  "existing","recent","learning","deep","neural","network","networks","data",
  "task","tasks","training","trained","large","high","low","via","into","each",
  "both","across","while","without","further","thus","extensive","experiments",
  "outperforms","significantly","achieves","benchmark","performance","evaluation",
  "superior","experimental","https","github","http","com","available","code",
  "page","project","arxiv","www","pdes","pinns","pinn","odes",
]);
const _T_NORM = {images:"image",models:"model",networks:"network",equations:"equation",methods:"method",agents:"agent",fields:"field",operators:"operator",algorithms:"algorithm",systems:"system",problems:"problem",tasks:"task"};
const _T_BP = /extensive experiment|state.of.the.art|code available|project page|success rate|real.world|significantly outperform|achieves state|available https|github com|page https/i;
const _T_UP = new Set(["pinn","fno","vla","rl","nlp","mri","ct","vae","gan","llm","vlm","nerf","ai","3d","2d","ood","cnn","rnn","gnn","gpt","ehr","wsi","oct"]);
const _T_RDIMS = [
  ["generat","diffusion","synthesis","text-to-video","text-to-image","generative","image synthesis","video generation","image generation"],
  ["physics","simulation","fluid","dynamics","pde","navier","finite element","rigid body","physical","continuum","turbulence"],
  ["control","manipulat","planning","policy","reinforcement","actuator","trajectory","locomotion","navigation","dexterous"],
  ["reasoning","chain-of-thought","inference","logic","understanding","question answer","comprehension","commonsense","causal","language model"],
  ["efficient","few-shot","zero-shot","lightweight","compress","pruning","quantization","distillation","sample efficient","low-resource"],
  ["generali","transfer","domain adapt","robustness","out-of-distribution","ood","cross-domain","unseen","distribution shift"],
];
const _T_OUTER = [[0,-170],[150,-90],[150,90],[0,170],[-150,90],[-150,-90]];

function _tTok(text) {
  return (text.toLowerCase().match(/[a-z][a-z0-9]*(?:-[a-z0-9]+)*/g) || [])
    .filter(t => !_T_STOP.has(t) && t.length > 2);
}
function _tNgrams(texts) {
  const m = new Map();
  for (const txt of texts) {
    const toks = _tTok(txt);
    for (let n = 2; n <= 3; n++)
      for (let i = 0; i <= toks.length - n; i++) {
        const g = toks.slice(i, i+n).join(" ");
        m.set(g, (m.get(g)||0) + 1);
      }
  }
  return m;
}
function _tDisplay(term) {
  return term.split(" ").map(w => _T_UP.has(w) ? w.toUpperCase() : w[0].toUpperCase()+w.slice(1)).join(" ");
}
function _tTokSet(term) {
  return new Set(term.toLowerCase().split(/[\s\-]+/).map(w => _T_NORM[w]||w));
}
function _tTopTopics(domainPapers, allNg, total) {
  const texts = domainPapers.map(p => `${p.title||""} ${p.title||""} ${(p.abstract||"").slice(0,400)}`);
  const nP = Math.max(texts.length, 1);
  const dNg = _tNgrams(texts);
  const cands = [];
  for (const [gram, freq] of [...dNg.entries()].sort((a,b) => b[1]-a[1])) {
    if (freq < 3) break;
    if (_T_BP.test(gram)) continue;
    const sp = (freq/nP) / ((allNg.get(gram)||0)/total + 1e-6);
    if (sp > 1.3) cands.push({term:gram, display:_tDisplay(gram), count:freq, specificity:Math.round(sp*100)/100});
  }
  const deduped = [];
  for (const c of cands) {
    const cW = _tTokSet(c.term); let skip = false; const reps = [];
    for (let i = 0; i < deduped.length; i++) {
      const eW = _tTokSet(deduped[i].term);
      const cInE = [...cW].every(w=>eW.has(w)), eInC = [...eW].every(w=>cW.has(w));
      if (cInE && eInC) { skip=true; break; }
      else if (eInC) reps.push(i);
      else if (cInE) { skip=true; break; }
    }
    if (skip) continue;
    for (const i of reps.sort((a,b)=>b-a)) deduped.splice(i,1);
    deduped.push(c);
    if (deduped.length >= 8) break;
  }
  return deduped;
}
function _tRadar(domainPapers) {
  const texts = domainPapers.map(p => ((p.title||"")+" "+(p.abstract||"").slice(0,300)).toLowerCase());
  const n = Math.max(texts.length,1);
  const raw = _T_RDIMS.map(kws => texts.filter(t=>kws.some(k=>t.includes(k))).length/n);
  const mx = Math.max(...raw)||1;
  return raw.map(v => Math.round(Math.min(v/mx*0.95,1)*1000)/1000);
}
function _tPoints(scores) {
  return scores.map((s,i)=>`${Math.round(240+s*_T_OUTER[i][0])},${Math.round(240+s*_T_OUTER[i][1])}`).join(" ");
}

async function computeTrendingClientSide() {
  const papers = feedPapersCache || await loadFeedPapers();
  const cutoff = new Date(); cutoff.setMonth(cutoff.getMonth()-6);
  const cutoffStr = cutoff.toISOString().slice(0,10);
  let recent = papers.filter(p=>(p.published||"")>=cutoffStr);
  if (recent.length < 100) recent = [...papers].sort((a,b)=>(b.published||"").localeCompare(a.published||"")).slice(0,800);

  const DOMS = ["world_model","physical_ai","medical_ai"];
  const allTexts = recent.map(p=>`${p.title||""} ${p.title||""} ${(p.abstract||"").slice(0,400)}`);
  const allNg = _tNgrams(allTexts);
  const total = Math.max(allTexts.length,1);

  const trends = {}, radar = {};
  for (const d of DOMS) {
    const dp = recent.filter(p=>(p._domains||[]).includes(d));
    trends[d] = _tTopTopics(dp, allNg, total);
    const sc = _tRadar(dp);
    radar[d] = {scores:sc, points:_tPoints(sc)};
  }
  return {trends, radar};
}

// 热榜手动刷新按钮
$("#hot-refresh-btn")?.addEventListener("click", async () => {
  const btn = $("#hot-refresh-btn");
  if (btn.disabled) return;
  btn.disabled = true;
  btn.style.animation = "spin 0.8s linear infinite";
  try {
    const computed = await computeTrendingClientSide();
    trendingData = computed.trends;
    radarData = computed.radar;
    hotLastUpdated = new Date();
    if (state.mode === "trending") {
      renderHotTopics(hotDomain);
      renderRadar();
      renderTopicCards();
      const timeEl = document.getElementById("hot-last-updated");
      if (timeEl) timeEl.textContent = formatHotUpdateTime();
    }
  } catch(e) {
    console.warn("Client trending failed, falling back to server", e);
    await refreshHotData();
  }
  btn.style.animation = "";
  btn.disabled = false;
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
  renderYearControls(availableYears);
  if (state.mode === "curated") {
    renderVenuePicker(state.domain);
    refreshVenueList();
  }
  if (state.mode === "trending" && hotLastUpdated) {
    const timeEl = document.getElementById("hot-last-updated");
    if (timeEl) timeEl.textContent = formatHotUpdateTime();
  }
  if (state.mode === "deadlines" && deadlinesCache) {
    ddlSubsBuiltLang = ""; // force rebuild with new language
    buildSubCheckboxes();
    renderDeadlines();
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
      if (tr?.radar) radarData = tr.radar;
      hotLastUpdated = new Date();
      if (state.mode === "trending") {
        renderHotTopics(hotDomain);
        renderRadar();
        renderTopicCards();
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
