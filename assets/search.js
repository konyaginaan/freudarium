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
  var pagefindFailed = false;
  var fallbackIndex = null;
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

  // pagefind — WASM + Web Worker; в вебвью Telegram (особенно iOS) это
  // иногда не запускается вовсе. Резерв — простой поиск по заголовкам/
  // тегам/работам без воркеров и WASM: беднее (не ищет внутри текста), но
  // работает везде. Переключаемся на него, если pagefind реально упал —
  // не заранее, чтобы не терять полнотекстовый поиск там, где он работает.
  async function getFallbackIndex() {
    if (fallbackIndex) return fallbackIndex;
    var r = await fetch(SITE_BASE + "/assets/search-index.json");
    fallbackIndex = await r.json();
    return fallbackIndex;
  }

  function fallbackSearch(query, type) {
    return getFallbackIndex().then(function (items) {
      var q = query.toLowerCase();
      return items
        .filter(function (it) {
          if (type && it.type !== type) return false;
          var hay = it.title.toLowerCase() + " " + (it.tags || []).join(" ").toLowerCase();
          return hay.indexOf(q) !== -1;
        })
        .slice(0, 40)
        .map(function (it) {
          return {
            url: SITE_BASE + it.url,
            meta: { title: it.title },
            excerpt: (it.tags || []).map(function (t) { return "#" + t; }).join(" "),
            filters: { type: [it.type], work: it.work ? [it.work] : [] },
          };
        });
    });
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
    if (pagefindFailed) {
      render(await fallbackSearch(query, activeType));
      return;
    }
    try {
      // Не только ошибка — иногда воркер/WASM в вебвью просто зависает,
      // не бросая исключение вовсе; таймаут ловит и этот случай тоже.
      var timeout = new Promise(function (_, reject) {
        setTimeout(function () { reject(new Error("pagefind timeout")); }, 2500);
      });
      var pf = await Promise.race([getPagefind(), timeout]);
      var opts = activeType ? { filters: { type: activeType } } : {};
      var search = await Promise.race([pf.search(query, opts), timeout]);
      var results = await Promise.all(
        search.results.slice(0, 40).map(function (r) { return r.data(); })
      );
      render(results);
    } catch (err) {
      console.warn("pagefind недоступен, переключаюсь на резервный поиск", err);
      pagefindFailed = true;
      render(await fallbackSearch(query, activeType));
    }
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
