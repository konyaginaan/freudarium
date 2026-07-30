// Общая логика сайта: настройки оформления, кнопка «назад» (в т.ч.
// плавающая), шторка настроек, скачивание заметки с окружением.
(function () {
  "use strict";
  var SITE_BASE = window.__SITE_BASE__ || "";
  var root = document.documentElement;

  // ── настройки оформления (localStorage; внутри Telegram дублируются в
  // CloudStorage — см. tg.js) ──
  var DEFAULTS = { theme: "system", fontsize: "m", width: "normal" };
  var KEY = "freud:settings";

  function loadSettings() {
    try {
      return Object.assign({}, DEFAULTS, JSON.parse(localStorage.getItem(KEY) || "{}"));
    } catch (e) {
      return Object.assign({}, DEFAULTS);
    }
  }

  function applySettings(s) {
    if (s.theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", s.theme);
    root.setAttribute("data-fontsize", s.fontsize);
    root.setAttribute("data-width", s.width);
    document.querySelectorAll(".seg").forEach(function (seg) {
      var key = seg.getAttribute("data-setting");
      seg.querySelectorAll("button").forEach(function (b) {
        b.classList.toggle("active", b.getAttribute("data-value") === s[key]);
      });
    });
  }

  function saveSettings(s) {
    localStorage.setItem(KEY, JSON.stringify(s));
    if (window.freudCloudSet) window.freudCloudSet(KEY, JSON.stringify(s));
  }

  var settings = loadSettings();
  applySettings(settings);

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".seg button");
    if (!btn) return;
    var seg = btn.closest(".seg");
    var key = seg.getAttribute("data-setting");
    settings[key] = btn.getAttribute("data-value");
    applySettings(settings);
    saveSettings(settings);
  });

  // Восстановление настроек из CloudStorage (Telegram), если они там новее
  // локальных — вызывается из tg.js после успешного чтения.
  window.freudApplyCloudSettings = function (json) {
    try {
      var s = Object.assign({}, DEFAULTS, JSON.parse(json));
      settings = s;
      applySettings(s);
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch (e) {}
  };

  // ── шторки: меню разделов и оформление (открывается из меню) ──
  var menuSheet = document.getElementById("menuSheet");
  var settingsSheet = document.getElementById("settingsSheet");
  document.getElementById("menuBtn").addEventListener("click", function () {
    menuSheet.hidden = false;
  });
  document.getElementById("openSettingsBtn").addEventListener("click", function () {
    menuSheet.hidden = true;
    settingsSheet.hidden = false;
  });
  [menuSheet, settingsSheet].forEach(function (sh) {
    sh.addEventListener("click", function (e) {
      if (e.target === sh || e.target.closest("[data-close-sheet]")) sh.hidden = true;
    });
  });

  // ── поиск ──
  document.getElementById("searchBtn").addEventListener("click", function () {
    window.location.href = SITE_BASE + "/search/";
  });

  // ── приветственный дисклеймер на главной: закрывается один раз навсегда ──
  var ONBOARD_KEY = "freud:onboard-dismissed";
  var onboard = document.getElementById("onboardCard");
  if (onboard) {
    if (localStorage.getItem(ONBOARD_KEY)) {
      onboard.remove();
    } else {
      document.getElementById("onboardClose").addEventListener("click", function () {
        localStorage.setItem(ONBOARD_KEY, "1");
        onboard.remove();
      });
    }
  }

  // ── кнопка «назад»: история браузера, а не жёсткая ссылка на «выше»,
  // если есть куда возвращаться внутри сайта ──
  function goBack(e) {
    if (window.history.length > 1 && document.referrer.indexOf(location.origin) === 0) {
      e.preventDefault();
      window.history.back();
    }
    // иначе — обычный переход по href элемента (контекстный «выше»)
  }
  document.querySelectorAll("[data-back]").forEach(function (el) {
    el.addEventListener("click", goBack);
  });

  // Плавающая кнопка — постоянный дубль ссылки «Назад» у большого пальца на
  // мобильных/планшетных экранах (на широких — есть мышь, хватает и шапки).
  // Раньше появлялась только после скролла вниз и снова пряталась при
  // скролле вверх — приходилось гоняться за ней; теперь она просто всегда
  // на месте, пока есть куда возвращаться, а не мигает от scrollY.
  var fab = document.getElementById("fabBack");
  var backHref = document.querySelector(".back-link");
  if (backHref) {
    fab.addEventListener("click", goBack);
    function updateFab() {
      fab.hidden = window.innerWidth >= 900;
    }
    updateFab();
    window.addEventListener("resize", updateFab);
  }

  // ── «Скачать с окружением»: сама заметка + все её связи (links_out +
  // backlinks), собранные в zip прямо в браузере из уже опубликованных
  // /dl/*/*.md — без бэкенда. Простой ZIP (STORE, без сжатия) с CRC32. ──
  function crc32(bytes) {
    var c, table = crc32.table;
    if (!table) {
      table = crc32.table = [];
      for (var n = 0; n < 256; n++) {
        c = n;
        for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        table[n] = c >>> 0;
      }
    }
    var crc = 0 ^ -1;
    for (var i = 0; i < bytes.length; i++) crc = (crc >>> 8) ^ table[(crc ^ bytes[i]) & 0xff];
    return (crc ^ -1) >>> 0;
  }

  function u16(n) { return [n & 0xff, (n >> 8) & 0xff]; }
  function u32(n) { return [n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >> 24) & 0xff]; }

  function buildZip(files) {
    // files: [{name, bytes: Uint8Array}]
    var localParts = [], centralParts = [], offset = 0;
    var now = new Date();
    var dosTime = ((now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1)) & 0xffff;
    var dosDate = (((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()) & 0xffff;

    files.forEach(function (f) {
      var nameBytes = new TextEncoder().encode(f.name);
      var crc = crc32(f.bytes);
      var header = new Uint8Array([
        0x50, 0x4b, 0x03, 0x04, 20, 0, 0, 0, 0, 0,
        ...u16(dosTime), ...u16(dosDate),
        ...u32(crc), ...u32(f.bytes.length), ...u32(f.bytes.length),
        ...u16(nameBytes.length), 0, 0,
      ]);
      var local = new Uint8Array(header.length + nameBytes.length + f.bytes.length);
      local.set(header, 0);
      local.set(nameBytes, header.length);
      local.set(f.bytes, header.length + nameBytes.length);
      localParts.push(local);

      var central = new Uint8Array([
        0x50, 0x4b, 0x01, 0x02, 20, 0, 20, 0, 0, 0, 0, 0,
        ...u16(dosTime), ...u16(dosDate),
        ...u32(crc), ...u32(f.bytes.length), ...u32(f.bytes.length),
        ...u16(nameBytes.length), 0, 0, 0, 0, 0, 0, ...u32(0),
        ...u32(offset),
      ]);
      var centralEntry = new Uint8Array(central.length + nameBytes.length);
      centralEntry.set(central, 0);
      centralEntry.set(nameBytes, central.length);
      centralParts.push(centralEntry);

      offset += local.length;
    });

    var centralSize = centralParts.reduce(function (a, p) { return a + p.length; }, 0);
    var end = new Uint8Array([
      0x50, 0x4b, 0x05, 0x06, 0, 0, 0, 0,
      ...u16(files.length), ...u16(files.length),
      ...u32(centralSize), ...u32(offset), 0, 0,
    ]);

    return new Blob([].concat(localParts, centralParts, [end]));
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-download-env]");
    if (!btn) return;
    e.preventDefault();
    btn.disabled = true;
    var origText = btn.textContent;
    btn.textContent = "Собираю…";
    var noteId = btn.getAttribute("data-download-env");
    fetch(SITE_BASE + "/assets/related/" + encodeURIComponent(noteId) + ".json")
      .then(function (r) { return r.json(); })
      .then(function (rel) {
        var urls = rel.files; // [{name, url}]
        return Promise.all(
          urls.map(function (f) {
            return fetch(f.url).then(function (r) { return r.arrayBuffer(); }).then(function (buf) {
              return { name: f.name, bytes: new Uint8Array(buf) };
            });
          })
        );
      })
      .then(function (files) {
        var blob = buildZip(files);
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = noteId.slice(0, 60) + " (окружение).zip";
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch(function (err) {
        console.warn("Не удалось собрать архив", err);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = origText;
      });
  });
})();
