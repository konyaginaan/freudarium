// Адаптер Telegram Mini App. Вне Telegram window.Telegram недоступен —
// весь файл ничего не делает, сайт работает как обычная страница
// (тот же принцип, что в ~/projects/norevia/index.html).
(function () {
  "use strict";
  var tg = window.Telegram && window.Telegram.WebApp;
  if (!tg || !tg.initData) return; // не внутри Telegram

  document.documentElement.classList.add("in-telegram");

  try {
    tg.ready();
    tg.expand();
  } catch (e) {
    console.warn("WebApp init failed", e);
  }
  try {
    tg.disableVerticalSwipes && tg.disableVerticalSwipes();
  } catch (e) {}

  // ── переход по start_param (ссылка вида t.me/bot/app?startapp=n-<slug>) ──
  try {
    var startParam = tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (startParam && location.pathname === (window.__SITE_BASE__ || "") + "/") {
      var m = /^([a-z]+)-(.+)$/.exec(startParam);
      if (m) {
        var prefixMap = { n: "n", w: "w", f: "f", m: "m", t: "t" };
        var prefix = prefixMap[m[1]];
        if (prefix) location.replace((window.__SITE_BASE__ || "") + "/" + prefix + "/" + m[2] + "/");
      }
    }
  } catch (e) {}

  // ── «Открыть как сайт» / «Открыть в Telegram» ──
  document.querySelectorAll("[data-open-external]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      try { tg.openLink(location.href); } catch (e2) { window.open(location.href, "_blank"); }
    });
  });

  // ── скачивание внутри Telegram: обычные <a download> в вебвью ненадёжны
  // (и на blob:-ссылки вроде архива «с окружением» tg.downloadFile вообще
  // не годится — ему нужен настоящий https-адрес). Вместо скачивания в
  // файловую систему устройства файл присылается ботом в чат — надёжнее,
  // с уведомлением, и остаётся под рукой. См. ~/projects/freudarium-server. ──
  var SERVER_URL = "https://freudarium.norevia.workers.dev";

  window.freudSendToChat = function (source, name) {
    if (window.freudToast) window.freudToast("Отправляю в чат…", { duration: 4000 });
    var endpoint = SERVER_URL + "/send?name=" + encodeURIComponent(name || "");
    var opts = { method: "POST", headers: { "X-Tg-Init-Data": tg.initData } };
    if (typeof source === "string") {
      endpoint += "&url=" + encodeURIComponent(source);
    } else {
      opts.body = source; // Blob, собранный в браузере (архив «с окружением»)
    }
    fetch(endpoint, opts)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
        return r.json();
      })
      .then(function () {
        if (window.freudToast) window.freudToast("Файл отправлен в чат с ботом", { duration: 3200 });
      })
      .catch(function (err) {
        console.warn("send to chat failed", err);
        var msg = /chat not started/.test(String(err.message))
          ? "Сначала откройте чат с ботом и отправьте /start — потом попробуйте снова"
          : "Не получилось отправить — проверьте связь и попробуйте ещё раз";
        if (window.freudToast) window.freudToast(msg, { duration: 4500 });
      });
  };

  document.addEventListener(
    "click",
    function (e) {
      var a = e.target.closest("a[download]");
      if (!a || a.href.indexOf("blob:") === 0) return; // blob: обрабатывает app.js напрямую через freudSendToChat
      e.preventDefault();
      var name = a.getAttribute("download") || a.href.split("/").pop();
      window.freudSendToChat(a.href, name);
    },
    true
  );

  // ── кнопка «назад» Telegram (Bot API 6.1+): без неё системный жест
  // на Android закрывает мини-приложение целиком вместо возврата ──
  function backAvailable() {
    try { return !!(tg.BackButton && tg.isVersionAtLeast && tg.isVersionAtLeast("6.1")); }
    catch (e) { return false; }
  }
  if (backAvailable()) {
    var hasBack = !!document.querySelector(".back-link");
    if (hasBack) tg.BackButton.show(); else tg.BackButton.hide();
    tg.onEvent("backButtonClicked", function () {
      var sheet = document.getElementById("settingsSheet");
      if (sheet && !sheet.hidden) { sheet.hidden = true; return; }
      if (window.history.length > 1) window.history.back();
    });
  }

  // ── CloudStorage: дублирование настроек оформления между устройствами ──
  var SETTINGS_KEY = "freud:settings";
  if (tg.CloudStorage) {
    tg.CloudStorage.getItem(SETTINGS_KEY, function (err, value) {
      if (!err && value && window.freudApplyCloudSettings) window.freudApplyCloudSettings(value);
    });
    window.freudCloudSet = function (key, value) {
      try { tg.CloudStorage.setItem(key, value, function () {}); } catch (e) {}
    };
  }

  // ── добавить на домашний экран (Bot API 8.0+) ──
  window.freudAddToHomeScreen = function () {
    try {
      if (tg.addToHomeScreen) tg.addToHomeScreen();
    } catch (e) {}
  };
})();
