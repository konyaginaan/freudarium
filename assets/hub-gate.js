// Гейт карты области — платный контент (см. templates/pages.py:render_hub,
// worker.js: /hub-content). На обычной заметке/полном тексте #hubPaywall
// нет вовсе — файл сразу выходит, ничего не делая.
(function () {
  "use strict";
  var paywall = document.getElementById("hubPaywall");
  if (!paywall) return;

  var SERVER_URL = "https://freudarium.norevia.workers.dev";
  var slug = paywall.getAttribute("data-hub-slug");
  var bodyEl = document.getElementById("hubBody");
  var downloadBtn = document.querySelector("[data-hub-download]");

  function tg() {
    return window.Telegram && window.Telegram.WebApp;
  }
  function initData() {
    var t = tg();
    return t && t.initData ? t.initData : null;
  }
  function loginData() {
    try {
      var raw = localStorage.getItem("freud:tglogin");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }
  // Тот же паттерн авторизации, что в assets/access.js/comments.js.
  function authHeaders() {
    var id = initData();
    if (id) return { "X-Tg-Init-Data": id };
    var login = loginData();
    if (login) return { "X-Tg-Login-Data": JSON.stringify(login) };
    return {};
  }

  function loadHubBody() {
    fetch(SERVER_URL + "/hub-content?slug=" + encodeURIComponent(slug) + "&kind=html", { headers: authHeaders() })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
        return r.json();
      })
      .then(function (d) {
        bodyEl.innerHTML = d.value;
        bodyEl.hidden = false;
        paywall.hidden = true;
        // Тело вставлено уже после разбора conceptlinks.js/app.js — без
        // повторного запуска автоссылки понятий и лайтбокс SVG-схем на
        // свежевставленном контенте просто не появятся.
        if (window.freudRunConceptLinks) window.freudRunConceptLinks(bodyEl);
        if (window.freudBindSvgLightbox) window.freudBindSvgLightbox();
      })
      .catch(function (err) {
        console.warn("hub content load failed", err);
        if (window.freudToast) window.freudToast("Не получилось загрузить карту — проверьте связь и обновите страницу", { duration: 4500 });
      });
  }

  if (window.freudOnAccessReady) {
    window.freudOnAccessReady(function (entitled) {
      if (entitled) loadHubBody();
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () {
      if (!window.freudEntitled) {
        if (window.freudOpenBuySheet) window.freudOpenBuySheet();
        return;
      }
      if (window.freudToast) window.freudToast("Готовлю файл…", { duration: 4000 });
      fetch(SERVER_URL + "/hub-content?slug=" + encodeURIComponent(slug) + "&kind=md", { headers: authHeaders() })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
          return r.json();
        })
        .then(function (d) {
          var name = slug + ".md";
          var blob = new Blob([d.value], { type: "text/markdown" });
          if (window.freudSendToChat) {
            window.freudSendToChat(blob, name);
          } else {
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = name;
            document.body.appendChild(a);
            a.click();
            a.remove();
            if (window.freudToast) window.freudToast("Скачано", { duration: 3200 });
          }
        })
        .catch(function (err) {
          console.warn("hub download failed", err);
          if (window.freudToast) window.freudToast("Не получилось скачать — проверьте связь и попробуйте ещё раз", { duration: 4500 });
        });
    });
  }
})();
