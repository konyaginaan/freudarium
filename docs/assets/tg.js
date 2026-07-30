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

  // ── скачивание внутри Telegram: обычные <a download> часто не срабатывают
  // в вебвью — используем tg.downloadFile (Bot API 8.0+), иначе открываем
  // во внешнем браузере ──
  function canDownloadFile() {
    try { return tg.isVersionAtLeast && tg.isVersionAtLeast("8.0") && !!tg.downloadFile; }
    catch (e) { return false; }
  }
  document.addEventListener(
    "click",
    function (e) {
      var a = e.target.closest("a[download]");
      if (!a) return;
      e.preventDefault();
      var url = a.href;
      var name = a.getAttribute("download") || url.split("/").pop();
      if (canDownloadFile()) {
        try {
          tg.downloadFile({ url: url, file_name: name });
          return;
        } catch (err) {
          console.warn("downloadFile failed, fallback to openLink", err);
        }
      }
      try { tg.openLink(url); } catch (e2) { window.open(url, "_blank"); }
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
