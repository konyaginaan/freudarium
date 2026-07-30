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

  // Личная заметка «просто текстом» — отдельным сообщением, не файлом
  // (см. /notes/, экспорт заметки).
  window.freudSendTextToChat = function (text) {
    if (window.freudToast) window.freudToast("Отправляю в чат…", { duration: 4000 });
    fetch(SERVER_URL + "/sendtext", {
      method: "POST",
      headers: { "X-Tg-Init-Data": tg.initData, "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
        return r.json();
      })
      .then(function () {
        if (window.freudToast) window.freudToast("Отправлено в чат с ботом", { duration: 3200 });
      })
      .catch(function (err) {
        console.warn("send text failed", err);
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
  // Раньше закрывалась по кнопке «назад» только settingsSheet, а видимость
  // самой кнопки считалась ОДИН раз при загрузке — только по наличию
  // .back-link на странице. На страницах без него (например, главная)
  // Telegram вообще не перехватывал аппаратную кнопку/жест «назад» на
  // Android — открытое меню, композер или панель выделения закрывали не
  // себя, а всё мини-приложение целиком. Теперь видимость и обработчик
  // следят за ЛЮБОЙ открытой шторкой/панелью, а не только за одной.
  function openOverlays() {
    return Array.prototype.slice.call(document.querySelectorAll(".sheet, .sel-toolbar"))
      .filter(function (el) { return !el.hidden; });
  }
  function updateBackButton() {
    if (!backAvailable()) return;
    var hasBack = !!document.querySelector(".back-link");
    if (hasBack || openOverlays().length) tg.BackButton.show(); else tg.BackButton.hide();
  }
  if (backAvailable()) {
    updateBackButton();
    document.querySelectorAll(".sheet, .sel-toolbar").forEach(function (el) {
      new MutationObserver(updateBackButton).observe(el, { attributes: true, attributeFilter: ["hidden"] });
    });
    tg.onEvent("backButtonClicked", function () {
      var open = openOverlays();
      if (open.length) { open[open.length - 1].hidden = true; return; }
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

  // ── CloudStorage: личные заметки (закладки/заметки/выделения) между
  // устройствами. Каждая запись — отдельный ключ (одно значение CloudStorage
  // не может быть длиннее 4096 символов, а весь список легко превысит это),
  // плюс один ключ-индекс со списком id (тоже под тем же лимитом — хватает
  // на несколько сотен записей, для личных пометок с запасом). ──
  var ANN_INDEX_KEY = "freud:ann:index";
  var ANN_PREFIX = "freud:ann:";
  if (tg.CloudStorage) {
    tg.CloudStorage.getItem(ANN_INDEX_KEY, function (err, indexJson) {
      if (err || !indexJson) return;
      var ids;
      try { ids = JSON.parse(indexJson); } catch (e) { return; }
      if (!ids || !ids.length) return;
      tg.CloudStorage.getItems(ids.map(function (id) { return ANN_PREFIX + id; }), function (err2, values) {
        if (err2 || !values) return;
        var cloudItems = [];
        Object.keys(values).forEach(function (k) {
          if (!values[k]) return;
          try { cloudItems.push(JSON.parse(values[k])); } catch (e) {}
        });
        if (!cloudItems.length) return;
        var local = window.freudAnnotationsAll ? window.freudAnnotationsAll() : [];
        var byId = {};
        local.concat(cloudItems).forEach(function (a) { byId[a.id] = a; });
        var merged = Object.keys(byId).map(function (id) { return byId[id]; });
        if (window.freudAnnotationsSaveAll) window.freudAnnotationsSaveAll(merged);
        if (window.freudAnnotationsRefresh) window.freudAnnotationsRefresh();
      });
    });

    // Пишем только то, чего в облаке ещё не было — не гоняем на каждое
    // изменение весь список, а держим, что уже отправлено, в этой сессии.
    var syncedIds = {};
    window.freudCloudSyncAnnotations = function (list) {
      var ids = list.map(function (a) { return a.id; });
      var toWrite = list.filter(function (a) { return !syncedIds[a.id]; });
      toWrite.forEach(function (a) {
        try {
          tg.CloudStorage.setItem(ANN_PREFIX + a.id, JSON.stringify(a).slice(0, 4090), function () {});
          syncedIds[a.id] = true;
        } catch (e) {}
      });
      // то, что удалили локально, но ещё числится в индексе — убрать и из облака
      Object.keys(syncedIds).forEach(function (id) {
        if (ids.indexOf(id) === -1) {
          try { tg.CloudStorage.removeItem(ANN_PREFIX + id, function () {}); } catch (e) {}
          delete syncedIds[id];
        }
      });
      try { tg.CloudStorage.setItem(ANN_INDEX_KEY, JSON.stringify(ids).slice(0, 4090), function () {}); } catch (e) {}
    };
  }

  // ── добавить на домашний экран (Bot API 8.0+) ──
  // Раньше решали по isVersionAtLeast('8.0') + наличию метода — это только
  // «в принципе умеет», а не «что сейчас произойдёт». Реальный статус даёт
  // checkHomeScreenStatus: 'unsupported' (в этой версии/на этом устройстве
  // нет вовсе), 'unknown' (можно предложить), 'added' (уже добавлено —
  // именно поэтому нажатие «ничего не делало»: addToHomeScreen тогда просто
  // no-op по документации Telegram), 'missed' (пользователь раньше отказался).
  var homeScreenMethodExists = false;
  try { homeScreenMethodExists = tg.isVersionAtLeast && tg.isVersionAtLeast("8.0") && !!tg.checkHomeScreenStatus; }
  catch (e) {}
  window.freudHomeScreenSupported = homeScreenMethodExists;

  window.freudAddToHomeScreen = function () {
    if (!homeScreenMethodExists) {
      if (window.freudToast) {
        window.freudToast(
          "Эта версия Telegram не поддерживает добавление напрямую — откройте меню ⋮ в шапке мини-приложения (не нашего сайта, а самого Telegram) и поищите там «Добавить на главный экран».",
          { duration: 6000 }
        );
      }
      return;
    }
    tg.checkHomeScreenStatus(function (status) {
      console.log("checkHomeScreenStatus", status);
      if (status === "added") {
        if (window.freudToast) window.freudToast("Уже добавлено на этом устройстве — ищите иконку на главном экране", { duration: 4000 });
        return;
      }
      if (status === "unsupported") {
        if (window.freudToast) {
          window.freudToast("Устройство не поддерживает это — попробуйте через меню ⋮ в шапке Telegram", { duration: 4500 });
        }
        return;
      }
      try {
        tg.addToHomeScreen();
      } catch (err) {
        console.warn("addToHomeScreen failed", err);
        if (window.freudToast) window.freudToast("Не получилось — попробуйте через меню ⋮ в шапке Telegram", { duration: 4500 });
      }
    });
  };
  if (tg.onEvent) {
    tg.onEvent("homeScreenAdded", function () {
      if (window.freudToast) window.freudToast("Готово — иконка добавлена на главный экран", { duration: 3000 });
    });
    tg.onEvent("homeScreenFailed", function () {
      if (window.freudToast) window.freudToast("Не получилось добавить иконку", { duration: 3500 });
    });
  }
})();
