// Публичные комментарии читателей — видны всем на странице (в т.ч. вне
// Telegram). Писать может настоящий Telegram-пользователь — двумя
// способами: изнутри Mini App (initData, как у freudSendFeedback в
// tg.js) или с обычного сайта через Telegram Login Widget (кнопка «Войти
// через Telegram», добавлено 01.08.2026 по просьбе пользователя — чтобы
// комментировать можно было и не открывая мини-приложение). Плоский
// список с необязательной ссылкой «в ответ на», без вложенных веток —
// по решению пользователя 31.07.2026. Модерация постфактум: автору сайта
// (id — свой в обоих способах входа — совпадает с OWNER_CHAT_ID на
// сервере) сервер отдаёт isOwner — только тогда рисуем «удалить».
(function () {
  "use strict";
  var root = document.getElementById("commentsSection");
  if (!root) return;

  var SERVER_URL = "https://freudarium.norevia.workers.dev";
  var BOT_USERNAME = "freudarium_bot";
  var LOGIN_KEY = "freud:tglogin";

  var listEl = root.querySelector(".comments-list");
  var formEl = root.querySelector(".comments-form");
  var textEl = formEl.querySelector("textarea");
  var replyBanner = root.querySelector(".comments-reply-banner");
  var replyNameEl = replyBanner.querySelector(".comments-reply-name");
  var authEl = root.querySelector("#commentsAuth");
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
  function loginData() {
    try {
      var raw = localStorage.getItem(LOGIN_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }
  // Заголовки авторизации — Mini App в приоритете (если открыто внутри
  // Telegram, там всегда самая свежая подпись); вне Telegram — то, что
  // осталось в localStorage от Login Widget.
  function authHeaders() {
    var id = initData();
    if (id) return { "X-Tg-Init-Data": id };
    var login = loginData();
    if (login) return { "X-Tg-Login-Data": JSON.stringify(login) };
    return {};
  }
  function hasAuth() {
    return !!(initData() || loginData());
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

  // Внутри Mini App виджет не нужен — там уже есть подлинная identity.
  // Вне Telegram: если уже вошли (в localStorage что-то есть) — показать
  // «Вы вошли как…» и кнопку выхода; если нет — вставить сам виджет
  // (его официальный скрипт сам рисует кнопку «Log in with Telegram»
  // внутри тега, где его разместили).
  //
  // attemptsLeft — на случай, если сюда попали через диплинк-редирект из
  // уведомления (t.me/bot/app?startapp=r-<код> → tg.js резолвит код →
  // location.replace на эту же страницу, см. tg.js): initData Telegram,
  // похоже, не всегда успевает «приложиться» к странице мгновенно после
  // такого JS-редиректа (баг, найденный пользователем 01.08.2026 — виджет
  // входа показывался ей внутри самого Telegram). Если СРАЗУ ни initData,
  // ни сохранённого логина нет — даём Telegram до 4 секунд (изначально
  // было 1.5с — не хватило, см. тот же баг), прежде чем решить, что это
  // действительно не Telegram, и показать виджет.
  // Обычный случай (initData есть сразу или его точно нет) ничего не ждёт.
  function renderAuth(attemptsLeft) {
    if (!authEl) return;
    if (initData()) {
      authEl.hidden = true;
      return;
    }
    var login = loginData();
    if (!login && attemptsLeft === undefined) attemptsLeft = 20;
    if (!login && attemptsLeft > 0) {
      setTimeout(function () { renderAuth(attemptsLeft - 1); }, 200);
      return;
    }
    authEl.hidden = false;
    if (login) {
      authEl.innerHTML =
        "Вы вошли как <b>" + escHtml(login.username ? "@" + login.username : login.first_name || "читатель") + "</b> · " +
        '<button type="button" class="chip-muted-btn" id="commentsLogout">Выйти</button>';
      authEl.querySelector("#commentsLogout").addEventListener("click", function () {
        localStorage.removeItem(LOGIN_KEY);
        renderAuth();
        load();
      });
    } else {
      authEl.innerHTML = "";
      var s = document.createElement("script");
      s.async = true;
      s.src = "https://telegram.org/js/telegram-widget.js?22";
      s.setAttribute("data-telegram-login", BOT_USERNAME);
      s.setAttribute("data-size", "medium");
      s.setAttribute("data-radius", "10");
      s.setAttribute("data-onauth", "freudTelegramLoginAuth(user)");
      s.setAttribute("data-request-access", "write");
      authEl.appendChild(s);
    }
  }
  // Колбэк самого виджета (data-onauth) — вызывается Telegram напрямую,
  // поэтому глобальный, а не внутри замыкания.
  window.freudTelegramLoginAuth = function (user) {
    localStorage.setItem(LOGIN_KEY, JSON.stringify(user));
    renderAuth();
    load();
  };

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
    fetch(SERVER_URL + "/comments?page=" + encodeURIComponent(pageUrl), { headers: authHeaders() })
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
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
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
    if (!hasAuth()) {
      if (window.freudToast) window.freudToast("Войдите через Telegram, чтобы комментировать");
      return;
    }
    var text = textEl.value.trim();
    if (!text) return;
    var pageTitle = (document.querySelector(".note-title, .chapter-title") || {}).textContent || document.title;
    fetch(SERVER_URL + "/comments", {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
      body: JSON.stringify({ page: pageUrl, text: text, replyTo: replyTo, pageTitle: pageTitle }),
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

  renderAuth();
  load();
})();
