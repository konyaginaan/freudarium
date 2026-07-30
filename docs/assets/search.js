// Клиент поиска на pagefind (индекс собирается на этапе сборки в /pagefind/).
(function () {
  "use strict";
  var SITE_BASE = window.__SITE_BASE__ || "";
  var input = document.getElementById("searchInput");
  var resultsEl = document.getElementById("searchResults");
  var emptyEl = document.getElementById("searchEmpty");
  var filtersEl = document.getElementById("searchFilters");
  if (!input) return;

  var activeType = "";
  var pagefind = null;
  var debounceTimer = null;

  var TYPE_LABEL = {
    "заметка": "Заметка",
    "работа": "Работа",
    "полный текст": "Полный текст",
    "карта": "Карта области",
  };

  async function getPagefind() {
    if (pagefind) return pagefind;
    pagefind = await import(SITE_BASE + "/pagefind/pagefind.js");
    await pagefind.init();
    return pagefind;
  }

  function render(results) {
    resultsEl.innerHTML = "";
    emptyEl.hidden = results.length > 0;
    results.forEach(function (r) {
      var a = document.createElement("a");
      a.className = "search-result";
      a.href = r.url;
      var work = r.filters && r.filters.work ? r.filters.work[0] : null;
      var type = r.filters && r.filters.type ? r.filters.type[0] : null;
      var kicker = [type ? TYPE_LABEL[type] || type : null, work].filter(Boolean).join(" · ");
      a.innerHTML =
        (kicker ? '<span class="sr-kicker">' + kicker + "</span>" : "") +
        "<span>" + (r.meta && r.meta.title ? r.meta.title : r.url) + "</span>" +
        '<span class="sr-excerpt">' + r.excerpt + "</span>";
      resultsEl.appendChild(a);
    });
  }

  async function runSearch() {
    var query = input.value.trim();
    if (!query) {
      resultsEl.innerHTML = "";
      emptyEl.hidden = true;
      return;
    }
    var pf = await getPagefind();
    var opts = activeType ? { filters: { type: activeType } } : {};
    var search = await pf.search(query, opts);
    var results = await Promise.all(
      search.results.slice(0, 40).map(function (r) { return r.data(); })
    );
    render(results);
  }

  input.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runSearch, 150);
  });

  if (filtersEl) {
    filtersEl.addEventListener("click", function (e) {
      var btn = e.target.closest(".search-filter");
      if (!btn) return;
      filtersEl.querySelectorAll(".search-filter").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      activeType = btn.getAttribute("data-type") || "";
      runSearch();
    });
  }

  // ?q=... в URL — прямой переход из шапки другой страницы (пока не используется,
  // задел на будущее: ссылка «искать «слово»» из карточки тега и т.п.)
  var params = new URLSearchParams(location.search);
  if (params.get("q")) {
    input.value = params.get("q");
    runSearch();
  }
  input.focus();
})();
