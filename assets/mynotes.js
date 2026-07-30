// Страница «Мои заметки» — читает freud:annotations (см. annotations.js) и
// рисует три списка: закладки, заметки, выделения. Экспорт заметки — в чат
// с ботом Telegram (лист выбора формата и вся логика сборки MD/DOC теперь
// общие в annotations.js, т.к. нужны и в панели выделения на любой странице —
// здесь только вызываем window.freudOpenExportSheet(id)).
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
        if (window.freudOpenExportSheet) window.freudOpenExportSheet(btn.getAttribute("data-export-note"));
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
      (a.comment ? '<p class="mynote-comment">' + esc(a.comment) + "</p>" : "") +
      '<div class="mynote-actions">' +
      '<span class="mynote-date">' + fmtDate(a.createdAt) + "</span>" +
      '<button class="btn" data-export-note="' + a.id + '">Отправить в чат</button>' +
      '<button class="btn" data-remove="' + a.id + '">Удалить</button>' +
      "</div></div>"
    );
  }

  render();
})();
