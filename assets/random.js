// Страница /n/random/ — статических случайных URL не бывает, поэтому
// список всех адресов заметок лежит в random-urls.json и выбор идёт в браузере.
(function () {
  var base = window.__SITE_BASE__ || "";
  fetch(base + "/assets/random-urls.json")
    .then(function (r) { return r.json(); })
    .then(function (urls) {
      if (!urls.length) return;
      var url = urls[Math.floor(Math.random() * urls.length)];
      location.replace(url);
    })
    .catch(function () {});
})();
