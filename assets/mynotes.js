// Страница «Мои заметки» — читает freud:annotations (см. annotations.js) и
// рисует три списка: закладки, заметки, выделения. Экспорт заметки — в чат
// с ботом Telegram, в одном из трёх форматов (MD/DOC/текст сообщением).
(function () {
  "use strict";
  var SITE_BASE = window.__SITE_BASE__ || "";

  function fmtDate(ts) {
    return new Date(ts).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
  }

  function esc(s) {
    var div = document.createElement("div");
    div.textContent = s || "";
    return div.innerHTML;
  }

  function render() {
    var all = (window.freudAnnotationsAll ? window.freudAnnotationsAll() : []).slice().sort(function (a, b) {
      return b.createdAt - a.createdAt;
    });
    var bookmarks = all.filter(function (a) { return a.type === "bookmark"; });
    var notes = all.filter(function (a) { return a.type === "note"; });
    var highlights = all.filter(function (a) { return a.type === "highlight"; });

    document.getElementById("mynotesEmpty").hidden = all.length > 0;

    var bSec = document.getElementById("mynotesBookmarks");
    bSec.hidden = bookmarks.length === 0;
    document.getElementById("mynotesBookmarksList").innerHTML = bookmarks
      .map(function (a) {
        return (
          '<a class="row" href="' + SITE_BASE + esc(a.url) + '">' +
          '<span class="row-title">' + esc(a.pageTitle) + "</span>" +
          '<span class="row-count">' + fmtDate(a.createdAt) + "</span></a>"
        );
      })
      .join("");

    var nSec = document.getElementById("mynotesNotes");
    nSec.hidden = notes.length === 0;
    document.getElementById("mynotesNotesList").innerHTML = notes.map(renderNoteCard).join("");

    var hSec = document.getElementById("mynotesHighlights");
    hSec.hidden = highlights.length === 0;
    document.getElementById("mynotesHighlightsList").innerHTML = highlights.map(renderHighlightCard).join("");

    document.querySelectorAll("[data-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        window.freudAnnotationRemove(btn.getAttribute("data-remove"));
        render();
      });
    });
    document.querySelectorAll("[data-export-note]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openExportSheet(btn.getAttribute("data-export-note"));
      });
    });
  }

  function renderNoteCard(a) {
    return (
      '<div class="mynote-card">' +
      '<a class="mynote-page-link" href="' + SITE_BASE + esc(a.url) + '">' + esc(a.pageTitle) + "</a>" +
      (a.quote ? '<blockquote class="mynote-quote">' + esc(a.quote) + "</blockquote>" : "") +
      '<p class="mynote-comment">' + esc(a.comment) + "</p>" +
      '<div class="mynote-actions">' +
      '<span class="mynote-date">' + fmtDate(a.createdAt) + "</span>" +
      '<button class="btn" data-export-note="' + a.id + '">Отправить в чат</button>' +
      '<button class="btn" data-remove="' + a.id + '">Удалить</button>' +
      "</div></div>"
    );
  }

  function renderHighlightCard(a) {
    return (
      '<div class="mynote-card">' +
      '<a class="mynote-page-link" href="' + SITE_BASE + esc(a.url) + '">' + esc(a.pageTitle) + "</a>" +
      '<mark class="user-mark user-mark-' + esc(a.color || "bruise") + '">' + esc(a.quote) + "</mark>" +
      '<div class="mynote-actions">' +
      '<span class="mynote-date">' + fmtDate(a.createdAt) + "</span>" +
      '<button class="btn" data-remove="' + a.id + '">Удалить</button>' +
      "</div></div>"
    );
  }

  // ── экспорт заметки в чат ──
  var exportSheet = document.getElementById("exportFormatSheet");
  var exportingId = null;

  function openExportSheet(id) {
    if (!window.freudSendToChat) {
      if (window.freudToast) window.freudToast("Отправка в чат работает только внутри Telegram");
      return;
    }
    exportingId = id;
    exportSheet.hidden = false;
  }

  function findAnnotation(id) {
    return (window.freudAnnotationsAll ? window.freudAnnotationsAll() : []).find(function (a) { return a.id === id; });
  }

  function noteFileTitle(a) {
    return (a.pageTitle || "Заметка").slice(0, 60);
  }

  function buildMd(a) {
    var lines = ["# " + noteFileTitle(a), ""];
    if (a.quote) lines.push("> " + a.quote, "");
    lines.push(a.comment, "", "—", SITE_BASE + a.url);
    return lines.join("\n");
  }

  // Простейший «.doc» без внешних библиотек: Word и большинство читалок
  // открывают HTML-документ с этим MIME/расширением как обычный документ —
  // общеизвестный приём, не требующий генерации настоящего .docx (zip+XML).
  function buildDocHtml(a) {
    return (
      "<html><head><meta charset='utf-8'></head><body>" +
      "<h2>" + esc(noteFileTitle(a)) + "</h2>" +
      (a.quote ? "<blockquote><i>" + esc(a.quote) + "</i></blockquote>" : "") +
      "<p>" + esc(a.comment).replace(/\n/g, "<br>") + "</p>" +
      "<p><a href='" + location.origin + SITE_BASE + esc(a.url) + "'>" + location.origin + SITE_BASE + esc(a.url) + "</a></p>" +
      "</body></html>"
    );
  }

  if (exportSheet) {
    exportSheet.addEventListener("click", function (e) {
      if (e.target === exportSheet || e.target.closest("[data-close-sheet]")) {
        exportSheet.hidden = true;
        return;
      }
      var btn = e.target.closest("[data-export]");
      if (!btn || !exportingId) return;
      var a = findAnnotation(exportingId);
      if (!a) return;
      var format = btn.getAttribute("data-export");
      exportSheet.hidden = true;
      if (format === "md") {
        window.freudSendToChat(new Blob([buildMd(a)], { type: "text/markdown" }), noteFileTitle(a) + ".md");
      } else if (format === "doc") {
        window.freudSendToChat(new Blob([buildDocHtml(a)], { type: "application/msword" }), noteFileTitle(a) + ".doc");
      } else if (format === "text" && window.freudSendTextToChat) {
        window.freudSendTextToChat(buildMd(a));
      }
    });
  }

  render();
})();
