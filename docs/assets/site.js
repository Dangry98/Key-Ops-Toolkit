// Key Ops: Toolkit docs: navigation, search, theme and lightbox.
// NAV is the single source of truth for the sidebar and the search index.
// Keep feature ids in sync with the links in addon_preferences.py.
const VERSION = "0.2.7";
const LINKS = {
  download: "https://extensions.blender.org/add-ons/key-ops-toolkit/",
  github: "https://github.com/Dangry98/Key-Ops-Toolkit",
  forum: "https://blenderartists.org/t/key-ops-toolkit-open-alpha/1517413",
};

const NAV = [
  { page: "index.html", title: "Overview", items: [
    ["sections", "Sections"],
  ]},
  { page: "industry-standard.html", title: "Industry Standard", items: [
    ["alt-navigation", "Alt Navigation"], ["select-island", "Double Click Select Island"], ["auto-delete", "Auto Delete"],
    ["maya-pivot", "Maya Pivot"], ["toggle-retopology", "Toggle Retopology"],
  ]},
  { page: "modeling-tools.html", title: "Modeling Tools", items: [
    ["merge-tool", "Merge Tool"], ["fast-loop-cut", "Fast Loop Cut"], ["cutter", "Cutter"], ["fast-mirror", "Fast Mirror"],
    ["fast-bevel", "Fast Bevel"], ["fast-array", "Fast Array"], ["fast-solidify", "Fast Solidify"], ["booleans", "Booleans"],
    ["snap-to-floor", "Snap to Floor"], ["select-similar", "Select Similar"], ["x-ray-select", "X-Ray Select"],
  ]},
  { page: "pie-menus.html", title: "Pie Menus", items: [
    ["add-objects-pie", "Add Objects Pie"], ["add-modifier-pie", "Add Modifier Pie"], ["cursor-pie", "Cursor Pie"],
    ["flatten-pie", "Flatten Pie"], ["workspace-pie", "Workspace Pie"], ["view-camera-pie", "View Camera Pie"],
    ["utility-pie", "Utility Pie"], ["uv-pies", "UV Pies"],
  ]},
  { page: "toolkit.html", title: "Toolkit Panel", items: [
    ["toolkit-panel", "Toolkit Panel"], ["object-toolkit", "Object Toolkit"], ["edit-toolkit", "Edit Toolkit"],
    ["cad-decimate", "CAD Decimate"], ["auto-lod", "Auto LOD"], ["polycount-list", "Polycount List"],
    ["quick-bake-name", "Quick Bake Name"], ["quick-export", "Quick Export"], ["material-utils", "Material Utils"],
  ]},
  { page: "uv.html", title: "UV", items: [
    ["uv-tools", "UV Tools"], ["smart-uv-sync", "Smart UV Sync"], ["uv-cut", "UV Cut"], ["remove-seam", "Remove Seam"],
  ]},
  { page: "extras.html", title: "Extras", items: [
    ["fast-merge", "Fast Merge & Connect"], ["modifier-key", "Modifier Key"], ["attribute-operations", "Attribute Operations"],
    ["viewport-menu", "Viewport Menu"], ["outliner-options", "Outliner Options"], ["legacy-shortcuts", "Legacy Shortcuts"],
    ["looptools-menu", "LoopTools Menu"],
  ]},
  { page: "preferences.html", title: "Preferences", items: [
    ["extensions-tab", "Extensions / Settings"], ["keymaps-tab", "Keymaps"], ["rebind-tab", "Rebind"], ["experimental", "Experimental"],
  ]},
  { page: "shortcuts.html", title: "Shortcut Cheat Sheet", items: [] },
];

