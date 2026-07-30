// Общая логика сайта: настройки оформления, кнопка «назад» (в т.ч.
// плавающая), шторка настроек, скачивание заметки с окружением.
(function () {
  "use strict";
  var SITE_BASE = window.__SITE_BASE__ || "";
  var root = document.documentElement;

  // ── всплывающее уведомление снизу (используется и здесь, и в tg.js) ──
  var toastEl = document.getElementById("toast");
  var toastTimer = null;
  window.freudToast = function (text, opts) {
    opts = opts || {};
    clearTimeout(toastTimer);
    toastEl.textContent = text;
    toastEl.classList.add("show");
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
    }, opts.duration || 2600);
  };

  // ── настройки оформления (localStorage; внутри Telegram дублируются в
  // CloudStorage — см. tg.js) ──
  // "system" — не отдельная кнопка (раньше дублировала «Светлую», когда
  // ОС светлая — путала), а неявное состояние: пока нет явного выбора,
  // data-theme не ставится вовсе, и решает чистый CSS prefers-color-scheme.
  var DEFAULTS = { theme: "system", fontsize: "m" };
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

  // ── «Добавить на экран „Домой“» ──
  // Внутри Telegram — нативный Bot API addToHomeScreen (см. tg.js). Вне
  // Telegram: в Chrome/Android есть системное событие beforeinstallprompt,
  // на которое можно ответить программным приглашением; в Safari/iOS такого
  // API нет вовсе — там только подсказка «Поделиться → На экран «Домой»».
  var addBtn = document.getElementById("addToHomeBtn");
  var addHint = document.getElementById("addToHomeHint");
  var deferredInstallPrompt = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredInstallPrompt = e;
    addBtn.hidden = false;
  });
  var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  var isStandalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  if (window.freudHomeScreenSupported) {
    addBtn.hidden = false; // внутри Telegram и API точно есть — кнопка сработает
  } else if (window.freudAddToHomeScreen) {
    // Внутри Telegram, но этот клиент не умеет addToHomeScreen — кнопку не
    // показываем (она бы молча ничего не делала), сразу даём рабочий путь.
    addHint.hidden = false;
    addHint.textContent = "Откройте меню ⋮ в шапке Telegram (не сайта) — там есть «Добавить на главный экран».";
  } else if (isIOS && !isStandalone) {
    addHint.hidden = false;
    addHint.textContent = "На iPhone/iPad: откройте меню «Поделиться» внизу экрана и выберите «На экран «Домой»».";
  }
  addBtn.addEventListener("click", function () {
    if (window.freudAddToHomeScreen) {
      window.freudAddToHomeScreen();
      return;
    }
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      deferredInstallPrompt.userChoice.finally(function () {
        deferredInstallPrompt = null;
        addBtn.hidden = true;
      });
    }
  });

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
  var downloadSheet = document.getElementById("downloadSheet");
  [menuSheet, settingsSheet, downloadSheet].forEach(function (sh) {
    if (!sh) return;
    sh.addEventListener("click", function (e) {
      if (e.target === sh || e.target.closest("[data-close-sheet]")) sh.hidden = true;
    });
  });

  // ── поиск ──
  document.getElementById("searchBtn").addEventListener("click", function () {
    window.location.href = SITE_BASE + "/search/";
  });

  // ── «Продолжить чтение» на главной ──
  // Запоминаем последнюю открытую заметку/полный текст (не главную и не
  // страницы-указатели — там нечего продолжать) — используется на главной,
  // чтобы для вернувшегося читателя первой кнопкой была не «Случайная
  // заметка», а «Продолжить: …». Чтобы это не превращалось в нагромождение
  // кнопок, «Случайная заметка» в этом случае не исчезает, а сжимается до
  // маленькой ссылки под основной парой кнопок (см. .see-all в CSS — тот же
  // приём, что у «Все теги →»).
  var LAST_READ_KEY = "freud:last-read";
  var contentBody = document.querySelector(".note-body, .fulltext-body");
  var noteTitleEl = document.querySelector(".note-title");
  if (contentBody && noteTitleEl) {
    try {
      localStorage.setItem(LAST_READ_KEY, JSON.stringify({ url: location.pathname, title: noteTitleEl.textContent }));
    } catch (e) {}
  }
  var heroPrimaryBtn = document.getElementById("heroPrimaryBtn");
  var heroRandomLink = document.getElementById("heroRandomLink");
  if (heroPrimaryBtn) {
    try {
      var lastRead = JSON.parse(localStorage.getItem(LAST_READ_KEY) || "null");
      // location.pathname уже содержит SITE_BASE (это реальный путь браузера) —
      // подставлять его вторично не нужно, иначе получится двойной префикс.
      if (lastRead && lastRead.url && lastRead.title) {
        heroPrimaryBtn.href = lastRead.url;
        heroPrimaryBtn.textContent = "Продолжить: «" + lastRead.title + "»";
        if (heroRandomLink) heroRandomLink.hidden = false;
      }
    } catch (e) {}
  }

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

  // ── скачивание заметки: единая кнопка «Скачать» → поп-ап с форматом ──
  // Раньше «Скачать .md» была обычной <a href download> ссылкой — на части
  // мобильных браузеров (типично для iOS Safari) атрибут download на неё не
  // распространяется, и вместо скачивания открывается сырой файл текстом,
  // без шапки сайта и без кнопки «назад» — тупик. Теперь везде одинаково:
  // содержимое получаем через fetch, собираем Blob и либо отправляем в чат
  // (Telegram), либо скачиваем программно через ссылку на blob: — это не
  // подвержено той же особенности браузеров, что и прямой download-атрибут
  // на обычный URL.
  function downloadOrSend(blob, name, hint) {
    if (window.freudSendToChat) {
      window.freudSendToChat(blob, name);
      // freudSendToChat уже показывает свой тост об успехе/ошибке; отдельно
      // добавляем короткую подсказку, как пользоваться файлом, чуть позже.
      if (hint) setTimeout(function () { window.freudToast(hint, { duration: 5000 }); }, 3600);
      return;
    }
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (window.freudToast) window.freudToast(hint || "Скачано", { duration: 4000 });
  }

  function buildDocHtml(title, bodyText) {
    var esc = function (s) {
      var d = document.createElement("div");
      d.textContent = s;
      return d.innerHTML;
    };
    return (
      "<html><head><meta charset='utf-8'></head><body>" +
      "<h2>" + esc(title) + "</h2>" +
      "<pre style='white-space:pre-wrap;font-family:inherit'>" + esc(bodyText) + "</pre>" +
      "</body></html>"
    );
  }

  var pendingDownload = null; // { mdUrl, noteId, title }
  document.addEventListener("click", function (e) {
    var openBtn = e.target.closest("[data-open-download]");
    if (openBtn) {
      pendingDownload = {
        mdUrl: openBtn.getAttribute("data-dl-md-url"),
        noteId: openBtn.getAttribute("data-dl-note-id"),
        title: openBtn.getAttribute("data-dl-title"),
      };
      if (downloadSheet) {
        downloadSheet.querySelector('[data-dl-format="text"]').hidden = !window.freudSendTextToChat;
        downloadSheet.hidden = false;
      }
      return;
    }
    var fmtBtn = e.target.closest("[data-dl-format]");
    if (!fmtBtn || !pendingDownload) return;
    var format = fmtBtn.getAttribute("data-dl-format");
    var fileBase = pendingDownload.title.slice(0, 60);
    downloadSheet.hidden = true;

    if (format === "env") {
      if (window.freudToast) window.freudToast("Собираю архив…", { duration: 4000 });
      fetch(SITE_BASE + "/assets/related/" + encodeURIComponent(pendingDownload.noteId) + ".json")
        .then(function (r) { return r.json(); })
        .then(function (rel) {
          return Promise.all(
            rel.files.map(function (f) {
              return fetch(f.url).then(function (r) { return r.arrayBuffer(); }).then(function (buf) {
                return { name: f.name, bytes: new Uint8Array(buf) };
              });
            })
          );
        })
        .then(function (files) {
          downloadOrSend(buildZip(files), fileBase + " (окружение).zip",
            "Распакуйте архив в папку с вашим хранилищем Obsidian — ссылки между заметками останутся рабочими.");
        })
        .catch(function (err) { console.warn("Не удалось собрать архив", err); });
      return;
    }

    fetch(pendingDownload.mdUrl)
      .then(function (r) { return r.text(); })
      .then(function (mdText) {
        if (format === "md") {
          downloadOrSend(new Blob([mdText], { type: "text/markdown" }), fileBase + ".md",
            "Откройте файл в Obsidian (или перетащите в окно приложения) — оформление и ссылки сохранены.");
        } else if (format === "doc") {
          downloadOrSend(new Blob([buildDocHtml(pendingDownload.title, mdText)], { type: "application/msword" }), fileBase + ".doc",
            "Откройте файл в Word или любом текстовом редакторе.");
        } else if (format === "text" && window.freudSendTextToChat) {
          window.freudSendTextToChat(mdText);
          setTimeout(function () {
            if (window.freudToast) window.freudToast("Сообщение с текстом заметки придёт следующим в чате с ботом.", { duration: 5000 });
          }, 3600);
        }
      })
      .catch(function (err) { console.warn("Не удалось скачать заметку", err); });
  });
})();
