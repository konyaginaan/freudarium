// Публичные комментарии читателей — видны всем на странице (в т.ч. вне
// Telegram), писать может только настоящий Telegram-пользователь (та же
// initData-подпись, что у freudSendFeedback в tg.js). Плоский список с
// необязательной ссылкой «в ответ на», без вложенных веток — по решению
// пользователя 31.07.2026. Модерация постфактум: автору сайта (initData
// совпадает с OWNER_CHAT_ID на сервере) сервер отдаёт isOwner — только
// тогда рисуем кнопку «удалить» у чужих комментариев.
(function () {
  "use strict";
  var root = document.getElementById("commentsSection");
  if (!root) return;

  var SERVER_URL = "https://freudarium.norevia.workers.dev";
  var listEl = root.querySelector(".comments-list");
  var formEl = root.querySelector(".comments-form");
  var textEl = formEl.querySelector("textarea");
  var replyBanner = root.querySelector(".comments-reply-banner");
  var replyNameEl = replyBanner.querySelector(".comments-reply-name");
  var pageUrl = location.pathname;

  var comments = [];
  var isOwner = false;
  var replyTo = null;

  function tg() {
    return window.Telegram && window.Telegram.WebApp;
  }
  function initData() {
    var t = tg();
    return t && t.initData ? t.initData : null;
  }

  function escHtml(s) {
    var div = document.createElement("div");
    div.textContent = s || "";
    return div.innerHTML;
  }

  function fmtTime(ts) {
    try {
      return new Date(ts).toLocaleString("ru-RU", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  }

  function render() {
    if (!comments.length) {
      listEl.innerHTML = '<p class="comments-empty">Комментариев пока нет — оставьте первый комментарий.</p>';
      return;
    }
    var byId = {};
    comments.forEach(function (c) { byId[c.id] = c; });
    listEl.innerHTML = comments.map(function (c) {
      var replyHtml = "";
      if (c.replyTo && byId[c.replyTo]) {
        replyHtml = '<div class="comment-reply-to">в ответ ' + escHtml(byId[c.replyTo].authorName) + "</div>";
      }
      var delHtml = isOwner
        ? '<button class="comment-delete" data-id="' + c.id + '" aria-label="Удалить">✕</button>'
        : "";
      return (
        '<div class="comment">' +
        replyHtml +
        '<div class="comment-head"><span class="comment-author">' + escHtml(c.authorName) + "</span>" +
        '<span class="comment-time">' + fmtTime(c.ts) + "</span>" + delHtml + "</div>" +
        '<p class="comment-text">' + escHtml(c.text) + "</p>" +
        '<button type="button" class="comment-reply-btn" data-id="' + c.id + '" data-name="' + escHtml(c.authorName) + '">Ответить</button>' +
        "</div>"
      );
    }).join("");
  }

  function load() {
    var headers = {};
    var id = initData();
    if (id) headers["X-Tg-Init-Data"] = id;
    fetch(SERVER_URL + "/comments?page=" + encodeURIComponent(pageUrl), { headers: headers })
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then(function (data) {
        comments = data.comments || [];
        isOwner = !!data.isOwner;
        render();
      })
      .catch(function () {
        listEl.innerHTML = '<p class="comments-empty">Не получилось загрузить комментарии.</p>';
      });
  }

  function clearReply() {
    replyTo = null;
    replyBanner.hidden = true;
  }

  listEl.addEventListener("click", function (e) {
    var replyBtn = e.target.closest(".comment-reply-btn");
    var delBtn = e.target.closest(".comment-delete");
    if (replyBtn) {
      replyTo = replyBtn.getAttribute("data-id");
      replyNameEl.textContent = replyBtn.getAttribute("data-name");
      replyBanner.hidden = false;
      textEl.focus();
    } else if (delBtn) {
      if (!window.confirm("Удалить комментарий?")) return;
      fetch(SERVER_URL + "/comments/delete", {
        method: "POST",
        headers: { "X-Tg-Init-Data": initData(), "Content-Type": "application/json" },
        body: JSON.stringify({ page: pageUrl, id: delBtn.getAttribute("data-id") }),
      })
        .then(function (r) { return r.json(); })
        .then(load)
        .catch(function () {
          if (window.freudToast) window.freudToast("Не получилось удалить");
        });
    }
  });

  replyBanner.querySelector("[data-cancel-reply]").addEventListener("click", clearReply);

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!initData()) {
      if (window.freudToast) window.freudToast("Комментировать можно только внутри Telegram");
      return;
    }
    var text = textEl.value.trim();
    if (!text) return;
    fetch(SERVER_URL + "/comments", {
      method: "POST",
      headers: { "X-Tg-Init-Data": initData(), "Content-Type": "application/json" },
      body: JSON.stringify({ page: pageUrl, text: text, replyTo: replyTo }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
        return r.json();
      })
      .then(function () {
        textEl.value = "";
        clearReply();
        load();
      })
      .catch(function () {
        if (window.freudToast) window.freudToast("Не получилось отправить — проверьте связь и попробуйте ещё раз");
      });
  });

  load();
})();