(function () {
  const here = document.body.dataset.page || "index.html";
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---------- theme ----------
  const root = document.documentElement;
  const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  function toggleTheme() {
    root.dataset.theme = isDark() ? "light" : "dark";
    try { localStorage.setItem("kot-theme", root.dataset.theme); } catch (e) {}
    themeBtn.innerHTML = themeIcon();
  }
  const themeIcon = () => isDark()
    ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  // ---------- top bar ----------
  const top = document.getElementById("topbar");
  top.className = "topbar";
  top.innerHTML = `
    <button class="icon-btn menu-btn" aria-label="Open navigation"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>
    <a class="brand" href="index.html" aria-label="Key Ops: Toolkit home"><img class="brand-icon" src="assets/icon-k.svg" alt="" width="32" height="32"><span class="brand-name">Key Ops <span class="brand-sub">Toolkit</span></span><span class="version">v${VERSION}</span></a>
    <div class="search-wrap">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input type="search" placeholder="Search features…  ( / )" aria-label="Search features">
      <div class="search-results" role="listbox"></div>
    </div>
    <div class="top-links">
      <a class="hide-sm" href="${LINKS.forum}" target="_blank" rel="noopener">Forum</a>
      <a class="hide-sm" href="${LINKS.github}" target="_blank" rel="noopener">GitHub</a>
      <button class="icon-btn keep theme-btn" aria-label="Toggle dark mode"></button>
      <a class="primary" href="${LINKS.download}" target="_blank" rel="noopener">Download</a>
    </div>`;
  const themeBtn = top.querySelector(".theme-btn");
  themeBtn.innerHTML = themeIcon();
  themeBtn.addEventListener("click", toggleTheme);
  top.querySelector(".menu-btn").addEventListener("click", () => document.body.classList.toggle("nav-open"));

  // ---------- sidebar ----------
  const side = document.getElementById("sidebar");
  side.className = "sidebar";
  side.setAttribute("aria-label", "Documentation");
  side.innerHTML = NAV.map((g) => {
    const cur = g.page === here;
    const items = g.items.length
      ? `<ul>${g.items.map(([id, t]) => `<li><a href="${g.page}#${id}" data-id="${cur ? id : ""}">${esc(t)}</a></li>`).join("")}</ul>` : "";
    return `<div class="group"><a class="page-link${cur ? " current" : ""}" href="${g.page}">${esc(g.title)}</a>${cur ? items : ""}</div>`;
  }).join("");
  side.addEventListener("click", (e) => { if (e.target.closest("a")) document.body.classList.remove("nav-open"); });

  // highlight the section in view
  const links = [...side.querySelectorAll("a[data-id]")].filter((a) => a.dataset.id);
  const sections = links.map((a) => document.getElementById(a.dataset.id)).filter(Boolean);
  if (sections.length && "IntersectionObserver" in window) {
    const vis = new Set();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => en.isIntersecting ? vis.add(en.target.id) : vis.delete(en.target.id));
      const first = sections.find((s) => vis.has(s.id));
      if (first) links.forEach((a) => a.classList.toggle("active", a.dataset.id === first.id));
    }, { rootMargin: "-70px 0px -55% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  // ---------- pager ----------
  const idx = NAV.findIndex((g) => g.page === here);
  const pager = document.getElementById("pager");
  if (pager && idx >= 0) {
    const prev = NAV[idx - 1], next = NAV[idx + 1];
    pager.className = "pager";
    pager.innerHTML = (prev ? `<a class="prev" href="${prev.page}"><small>Previous</small>${esc(prev.title)}</a>` : "<span></span>")
      + (next ? `<a class="next" href="${next.page}"><small>Next</small>${esc(next.title)}</a>` : "");
  }

  // ---------- anchors on feature headings ----------
  document.querySelectorAll(".feature[id] > .feature-head h2").forEach((h) => {
    const id = h.closest(".feature").id;
    h.innerHTML = `<a class="anchor" href="#${id}">${h.innerHTML}</a>`;
  });

  // ---------- search ----------
  const index = [];
  NAV.forEach((g) => {
    index.push({ t: g.title, p: g.title, u: g.page });
    g.items.forEach(([id, t]) => index.push({ t, p: g.title, u: `${g.page}#${id}` }));
  });
  const input = top.querySelector("input"), box = top.querySelector(".search-results");
  let sel = 0, hits = [];
  function render() {
    const q = input.value.trim().toLowerCase();
    if (!q) { box.classList.remove("open"); return; }
    const words = q.split(/\s+/);
    hits = index.filter((e) => words.every((w) => (e.t + " " + e.p).toLowerCase().includes(w))).slice(0, 12);
    sel = 0;
    box.innerHTML = hits.length
      ? hits.map((h, i) => `<a href="${h.u}" class="${i === 0 ? "active" : ""}">${esc(h.t)}<small>${esc(h.p)}</small></a>`).join("")
      : `<div class="empty">No feature matches “${esc(q)}”</div>`;
    box.classList.add("open");
  }
  input.addEventListener("input", render);
  input.addEventListener("focus", render);
  input.addEventListener("keydown", (e) => {
    const as = [...box.querySelectorAll("a")];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); if (!as.length) return;
      sel = (sel + (e.key === "ArrowDown" ? 1 : as.length - 1)) % as.length;
      as.forEach((a, i) => a.classList.toggle("active", i === sel));
    } else if (e.key === "Enter" && as[sel]) { location.href = as[sel].href; box.classList.remove("open"); input.blur(); }
    else if (e.key === "Escape") { input.value = ""; box.classList.remove("open"); input.blur(); }
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search-wrap")) box.classList.remove("open"); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== input && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); input.focus(); }
  });

  // ---------- media: placeholders + lightbox ----------
  document.querySelectorAll(".media-missing").forEach((m) => {
    m.insertAdjacentHTML("afterbegin", '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="5" width="15" height="14" rx="2"/><path d="m17 10 5-3v10l-5-3"/></svg>');
  });
  document.querySelectorAll(".media img").forEach((img) => {
    img.classList.add("zoomable");
    img.addEventListener("click", () => {
      const lb = document.createElement("div");
      lb.className = "lightbox"; lb.innerHTML = `<img src="${img.src}" alt="${esc(img.alt || "")}">`;
      lb.addEventListener("click", () => lb.remove());
      document.addEventListener("keydown", function k(e) { if (e.key === "Escape") { lb.remove(); document.removeEventListener("keydown", k); } });
      document.body.appendChild(lb);
    });
  });

  const y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
})();
