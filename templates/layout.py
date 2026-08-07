"""Общая HTML-обёртка страницы: <head>, шапка с липкой полосой «Назад»,
меню разделов, шторка оформления, плавающая кнопка «назад», подключение
assets. Также вешает pagefind-атрибуты (data-pagefind-*) для этапа поиска.

site_base — корень сайта (например "" локально или "/freud" на Pages без
домена); assets — всегда site_base + "/assets"."""
import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

# Видимый штамп сборки (низ меню «Разделы») — чтобы с телефона можно было
# сразу сказать, какая версия сайта реально открыта: вебвью Telegram кэширует
# страницы упорнее обычного браузера, и «правки не доходят» иначе не отличить
# от «правки сломаны».
_BUILD_STAMP = datetime.now().strftime("%d.%m %H:%M")

# Кэш-бастер: короткий хэш содержимого файла в query-параметре (?v=…).
# Без него GitHub Pages/браузер/вебвью Telegram спокойно держат старые копии
# style.css и скриптов ещё долго после деплоя — правки «не доходят» до
# пользователя, хотя на сервере уже лежат новые файлы. Хэш меняется только
# когда меняется сам файл, так что кэш сбрасывается ровно тогда, когда нужно.
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_ASSET_V: dict[str, str] = {}


def asset_v(name: str) -> str:
    if name not in _ASSET_V:
        _ASSET_V[name] = hashlib.md5((_ASSETS_DIR / name).read_bytes()).hexdigest()[:8]
    return _ASSET_V[name]


SITE_NAME = "Фрейдариум"
# Марка в шапке — тот же профиль, что и в главном логотипе, но без цветного
# фона (currentColor): фон нужен только отдельному favicon/PWA-иконке
# (assets/icons/icon.svg), которая должна читаться на произвольном фоне.
_PROFILE_MARK = (Path(__file__).parent.parent / "assets" / "icons" / "profile-mark.svg").read_text(encoding="utf-8")

NAV_ITEMS = [
    ("/", "Главная"),
    ("/works/", "Все работы"),
    ("/cases/", "Клинические случаи"),
    ("/texts/", "Полные тексты"),
    ("/maps/", "Карты областей"),
    ("/tags/", "Все теги"),
    ("/notes/", "Мои заметки"),
    ("/notes/?only=bookmarks", "Закладки"),
    ("/about/", "О проекте"),
]


