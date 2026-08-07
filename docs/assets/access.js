// Доступ к платной части сайта (карты областей, личные инструменты —
// закладки/заметки/экспорт в чат/скачивание) + шторка «Купить». Покупка —
// вручную: реквизиты и одобрение идут через чат с ботом (см.
// ~/projects/freudarium-server), сама эта шторка только отправляет заявку
// на старт покупки (POST /purchase/start) при отмеченном согласии на
// обработку персональных данных.
(function () {
  "use strict";
  var SERVER_URL = "https://freudarium.norevia.workers.dev";
  var CACHE_KEY = "freud:access-cache";
  var LOGIN_KEY = "freud:tglogin";

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
  // Тот же паттерн, что в assets/comments.js: Mini App в приоритете, вне
  // Telegram — то, что осталось от Login Widget.
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

  window.freudEntitled = false; // по умолчанию, пока не пришёл ответ сервера/кэша

  // Кэш на сессию вкладки — не дёргать /access заново на каждой странице
  // при обычной навигации по сайту.
  try {
    if (sessionStorage.getItem(CACHE_KEY) === "1") window.freudEntitled = true;
  } catch (e) {}

  var readyListeners = [];
  window.freudOnAccessReady = function (fn) {
    if (window.freudAccessResolved) fn(window.freudEntitled);
    else readyListeners.push(fn);
  };

  function resolveAccess(entitled) {
    window.freudEntitled = entitled;
    window.freudAccessResolved = true;
    try {
      sessionStorage.setItem(CACHE_KEY, entitled ? "1" : "0");
    } catch (e) {}
    readyListeners.forEach(function (fn) { fn(entitled); });
    readyListeners = [];
    document.dispatchEvent(new CustomEvent("freud:access", { detail: { entitled: entitled } }));
  }

  if (!hasAuth()) {
    // Нет подписи — нечем подтвердить личность на сервере, доступа нет.
    resolveAccess(false);
  } else {
    fetch(SERVER_URL + "/access", { headers: authHeaders() })
      .then(function (r) { return r.ok ? r.json() : { entitled: false }; })
      .then(function (d) { resolveAccess(!!d.entitled); })
      // Сеть подвела — не понижаем уже известный статус из кэша, просто
      // подтверждаем то, что было (кэш или false по умолчанию).
      .catch(function () { resolveAccess(window.freudEntitled); });
  }

  // ── шторка «Купить» ──
  var sheet = document.getElementById("purchaseSheet");
  var bodyEl = document.getElementById("purchaseSheetBody");
  var outsideHint = document.getElementById("purchaseOutsideTelegramHint");
  var consentCb = document.getElementById("purchaseConsent");
  var submitBtn = document.getElementById("purchaseSubmitBtn");

  // Покупка возможна только внутри Telegram — бот присылает реквизиты и
  // принимает квитанцию в чате, вне Telegram такого чата нет.
  window.freudOpenBuySheet = function () {
    if (!sheet) return;
    var inTelegram = !!initData();
    if (bodyEl) bodyEl.hidden = !inTelegram;
    if (outsideHint) outsideHint.hidden = inTelegram;
    sheet.hidden = false;
  };

  if (sheet) {
    sheet.addEventListener("click", function (e) {
      if (e.target === sheet || e.target.closest("[data-close-sheet]")) sheet.hidden = true;
    });
  }

  // Делегирование на document — «Купить» может появиться где угодно (карта
  // области, позже — кнопки скачивания/закладок/заметок из соседних
  // файлов), не нужно отдельно подписываться в каждом из них.
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-buy-open]")) window.freudOpenBuySheet();
  });

  // Скачивание — тоже платный инструмент (чтение самого текста остаётся
  // бесплатным, см. render_hub/render_note; продаётся именно удобство:
  // закладки, заметки, экспорт, скачивание). Большинство кнопок «Скачать»
  // идут через шторку (см. gate в app.js), но ссылка на zip работы —
  // обычная <a download> (templates/downloads_widget_work в build.py) —
  // перехватываем её здесь же, в capture-фазе, ДО обработчика tg.js
  // (иначе тот уже начал бы отправку в чат до проверки доступа).
  document.addEventListener(
    "click",
    function (e) {
      var a = e.target.closest("a[download]");
      if (!a || window.freudEntitled) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (window.freudOpenBuySheet) window.freudOpenBuySheet();
    },
    true
  );

  if (consentCb && submitBtn) {
    consentCb.addEventListener("change", function () {
      submitBtn.disabled = !consentCb.checked;
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", function () {
      if (!consentCb || !consentCb.checked) return;
      submitBtn.disabled = true;
      fetch(SERVER_URL + "/purchase/start", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
        body: JSON.stringify({ consent: true }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || String(r.status)); });
          return r.json();
        })
        .then(function () {
          sheet.hidden = true;
          consentCb.checked = false;
          submitBtn.disabled = true;
          if (window.freudToast) {
            window.freudToast("Реквизиты отправлены в чат с ботом — откройте его и пришлите квитанцию", { duration: 6000 });
          }
        })
        .catch(function (err) {
          console.warn("purchase start failed", err);
          submitBtn.disabled = false;
          if (window.freudToast) window.freudToast("Не получилось отправить — проверьте связь и попробуйте ещё раз", { duration: 4500 });
        });
    });
  }
})();
