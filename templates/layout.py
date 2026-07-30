"""Общая HTML-обёртка страницы: <head>, шапка с липкой полосой «Назад»,
меню разделов, шторка оформления, плавающая кнопка «назад», подключение
assets. Также вешает pagefind-атрибуты (data-pagefind-*) для этапа поиска.

site_base — корень сайта (например "" локально или "/freud" на Pages без
домена); assets — всегда site_base + "/assets"."""
import html
from pathlib import Path

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
    ("/about/", "О проекте"),
]


def page(title: str, description: str, body_html: str, site_base: str,
         canonical_path: str, back_href: str | None = None,
         back_label: str = "Назад", extra_head: str = "",
         pagefind_filters: dict | None = None, pagefind_ignore: bool = False) -> str:
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
<link rel="stylesheet" href="{assets}/style.css">
<link rel="manifest" href="{site_base}/manifest.webmanifest">
<meta name="theme-color" content="#EFE2D8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2A1F2D" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{assets}/icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{assets}/icons/icon.svg">
<script>window.__SITE_BASE__={html.escape(repr(site_base)).replace("'", '"')};</script>
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

<main {main_attrs}>
<span data-pagefind-meta="title" hidden>{esc_title_raw}</span>
{body_html}
</main>

<div class="toast" id="toast" data-pagefind-ignore></div>

<div class="sel-toolbar" id="selToolbar" hidden data-pagefind-ignore>
  <button class="sel-color" data-color="bruise" aria-label="Выделить лиловым"></button>
  <button class="sel-color" data-color="flesh" aria-label="Выделить тёплым"></button>
  <button class="sel-color" data-color="verdigris" aria-label="Выделить зелёным"></button>
  <button class="sel-note-btn" data-action="note">Заметка</button>
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
    </div>
  </div>
</div>

<button class="fab-back" id="fabBack" data-back aria-label="Назад" hidden data-pagefind-ignore>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
    stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
</button>

<div class="sheet" id="menuSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Разделы</h3>
    <nav class="nav-list">{nav_html}</nav>
    <button class="btn" id="openSettingsBtn">Настройки</button>
    <button class="sheet-close" data-close-sheet>Закрыть</button>
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

<script src="{assets}/app.js"></script>
<script src="{assets}/annotations.js"></script>
<script src="{assets}/tg.js"></script>
</body>
</html>"""