def page(title: str, description: str, body_html: str, site_base: str,
         canonical_path: str, back_href: str | None = None,
         back_label: str = "Назад", extra_head: str = "",
         pagefind_filters: dict | None = None, pagefind_ignore: bool = False,
         pre_main_html: str = "") -> str:
    full_title = title if title == SITE_NAME else f"{title} — {SITE_NAME}"
    esc_title = html.escape(full_title)
    esc_title_raw = html.escape(title)
    esc_desc = html.escape(description or "")
    assets = f"{site_base}/assets"
    back_html = ""
    if back_href:
        back_html = (
            f'<a class="back-link" href="{html.escape(back_href)}" data-back>'
            f'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M15 18l-6-6 6-6"/></svg>'
            f'<span>{html.escape(back_label)}</span></a>'
        )

    main_attrs = 'id="main"'
    if pagefind_ignore:
        main_attrs += ' data-pagefind-ignore'
    else:
        main_attrs += ' data-pagefind-body'
        for key, val in (pagefind_filters or {}).items():
            main_attrs += f' data-pagefind-filter="{html.escape(key)}:{html.escape(val)}"'

    nav_html = "".join(
        f'<a class="nav-link" href="{site_base}{href}">{label}</a>' for href, label in NAV_ITEMS
    )

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc_title}</title>
<meta name="description" content="{esc_desc}">
<link rel="canonical" href="{html.escape(canonical_path)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500;1,600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{assets}/style.css?v={asset_v("style.css")}">
<link rel="manifest" href="{site_base}/manifest.webmanifest">
<meta name="theme-color" content="#EFE2D8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2A1F2D" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{assets}/icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{assets}/icons/icon.svg">
<!-- БАГ, исправленный 30.07.2026: html.escape(repr(x)) экранирует кавычку
     в HTML-сущность &#x27;, а .replace("'", '"') после этого уже ничего не
     находит (кавычки-то больше нет, есть &#x27;) — сущность утекала прямо в
     JS внутри <script>, где HTML-сущности НЕ раскрываются браузером (это не
     HTML-контент, а сырой текст скрипта). Получался синтаксис вида
     window.__SITE_BASE__=&#x27;/freudarium&#x27; — ошибка парсинга JS, и
     переменная НИКОГДА не устанавливалась (весь код читал её как ""). Отсюда
     404 у поиска (SITE_BASE+"/search/" превращался в "/search/" без
     префикса) и неправильные ссылки в экспорте/«Моих заметках». json.dumps
     даёт валидный JS-литерал в двойных кавычках — без этой ловушки. -->
<script>window.__SITE_BASE__={json.dumps(site_base)};</script>
<!-- Официальный SDK Telegram Mini Apps. Без него window.Telegram вообще не
     существует — tg.js (см. assets/tg.js) молча выключает себя целиком, а
     значит и класс .in-telegram никогда не появляется, и все завязанные на
     него функции (наше выделение долгим тапом, синхронизация заметок в
     CloudStorage, вибрация, кнопка «назад») не работают — не потому что
     сломаны, а потому что сами не видят, что находятся внутри Telegram.
     Грузится синхронно в head, как рекомендует официальная документация —
     чтобы объект был готов ещё до тела страницы. -->
<script src="https://telegram.org/js/telegram-web-app.js"></script>
{extra_head}
</head>
<body>
<header class="topbar" id="topbar" data-pagefind-ignore>
  {back_html}
  <a class="brand" href="{site_base}/">
    <span class="brand-mark">{_PROFILE_MARK}</span>
    <span>{SITE_NAME}</span>
  </a>
  <div class="topbar-actions">
    <button class="icon-btn" id="bookmarkBtn" title="Добавить в избранное" aria-label="Добавить в избранное" hidden data-pagefind-ignore>
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-6-4-6 4V3Z"/></svg>
    </button>
    <button class="icon-btn" id="searchBtn" title="Поиск" aria-label="Поиск">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
    </button>
    <button class="icon-btn" id="menuBtn" title="Разделы" aria-label="Разделы">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
  </div>
</header>
{pre_main_html}
<main {main_attrs}>
<span data-pagefind-meta="title" hidden>{esc_title_raw}</span>
{body_html}
</main>

<!-- Ненавязчивая подпись автора внизу каждой страницы (в дополнение к
     «О проекте» и пункту в меню ☰) — пока с тем же значком-силуэтом, что и
     в шапке; когда пришлют собственное лого, заменить только эту иконку. -->
<footer class="site-footer" data-pagefind-ignore>
  <span class="site-footer-mark">{_PROFILE_MARK}</span>
  <span>Автор — <a href="https://t.me/chtotonapsy" target="_blank" rel="noopener">@chtotonapsy</a> в Telegram
  · <a href="{site_base}/privacy/">Политика конфиденциальности</a></span>
</footer>

<div class="toast" id="toast" data-pagefind-ignore></div>

<div class="sel-toolbar" id="selToolbar" hidden data-pagefind-ignore>
  <button class="sel-color" data-color="bruise" aria-label="Выделить лиловым"></button>
  <button class="sel-color" data-color="flesh" aria-label="Выделить тёплым"></button>
  <button class="sel-color" data-color="verdigris" aria-label="Выделить зелёным"></button>
  <button class="sel-note-btn" data-action="note">Заметка</button>
  <button class="sel-note-btn" data-action="send">Отправить</button>
  <button class="sel-note-btn" data-action="report">Правка</button>
</div>

<!-- Панель по тапу на уже сохранённое выделение/заметку (mark.user-mark в
     тексте) — перекрасить, отредактировать комментарий, отправить в чат,
     удалить. Тот же принцип, что у selToolbar выше, просто для существующей
     записи, а не для нового выделения. -->
<div class="sel-toolbar" id="noteQuickBar" hidden data-pagefind-ignore>
  <button class="sel-color" data-color="bruise" aria-label="Перекрасить лиловым"></button>
  <button class="sel-color" data-color="flesh" aria-label="Перекрасить тёплым"></button>
  <button class="sel-color" data-color="verdigris" aria-label="Перекрасить зелёным"></button>
  <button class="sel-note-btn" data-action="edit">Заметка</button>
  <button class="sel-note-btn" data-action="send">Отправить</button>
  <button class="sel-note-btn" data-action="delete">Удалить</button>
</div>

<div class="sheet" id="noteComposer" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Заметка к выделенному</h3>
    <blockquote class="composer-quote" id="composerQuoteView"></blockquote>
    <input type="hidden" name="quote">
    <textarea name="comment" class="composer-textarea" rows="4" placeholder="Ваш комментарий…"></textarea>
    <div class="composer-actions">
      <button class="btn btn-primary" data-composer-save>Сохранить</button>
      <button class="btn" data-composer-cancel>Отмена</button>
      <button class="icon-btn" data-composer-send aria-label="Отправить в чат" title="Отправить в чат">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22 11 13 2 9 22 2Z"/></svg>
      </button>
    </div>
  </div>
</div>

<!-- Комментарий / «Предложить правку» — автору сайта в Telegram (не автору
     запроса, см. assets/tg.js:freudSendFeedback). Одна шторка на оба сценария:
     с цитатой (запущена из selToolbar по выделению — data-action="report")
     и без (запущена кнопкой «Написать администратору» внизу страницы заметки). -->
<div class="sheet" id="feedbackSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3 id="feedbackSheetTitle">Написать администратору</h3>
    <blockquote class="composer-quote" id="feedbackQuoteView" hidden></blockquote>
    <textarea name="feedback-text" class="composer-textarea" rows="4" placeholder="Ваше сообщение…"></textarea>
    <div class="composer-actions">
      <button class="btn btn-primary" data-feedback-send>Отправить администратору</button>
      <button class="btn" data-close-sheet>Отмена</button>
    </div>
  </div>
</div>

<!-- Раньше жил только на /notes/ — теперь нужен и в панелях выделения на
     любой странице (кнопка «Отправить»), поэтому здесь, в общем layout. -->
<div class="sheet" id="exportFormatSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Отправить в чат с ботом</h3>
    <button class="btn" data-export="md">MD-файл</button>
    <button class="btn" data-export="doc">DOC-файл</button>
    <button class="btn" data-export="text">Просто текст в чат</button>
    <button class="sheet-close" data-close-sheet>Отмена</button>
  </div>
</div>

<div class="sheet" id="downloadSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Скачать заметку</h3>
    <p class="sheet-hint">Внутри Telegram файл придёт в чат с ботом; вне Telegram — обычным скачиванием.</p>
    <button class="btn dl-format" data-dl-format="md">MD для Obsidian</button>
    <button class="btn dl-format" data-dl-format="doc">DOC</button>
    <button class="btn dl-format" data-dl-format="text">Текст в чат</button>
    <button class="btn dl-format" data-dl-format="env">С окружением (.zip, MD)</button>
    <button class="sheet-close" data-close-sheet>Закрыть</button>
  </div>
</div>

<!-- Покупка платного доступа (карты областей + личные инструменты) —
     вручную: реквизиты и приём квитанции идут через чат с ботом, эта
     шторка только берёт согласие на обработку персональных данных и
     запускает заявку (см. assets/access.js, POST /purchase/start). -->
<div class="sheet" id="purchaseSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Купить полный доступ</h3>
    <div id="purchaseSheetBody">
      <p class="sheet-hint">Разовая покупка — 1500₽ / 15€. Открывает карты
        областей и личные инструменты: закладки, заметки на полях,
        отправку в чат, скачивание.</p>
      <label class="consent-row">
        <input type="checkbox" id="purchaseConsent">
        <span>Я даю согласие на обработку персональных данных согласно
          <a href="{site_base}/privacy/" target="_blank" rel="noopener">Политике</a></span>
      </label>
      <button class="btn btn-primary" id="purchaseSubmitBtn" disabled>Отправить реквизиты</button>
    </div>
    <p class="sheet-hint" id="purchaseOutsideTelegramHint" hidden>
      Купить можно только внутри Telegram — бот присылает реквизиты и
      принимает квитанцию прямо в чате.
      <a href="https://t.me/freudarium_bot/app">Открыть в Telegram →</a>
    </p>
    <button class="sheet-close" data-close-sheet>Отмена</button>
  </div>
</div>

<div class="sheet" id="svgLightbox" hidden data-pagefind-ignore>
  <div class="sheet-inner svg-lightbox-inner">
    <button class="sheet-close svg-lightbox-close" data-close-sheet>Закрыть ✕</button>
    <div class="svg-lightbox-stage"></div>
  </div>
</div>

<button class="fab-back" id="fabBack" data-back aria-label="Назад" hidden data-pagefind-ignore>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
    stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
</button>

<button class="fab-top" id="fabTop" aria-label="Наверх" hidden data-pagefind-ignore>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
    stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>
</button>

<div class="sheet" id="menuSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Разделы</h3>
    <nav class="nav-list">{nav_html}</nav>
    <button class="btn" id="openSettingsBtn">Настройки</button>
    <button class="sheet-close" data-close-sheet>Закрыть</button>
    <p class="menu-author">Автор — <a href="https://t.me/chtotonapsy" target="_blank" rel="noopener">@chtotonapsy</a></p>
    <p class="build-stamp">сборка {_BUILD_STAMP} · {asset_v("annotations.js")[:6]}</p>
  </div>
</div>

<div class="sheet" id="settingsSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Настройки</h3>
    <div class="settings-row">
      <span>Тема</span>
      <div class="seg" data-setting="theme">
        <button data-value="light">Светлая</button>
        <button data-value="sepia">Сепия</button>
        <button data-value="dark">Тёмная</button>
      </div>
    </div>
    <div class="settings-row">
      <span>Кегль</span>
      <div class="seg" data-setting="fontsize">
        <button data-value="s">A</button>
        <button data-value="m">A</button>
        <button data-value="l">A</button>
        <button data-value="xl">A</button>
      </div>
    </div>
    <button class="btn" id="addToHomeBtn" hidden>Добавить на экран «Домой»</button>
    <p class="settings-hint" id="addToHomeHint" hidden></p>
    <button class="sheet-close" data-close-sheet>Готово</button>
  </div>
</div>

<!-- tg.js — первым: определяет window.freudHomeScreenSupported/
     freudAddToHomeScreen синхронно при загрузке, а app.js читает их тоже
     синхронно (не лениво, не в обработчике) сразу при разборе, чтобы решить,
     показывать ли кнопку «Добавить на экран „Домой“» — если бы tg.js
     выполнялся позже, эти переменные ещё не существовали бы в момент
     проверки, и кнопка внутри Telegram никогда бы не показывалась. -->
<script src="{assets}/access.js?v={asset_v("access.js")}"></script>
<script src="{assets}/tg.js?v={asset_v("tg.js")}"></script>
<script src="{assets}/app.js?v={asset_v("app.js")}"></script>
<script src="{assets}/annotations.js?v={asset_v("annotations.js")}"></script>
<script src="{assets}/comments.js?v={asset_v("comments.js")}"></script>
<!-- hub-keywords.js — не файл из assets/, а сгенерированный build.py
     словарь понятие→карта (word-list меняется вместе с логикой куда чаще,
     чем сам по себе), поэтому версионируем общим хэшем с conceptlinks.js,
     а не своим отдельным (его нет в исходном дереве assets/ для asset_v). -->
<script src="{assets}/hub-keywords.js?v={asset_v("conceptlinks.js")}"></script>
<script src="{assets}/conceptlinks.js?v={asset_v("conceptlinks.js")}"></script>
<script src="{assets}/hub-gate.js?v={asset_v("hub-gate.js")}"></script>
</body>
</html>"""
