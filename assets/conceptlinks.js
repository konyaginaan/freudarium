// Автоссылки понятий в тексте заметок на карты областей (фидбек
// пользователя 31.07.2026: «встречается невроз — можно сделать кликабельным
// на карту области „невроз“»). window.__HUB_KEYWORDS__ — сгенерированный
// build.py словарь {"невроз навязчивости": "/freudarium/m/...", ...} из
// собственных тегов хабов (assets/hub-keywords.js, грузится раньше этого
// файла). Только первое вхождение каждого понятия на странице — иначе
// прозу запестрит повторами одной и той же ссылки.
//
// \b не работает с кириллицей (JS считает границей слова только ASCII
// \w) — тот же класс ловушки, что уже был у wordAtPoint в annotations.js.
// Используем юникод-осведомлённые лукбихайнд/лукахед по \p{L}\p{N}.
(function () {
  "use strict";
  var keywords = window.__HUB_KEYWORDS__;
  if (!keywords) return;

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // window.freudRunConceptLinks — тело карты области подгружается позже,
  // скриптом (платный контент, см. assets/hub-gate.js), и на момент
  // разбора этого файла его ещё нет в DOM; после вставки нужно прогнать
  // автоссылки заново на уже вставленный контейнер.
  function run(container) {
    if (!container) return;
    Object.keys(keywords).forEach(function (phrase) {
      var url = keywords[phrase];
      // Уже есть ссылка на эту же карту на странице (например, в «Дальше
      // по мысли» или в самом «Источнике») — не дублируем ещё одной в прозе.
      if (
        container.querySelector('a[href="' + url + '"]') ||
        document.querySelector('.note-source a[href="' + url + '"]')
      ) {
        return;
      }

      var re = new RegExp("(?<![\\p{L}\\p{N}])(" + escapeRe(phrase) + ")(?![\\p{L}\\p{N}])", "iu");
      var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
      var node;
      while ((node = walker.nextNode())) {
        if (node.parentNode.closest("a")) continue;
        var m = re.exec(node.nodeValue);
        if (!m) continue;
        var range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        var a = document.createElement("a");
        a.href = url;
        a.className = "concept-link";
        try {
          range.surroundContents(a);
        } catch (e) {
          break;
        }
        break; // только первое вхождение этого понятия на странице
      }
    });
  }

  window.freudRunConceptLinks = run;
  run(document.querySelector(".note-body, .fulltext-body"));
})();
