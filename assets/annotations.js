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

  // Внутри Telegram-мини-приложения (и на iOS, и на Android) долгий тап по
  // тексту не поднимает нативное выделение вовсе — жест туда не доходит,
  // это ограничение самого клиента. Поэтому там ведём выделение сами (см.
  // «ВЫДЕЛЕНИЕ ДОЛГИМ ТАПОМ» ниже — механизм портирован из читалки Norevia,
  // ~/projects/norevia, где та же проблема решена таким же способом).
  // Проверяем именно в момент события, а не один раз при загрузке скрипта:
  // тег tg.js идёт в разметке ПОСЛЕ annotations.js и подставляет класс
  // .in-telegram позже, чем выполняется код этого файла целиком.
  function inTelegram() {
    return document.documentElement.classList.contains("in-telegram");
  }

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

  // offsetHeight у скрытого (display:none) элемента всегда 0 — снять hidden
  // НАДО до замера, иначе панель встаёт поверх самого выделения вместо того,
  // чтобы висеть над ним (баг, из-за которого казалось, что выделение «не
  // работает» — панель пряталась под пальцем/курсором).
  function positionToolbar(rect) {
    if (!toolbar) return;
    toolbar.hidden = false;
    var top = window.scrollY + rect.top - toolbar.offsetHeight - 10;
    var left = window.scrollX + rect.left + rect.width / 2;
    toolbar.style.top = Math.max(window.scrollY + 8, top) + "px";
    toolbar.style.left = left + "px";
  }
  function showToolbarForSelection(sel) {
    positionToolbar(sel.getRangeAt(0).getBoundingClientRect());
  }

  function handleSelectionUpdate() {
    // Внутри Telegram нативный Selection всегда пуст (жест туда не доходит) —
    // ведёт панель свой обработчик долгого тапа ниже.
    if (inTelegram()) return;
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

  // ── ВЫДЕЛЕНИЕ ДОЛГИМ ТАПОМ (своё, вместо нативного — только внутри Telegram) ──
  // Портировано из читалки Norevia (~/projects/norevia/index.html): та же
  // проблема (нативное выделение не поднимается в вебвью Telegram) решена
  // там точно так же — долгий тап цепляет слово под пальцем по символьным
  // смещениям, протяжка расширяет выделение до слова под пальцем, подсветка
  // во время протяжки рисуется самим (не через Range.surroundContents,
  // чтобы не мутировать DOM на каждый tick протяжки и не терять узлы карты).
  var WORD_CHAR_RE = /[\p{L}\p{M}]/u;
  var LONG_PRESS_MS = 350;
  var LONG_PRESS_SLOP = 10; // px: больше — это скролл, а не удержание

  function buildTextMap(container) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var text = "";
    var n;
    while ((n = walker.nextNode())) {
      nodes.push({ node: n, start: text.length, end: text.length + n.nodeValue.length });
      text += n.nodeValue;
    }
    return { text: text, nodes: nodes, container: container };
  }

  function caretAt(x, y) {
    if (document.caretPositionFromPoint) {
      var pos = document.caretPositionFromPoint(x, y);
      if (!pos || pos.offsetNode.nodeType !== Node.TEXT_NODE) return null;
      return { node: pos.offsetNode, offset: pos.offset };
    }
    if (document.caretRangeFromPoint) {
      var r = document.caretRangeFromPoint(x, y);
      if (!r || r.startContainer.nodeType !== Node.TEXT_NODE) return null;
      return { node: r.startContainer, offset: r.startOffset };
    }
    return null;
  }

  function wordAtPoint(x, y, map) {
    var pos = caretAt(x, y);
    if (!pos) return null;
    var holder = map.nodes.find(function (n) { return n.node === pos.node; });
    if (!holder) return null;
    var text = map.text;
    var start = holder.start + pos.offset, end = start;
    while (start > 0 && WORD_CHAR_RE.test(text[start - 1])) start--;
    while (end < text.length && WORD_CHAR_RE.test(text[end])) end++;
    var word = text.slice(start, end);
    return word ? { word: word, start: start, end: end } : null;
  }

  function rangeFromOwnOffsets(map, start, end) {
    var s = map.nodes.find(function (n) { return start >= n.start && start < n.end; });
    var e = map.nodes.find(function (n) { return end > n.start && end <= n.end; });
    if (!s || !e) return null;
    var r = document.createRange();
    r.setStart(s.node, start - s.start);
    r.setEnd(e.node, end - e.start);
    return r;
  }

  // pdf.js у Norevia режет текст на фрагменты и поэтому там склейка строк
  // была обязательна; у нас разметка проще, но выделение всё равно может
  // пересекать <em>/<code>/<mark> — Range.getClientRects() тогда тоже отдаёт
  // по прямоугольнику на фрагмент. Склеиваем те, чьи вертикальные диапазоны
  // пересекаются, в один сплошной прямоугольник на строку.
  function mergeLineRects(rects) {
    var sorted = Array.prototype.filter.call(rects, function (r) { return r.width && r.height; })
      .sort(function (a, b) { return a.top - b.top; });
    var lines = [];
    sorted.forEach(function (r) {
      var line = lines.find(function (l) { return r.top - 3 <= l.bottom && l.top - 3 <= r.bottom; });
      if (!line) { lines.push({ top: r.top, bottom: r.bottom, left: r.left, right: r.right }); return; }
      line.top = Math.min(line.top, r.top);
      line.bottom = Math.max(line.bottom, r.bottom);
      line.left = Math.min(line.left, r.left);
      line.right = Math.max(line.right, r.right);
    });
    return lines;
  }

  function ensureOwnHlLayer(container) {
    var layer = container.querySelector(":scope > .own-hl-layer");
    if (!layer) {
      layer = document.createElement("div");
      layer.className = "own-hl-layer";
      container.appendChild(layer);
    }
    return layer;
  }
  function clearPreviewRects(container) {
    var layer = container.querySelector(":scope > .own-hl-layer");
    if (layer) layer.innerHTML = "";
  }
  function renderPreviewRects(container, range) {
    clearPreviewRects(container);
    var layer = ensureOwnHlLayer(container);
    var base = container.getBoundingClientRect();
    mergeLineRects(range.getClientRects()).forEach(function (r) {
      var d = document.createElement("div");
      d.className = "own-hl-rect";
      d.style.cssText = "left:" + (r.left - base.left - 2) + "px;top:" + (r.top - base.top) + "px;" +
        "width:" + (r.right - r.left + 4) + "px;height:" + (r.bottom - r.top) + "px;";
      layer.appendChild(d);
    });
  }

  var lpTimer = null, lpOrigin = null, lpContainer = null, lpMap = null, lpAnchor = null;
  var selecting = false;
  var customSelection = null; // {container, map, start, end, text}

  function cancelLongPress() {
    clearTimeout(lpTimer);
    lpTimer = null;
    lpOrigin = null;
  }

  function clearCustomSelection() {
    if (customSelection) clearPreviewRects(customSelection.container);
    customSelection = null;
  }

  function applyCustomSelection(container, map, start, end) {
    var range = rangeFromOwnOffsets(map, start, end);
    if (!range) return;
    customSelection = { container: container, map: map, start: start, end: end, text: map.text.slice(start, end) };
    renderPreviewRects(container, range);
  }

  function beginOwnSelection(x, y) {
    if (!lpMap) return;
    var word = wordAtPoint(x, y, lpMap);
    if (!word) return;
    selecting = true;
    lpAnchor = word;
    applyCustomSelection(lpContainer, lpMap, word.start, word.end);
    try {
      var tgApp = window.Telegram && window.Telegram.WebApp;
      if (tgApp && tgApp.HapticFeedback) tgApp.HapticFeedback.impactOccurred("light");
    } catch (e) {}
  }

  function extendOwnSelection(x, y) {
    if (!selecting || !lpMap || !lpAnchor) return;
    var word = wordAtPoint(x, y, lpMap);
    if (!word) return;
    // Слово под пальцем захватываем целиком, только если палец прошёл его
    // середину — иначе на конце абзаца выделение утаскивало первое слово
    // следующего.
    var start = word.start, end = word.end;
    var range = rangeFromOwnOffsets(lpMap, word.start, word.end);
    if (range) {
      var r = range.getBoundingClientRect();
      if (r.width) {
        var pastMiddle = x > r.left + r.width / 2;
        if (word.start >= lpAnchor.end && !pastMiddle) end = word.start;
        else if (word.end <= lpAnchor.start && pastMiddle) start = word.end;
      }
    }
    applyCustomSelection(lpContainer, lpMap, Math.min(lpAnchor.start, start), Math.max(lpAnchor.end, end));
  }

  function finishOwnPointer() {
    cancelLongPress();
    if (!selecting) return;
    selecting = false;
    lpAnchor = null;
    if (customSelection) {
      pendingQuote = customSelection.text;
      var range = rangeFromOwnOffsets(customSelection.map, customSelection.start, customSelection.end);
      if (range) positionToolbar(range.getBoundingClientRect());
    }
  }

  document.addEventListener("pointerdown", function (e) {
    if (!inTelegram()) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    var container = e.target.closest && e.target.closest(CONTENT_SELECTOR);
    // Тап вне контейнера с текстом (в т.ч. по самой панели) не должен
    // сбрасывать уже готовое выделение — только новый тап ПО ТЕКСТУ его снимает.
    if (!container) { lpMap = null; return; }
    if (customSelection) clearCustomSelection();
    lpContainer = container;
    lpMap = buildTextMap(container);
    lpOrigin = { x: e.clientX, y: e.clientY };
    clearTimeout(lpTimer);
    lpTimer = setTimeout(function () { beginOwnSelection(lpOrigin.x, lpOrigin.y); }, LONG_PRESS_MS);
  });
  document.addEventListener("pointermove", function (e) {
    if (!inTelegram()) return;
    if (selecting) { extendOwnSelection(e.clientX, e.clientY); return; }
    if (lpOrigin && Math.hypot(e.clientX - lpOrigin.x, e.clientY - lpOrigin.y) > LONG_PRESS_SLOP) {
      cancelLongPress();
    }
  });
  document.addEventListener("pointerup", function () {
    if (!inTelegram()) return;
    finishOwnPointer();
  });
  document.addEventListener("pointercancel", function () {
    if (!inTelegram()) return;
    if (selecting) finishOwnPointer(); else cancelLongPress();
  });
  // Пока тянут выделение, страница не должна ехать под пальцем.
  document.addEventListener("touchmove", function (e) {
    if (inTelegram() && selecting) e.preventDefault();
  }, { passive: false });
  // На части Android-клиентов долгий тап всё же успевает поднять нативные
  // «синие маркеры»/меню раньше нашего таймера — глушим их зарождение внутри
  // текста заметки, чтобы не соревновались с собственным выделением.
  document.addEventListener("selectstart", function (e) {
    if (!inTelegram()) return;
    var el = e.target && (e.target.nodeType === Node.TEXT_NODE ? e.target.parentElement : e.target);
    if (el && el.closest && el.closest(CONTENT_SELECTOR)) e.preventDefault();
  });
  document.addEventListener("contextmenu", function (e) {
    if (!inTelegram()) return;
    if (e.target && e.target.closest && e.target.closest(CONTENT_SELECTOR)) e.preventDefault();
  });

  if (toolbar) {
    toolbar.addEventListener("click", function (e) {
      var colorBtn = e.target.closest("[data-color]");
      var noteBtn = e.target.closest("[data-action='note']");
      if (colorBtn) {
        add({ type: "highlight", color: colorBtn.getAttribute("data-color"), quote: pendingQuote });
        hideToolbar();
        window.getSelection().removeAllRanges();
        clearCustomSelection();
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
      clearCustomSelection();
      renderSavedMarks();
      if (window.freudToast) window.freudToast("Заметка сохранена");
    });
    composer.querySelector("[data-composer-cancel]").addEventListener("click", function () {
      composer.hidden = true;
      clearCustomSelection();
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
