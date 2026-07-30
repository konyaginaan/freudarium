// Страница «Мои заметки» — читает freud:annotations (см. annotations.js) и
// рисует ОДИН общий список (закладки, выделения, заметки с комментарием —
// вперемешку, по дате). Раньше были три отдельных раздела (Закладки/Заметки/
// Выделения) — по просьбе пользователя объединено в один, чтобы не плодить
// категории ради категорий. Экспорт в чат (лист выбора формата и вся логика
// сборки MD/DOC) — общие в annotations.js, здесь только вызываем
// window.freudOpenExportSheet(id).
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

  function renderCard(a) {
    var html = '<div class="mynote-card">' +
      '<a class="mynote-page-link" href="' + SITE_BASE + esc(a.url) + '">' + esc(a.pageTitle) + "</a>";
    if (a.quote) {
      var cls = "user-mark user-mark-" + esc(a.color || "bruise") + (a.type === "note" ? " user-mark-note" : "");
      html += '<mark class="' + cls + '">' + esc(a.quote) + "</mark>";
    }
    if (a.comment) {
      html += '<p class="mynote-comment">' + esc(a.comment) + "</p>";
    }
    html += '<div class="mynote-actions"><span class="mynote-date">' + fmtDate(a.createdAt) + "</span>";
    if (a.quote) html += '<button class="btn" data-export-note="' + a.id + '">Отправить в чат</button>';
    html += '<button class="btn" data-remove="' + a.id + '">Удалить</button></div></div>';
    return html;
  }

  function render() {
    var all = (window.freudAnnotationsAll ? window.freudAnnotationsAll() : []).slice().sort(function (a, b) {
      return b.createdAt - a.createdAt;
    });
    document.getElementById("mynotesEmpty").hidden = all.length > 0;
    document.getElementById("mynotesList").innerHTML = all.map(renderCard).join("");

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

  render();
})();
