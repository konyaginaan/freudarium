// Личные заметки читателя: выделения (цветом), заметки (выделение +
// комментарий) и закладки страниц. Хранятся в localStorage (freud:annotations),
// внутри Telegram лучшим усилием дублируются в CloudStorage (см. tg.js —
// тот же принцип, что и для настроек оформления). Работает на любой странице
// с телом заметки/полного текста; страница «Мои заметки» — /notes/.
(function () {
  "use strict";
  var SITE_BASE = window.__SITE_BASE__ || "";
  var KEY = "freud:annotations";
  var CONTENT_SELECTOR = ".note-body, .fulltext-body";

  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function loadAll() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveAll(list) {
    localStorage.setItem(KEY, JSON.stringify(list));
    if (window.freudCloudSyncAnnotations) window.freudCloudSyncAnnotations(list);
  }
  window.freudAnnotationsAll = loadAll;
  window.freudAnnotationsSaveAll = saveAll; // используется tg.js при слиянии с CloudStorage

  function pageUrl() {
    return location.pathname;
  }

  function add(entry) {
    var list = loadAll();
    entry.id = uid();
    entry.url = pageUrl();
    entry.pageTitle = (document.querySelector(".note-title") || {}).textContent || document.title;
    entry.createdAt = Date.now();
    list.push(entry);
    saveAll(list);
    return entry;
  }
  function remove(id) {
    saveAll(loadAll().filter(function (a) { return a.id !== id; }));
  }
  window.freudAnnotationRemove = remove;

  // ── подсветка сохранённого текста на странице ──
  // Простой посимвольный поиск по конкатенации текстовых узлов контейнера;
  // если совпадение пересекает несколько узлов (например, часть выделения
  // была курсивом) — оборачиваем каждый затронутый узел отдельно, а не всё
  // выделение целиком: Range.surroundContents не умеет пересекать границы
  // элементов, а по одному текстовому узлу — всегда можно.
  function highlightTextInContainer(container, text, className, dataId) {
    if (!text) return false;
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var fullText = "";
    var node;
    while ((node = walker.nextNode())) {
      nodes.push({ node: node, start: fullText.length });
      fullText += node.nodeValue;
    }
    var idx = fullText.indexOf(text);
    if (idx === -1) return false;
    var endIdx = idx + text.length;
    nodes
      .filter(function (n) {
        var nEnd = n.start + n.node.nodeValue.length;
        return n.start < endIdx && nEnd > idx;
      })
      .forEach(function (n) {
        var nStart = n.start;
        var from = Math.max(idx, nStart) - nStart;
        var to = Math.min(endIdx, nStart + n.node.nodeValue.length) - nStart;
        if (from >= to || !n.node.parentNode) return;
        var range = document.createRange();
        range.setStart(n.node, from);
        range.setEnd(n.node, to);
        var mark = document.createElement("mark");
        mark.className = className;
        if (dataId) mark.setAttribute("data-ann-id", dataId);
        try { range.surroundContents(mark); } catch (e) {}
      });
    return true;
  }

  function renderSavedMarks() {
    var container = document.querySelector(CONTENT_SELECTOR);
    if (!container) return;
    var mine = loadAll().filter(function (a) { return a.url === pageUrl() && a.quote; });
    mine.forEach(function (a) {
      var cls = "user-mark user-mark-" + (a.type === "note" ? "note" : a.color || "bruise");
      highlightTextInContainer(container, a.quote, cls, a.id);
    });
  }

  // ── плавающая панель при выделении текста ──
  var toolbar = document.getElementById("selToolbar");
  var composer = document.getElementById("noteComposer");
  var pendingQuote = "";

  function hideToolbar() {
    if (toolbar) toolbar.hidden = true;
  }

  function showToolbarForSelection(sel) {
    if (!toolbar) return;
    var range = sel.getRangeAt(0);
    var rect = range.getBoundingClientRect();
    // offsetHeight у скрытого (display:none) элемента всегда 0 — снять
    // hidden НАДО до замера, иначе панель встаёт поверх самого выделения
    // вместо того, чтобы висеть над ним (баг, из-за которого казалось,
    // что выделение «не работает» — панель пряталась под пальцем/курсором).
    toolbar.hidden = false;
    var top = window.scrollY + rect.top - toolbar.offsetHeight - 10;
    var left = window.scrollX + rect.left + rect.width / 2;
    toolbar.style.top = Math.max(window.scrollY + 8, top) + "px";
    toolbar.style.left = left + "px";
  }

  function handleSelectionUpdate() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
      hideToolbar();
      return;
    }
    var text = sel.toString().trim();
    if (!text || text.length > 600) {
      hideToolbar();
      return;
    }
    var container = document.querySelector(CONTENT_SELECTOR);
    if (!container || !container.contains(sel.anchorNode)) {
      hideToolbar();
      return;
    }
    pendingQuote = text;
    showToolbarForSelection(sel);
  }

  document.addEventListener("selectionchange", handleSelectionUpdate);
  // На части мобильных браузеров/вебвью selectionchange после жеста
  // выделения (долгий тап → перетаскивание маркеров) приходит с задержкой
  // или не приходит вовсе, пока палец не отпущен — дублируем на touchend/
  // mouseup с небольшой паузой, чтобы Selection успел обновиться к моменту
  // отпускания (без паузы sel.toString() иногда ещё пуст).
  ["mouseup", "touchend"].forEach(function (evt) {
    document.addEventListener(evt, function () {
      setTimeout(handleSelectionUpdate, 30);
    });
  });

  if (toolbar) {
    toolbar.addEventListener("click", function (e) {
      var colorBtn = e.target.closest("[data-color]");
      var noteBtn = e.target.closest("[data-action='note']");
      if (colorBtn) {
        add({ type: "highlight", color: colorBtn.getAttribute("data-color"), quote: pendingQuote });
        hideToolbar();
        window.getSelection().removeAllRanges();
        renderSavedMarks();
        if (window.freudToast) window.freudToast("Выделено");
      } else if (noteBtn) {
        hideToolbar();
        if (composer) {
          composer.querySelector("[name=quote]").value = pendingQuote;
          composer.querySelector("[name=comment]").value = "";
          composer.querySelector("#composerQuoteView").textContent = pendingQuote;
          composer.hidden = false;
          composer.querySelector("textarea[name=comment]").focus();
        }
      }
    });
  }

  if (composer) {
    composer.querySelector("[data-composer-save]").addEventListener("click", function () {
      var quote = composer.querySelector("[name=quote]").value;
      var comment = composer.querySelector("[name=comment]").value.trim();
      if (!comment) return;
      add({ type: "note", quote: quote, comment: comment });
      composer.hidden = true;
      window.getSelection().removeAllRanges();
      renderSavedMarks();
      if (window.freudToast) window.freudToast("Заметка сохранена");
    });
    composer.querySelector("[data-composer-cancel]").addEventListener("click", function () {
      composer.hidden = true;
    });
    composer.addEventListener("click", function (e) {
      if (e.target === composer) composer.hidden = true;
    });
  }

  // клик вне панели/композера — скрыть панель выделения (touchstart тоже:
  // на чистом тач-устройстве mousedown может не прийти вовсе)
  ["mousedown", "touchstart"].forEach(function (evt) {
    document.addEventListener(evt, function (e) {
      if (toolbar && !toolbar.hidden && !toolbar.contains(e.target)) hideToolbar();
    });
  });

  // ── закладка страницы ──
  // Показываем только там, где вообще есть что добавлять в избранное —
  // на страницах-указателях (/works/, /tags/, /search/...) кнопка бессмысленна.
  var bookmarkBtn = document.getElementById("bookmarkBtn");
  if (bookmarkBtn && document.querySelector(".note-title")) bookmarkBtn.hidden = false;
  function currentBookmark() {
    return loadAll().find(function (a) { return a.type === "bookmark" && a.url === pageUrl(); });
  }
  function updateBookmarkBtn() {
    if (!bookmarkBtn) return;
    bookmarkBtn.classList.toggle("active", !!currentBookmark());
  }
  if (bookmarkBtn) {
    bookmarkBtn.addEventListener("click", function () {
      var existing = currentBookmark();
      if (existing) {
        remove(existing.id);
        if (window.freudToast) window.freudToast("Убрано из избранного");
      } else {
        add({ type: "bookmark" });
        if (window.freudToast) window.freudToast("Добавлено в избранное");
      }
      updateBookmarkBtn();
    });
    updateBookmarkBtn();
  }

  renderSavedMarks();

  // вызывается из tg.js после слияния с облаком, чтобы перерисовать разметку
  window.freudAnnotationsRefresh = function () {
    document.querySelectorAll("mark.user-mark").forEach(function (m) {
      var parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    });
    updateBookmarkBtn();
    renderSavedMarks();
  };
})();
