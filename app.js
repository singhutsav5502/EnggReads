const GENRE_ORDER = [
  "recommended",
  "engineering",
  "internal",
  "infrastructure",
  "ai",
  "security",
  "data",
  "databases",
  "frontend",
  "backend",
  "devops",
  "reliability",
  "mobile",
  "culture",
];

const state = {
  sources: [],
  genres: [],
  posts: [],
  generatedAt: null,
  query: "",
  genre: "all",
  company: "all",
};

const els = {
  filters: document.getElementById("filters"),
  feed: document.getElementById("feed"),
  count: document.getElementById("count"),
  status: document.getElementById("status"),
  q: document.getElementById("q"),
  companyList: document.getElementById("company-list"),
  sheetList: document.getElementById("sheet-list"),
  sourcesBtn: document.getElementById("sources-btn"),
  sheet: document.getElementById("sources-sheet"),
  themeBtn: document.getElementById("theme-btn"),
};

function sourceById(id) {
  return state.sources.find((s) => s.id === id);
}

function genreLabel(id) {
  return state.genres.find((g) => g.id === id)?.label || id;
}

function relativeTime(iso) {
  if (!iso) return "";
  const delta = Date.now() - Date.parse(iso);
  const mins = Math.round(delta / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function filtered() {
  const q = state.query.trim().toLowerCase();
  return state.posts.filter((post) => {
    const source = sourceById(post.sourceId);
    if (state.genre !== "all" && !(post.tags || []).includes(state.genre)) {
      return false;
    }
    if (state.company !== "all" && post.sourceId !== state.company) {
      return false;
    }
    if (!q) return true;
    const hay = `${post.title} ${source?.name || ""} ${source?.blog || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function countsByCompany() {
  const map = new Map();
  for (const post of state.posts) {
    map.set(post.sourceId, (map.get(post.sourceId) || 0) + 1);
  }
  return map;
}

function renderFilters() {
  const ids = [
    "all",
    ...GENRE_ORDER.filter((id) => state.genres.some((g) => g.id === id)),
  ];
  els.filters.innerHTML = "";
  for (const id of ids) {
    const btn = document.createElement("button");
    btn.className = "filter";
    btn.type = "button";
    btn.dataset.genre = id;
    btn.setAttribute("aria-pressed", String(state.genre === id));
    btn.textContent = id === "all" ? "All" : genreLabel(id);
    btn.addEventListener("click", () => {
      state.genre = id;
      render();
    });
    els.filters.appendChild(btn);
  }
}

function companyButton(source, count, pressed) {
  const btn = document.createElement("button");
  btn.className = "company";
  btn.type = "button";
  btn.setAttribute("aria-pressed", String(pressed));
  btn.innerHTML = `<span>${source.name}</span><span class="n">${count}</span>`;
  btn.addEventListener("click", () => {
    state.company = pressed ? "all" : source.id;
    els.sheet.close();
    render();
  });
  return btn;
}

function renderCompanies() {
  const counts = countsByCompany();
  const items = state.sources
    .map((source) => ({ source, count: counts.get(source.id) || 0 }))
    .filter((row) => row.count > 0)
    .sort((a, b) => a.source.name.localeCompare(b.source.name));

  const fill = (root) => {
    root.innerHTML = "";
    const all = document.createElement("button");
    all.className = "company";
    all.type = "button";
    all.setAttribute("aria-pressed", String(state.company === "all"));
    all.innerHTML = `<span>All</span><span class="n">${state.posts.length}</span>`;
    all.addEventListener("click", () => {
      state.company = "all";
      els.sheet.close();
      render();
    });
    const wrap = document.createElement("li");
    wrap.appendChild(all);
    root.appendChild(wrap);
    for (const { source, count } of items) {
      const li = document.createElement("li");
      li.appendChild(companyButton(source, count, state.company === source.id));
      root.appendChild(li);
    }
  };

  fill(els.companyList);
  fill(els.sheetList);
}

function renderFeed() {
  const posts = filtered();
  const company = sourceById(state.company);
  const genreBit =
    state.genre === "all" ? "all" : genreLabel(state.genre).toLowerCase();
  const companyBit = company ? company.name : "all sources";
  els.count.textContent = `${posts.length} pieces · ${genreBit} · ${companyBit}`;

  if (!posts.length) {
    els.feed.innerHTML =
      '<p class="empty">Nothing matches. Clear a filter or try another search.</p>';
    return;
  }

  els.feed.innerHTML = "";
  for (const post of posts) {
    const source = sourceById(post.sourceId);
    const a = document.createElement("a");
    a.className = "card";
    a.href = post.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const rec = source?.recommended
      ? '<span class="mark">Recommended</span>'
      : "";
    a.innerHTML = `
      <div class="meta">
        <span>${source?.name || post.sourceId}${rec}</span>
        <span>${relativeTime(post.publishedAt)}</span>
      </div>
      <h2>${escapeHtml(post.title)}</h2>
      ${post.excerpt ? `<p class="excerpt">${escapeHtml(post.excerpt)}</p>` : ""}
    `;
    els.feed.appendChild(a);
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function render() {
  renderFilters();
  renderCompanies();
  renderFeed();
}

function applyTheme(theme) {
  const next = theme === "night" ? "night" : "paper";
  document.documentElement.dataset.theme = next === "night" ? "night" : "";
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    "content",
    next === "night" ? "#121110" : "#f6f3ee",
  );
  localStorage.setItem("enggreads-theme", next);
}

function initTheme() {
  const saved =
    localStorage.getItem("enggreads-theme") ||
    localStorage.getItem("engreads-theme");
  if (saved) applyTheme(saved);
  else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    applyTheme("night");
  }
}

async function load() {
  initTheme();
  try {
    const [sourcesRes, postsRes] = await Promise.all([
      fetch("./data/sources.json"),
      fetch("./data/posts.json"),
    ]);
    if (!sourcesRes.ok) throw new Error("Could not load sources");
    const catalog = await sourcesRes.json();
    state.sources = catalog.sources || [];
    state.genres = catalog.genres || [];

    if (postsRes.ok) {
      const bundle = await postsRes.json();
      state.posts = bundle.posts || [];
      state.generatedAt = bundle.generatedAt;
    }

    if (state.generatedAt) {
      els.status.textContent = `Updated ${relativeTime(state.generatedAt)} · ${state.sources.length} sources`;
    } else {
      els.status.textContent = `${state.sources.length} sources`;
    }

    if (!state.posts.length) {
      els.feed.innerHTML =
        '<p class="empty">Feeds have not been fetched yet.</p>';
      els.count.textContent = "No posts yet";
      renderFilters();
      renderCompanies();
      return;
    }

    render();
  } catch (err) {
    els.feed.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
    els.count.textContent = "Could not load the catalog";
  }
}

els.q.addEventListener("input", () => {
  state.query = els.q.value;
  renderFeed();
});

els.sourcesBtn.addEventListener("click", () => els.sheet.showModal());
els.themeBtn.addEventListener("click", () => {
  const night = document.documentElement.dataset.theme === "night";
  applyTheme(night ? "paper" : "night");
});

load();
