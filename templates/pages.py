"""Рендер конкретных типов страниц: заметка, работа, глава полного текста,
карта области, тег, главная. Возвращают HTML тела страницы (без обёртки —
её добавляет layout.page)."""
import html
import re

from . import mdconv

_P_TAG_RE = re.compile(r'<p id="(p[a-zA-Z0-9]*)">(.*?)</p>', re.DOTALL)


def _inject_note_markers(body_html, anchor_notes, note_url):
    """anchor_notes: {anchor: [note_id, ...]} — заметки, у которых
    Полный-текст:: указывает именно на этот абзац. Добавляет к абзацу
    маленькие кружки-ссылки на них (переход «из полного текста — в заметки»)."""
    if not anchor_notes:
        return body_html

    def repl(m):
        anchor, content = m.group(1), m.group(2)
        note_ids = anchor_notes.get(anchor)
        if not note_ids:
            return m.group(0)
        links = "".join(
            f'<a class="p-note-link" href="{html.escape(url)}" title="Заметка об этом месте">●</a>'
            for url in (note_url(nid) for nid in note_ids)
            if url
        )
        if not links:
            return m.group(0)
        return f'<p id="{anchor}">{content}<span class="p-note-links">{links}</span></p>'

    return _P_TAG_RE.sub(repl, body_html)


def _tag_chip(tag, tag_url):
    url = tag_url(tag)
    if url:
        return f'<a class="chip" href="{html.escape(url)}">{html.escape(tag)}</a>'
    return f'<span class="chip chip-muted">{html.escape(tag)}</span>'


def _note_card(note, ctx, small=False):
    url = ctx["note_url"](note["id"])
    cls = "card card-sm" if small else "card"
    kicker = ""
    if note.get("source_work_id"):
        w = ctx["works_by_id"].get(note["source_work_id"])
        if w:
            kicker = f'<span class="card-kicker">{html.escape(w["title"])}, {html.escape(w["year"] or "")}</span>'
    return (
        f'<a class="{cls}" href="{html.escape(url)}">'
        f'{kicker}<span class="card-title">{html.escape(_display_title(note["id"]))}</span>'
        f"</a>"
    )


_HUB_SUFFIX_RE = re.compile(r"\s*—\s*карта области\s*\(Фрейд\)\s*$")


def _display_title(note_id: str) -> str:
    """Заголовок для карточки — id заметки и есть заголовок (без .md).
    Суффикс «— карта области (Фрейд)» нужен только для классификации файлов
    в build_export.py — на сайте не показываем, читателю он ничего не даёт."""
    return _HUB_SUFFIX_RE.sub("", note_id)


def render_note(note, ctx):
    """ctx: resolve_link, note_url, work_url, fulltext_anchor_url, tag_url,
    works_by_id, backlinks_by_id, site_base, assets_base"""
    body_html = mdconv.render_body(note["body"], ctx["resolve_link"], ctx["assets_base"])

    work = ctx["works_by_id"].get(note["source_work_id"]) if note.get("source_work_id") else None
    crumbs = ""
    if work:
        wurl = ctx["work_url"](note["source_work_id"])
        crumbs = (
            f'<div class="crumbs"><a href="{html.escape(wurl)}">{html.escape(work["title"])}</a>'
            f' · {html.escape(work["year"] or "")}'
            + (f' · {html.escape(note["source_detail"])}' if note.get("source_detail") else "")
            + "</div>"
        )

    tags_html = ""
    if note["tags"]:
        chips = "".join(_tag_chip(t, ctx["tag_url"]) for t in note["tags"])
        tags_html = f'<div class="chips">{chips}</div>'

    # Панель связей
    def link_list(ids, label, empty=None):
        items = []
        for tid in ids:
            url = ctx["resolve_link"](tid)
            if url:
                items.append(f'<li><a href="{html.escape(url)}">{html.escape(_display_title(tid))}</a></li>')
        if not items:
            return ""
        return f'<section class="rel-block"><h2>{label}</h2><ul class="rel-list">{"".join(items)}</ul></section>'

    forward_ids = note["forward_links"]
    other_ids = [i for i in note["links_out"] if i not in forward_ids]
    backlinks = ctx["backlinks_by_id"].get(note["id"], [])

    rel_html = (
        link_list(forward_ids, "Дальше по мысли")
        + link_list(other_ids, "Связано")
        + link_list(backlinks, "Сюда ссылаются")
    )

    fulltext_html = ""
    refs = note.get("full_text_refs") or []
    if refs:
        by_target = {}
        for ref in refs:
            by_target.setdefault(ref["target"], []).append(ref.get("anchor"))
        items = []
        for target, anchors in by_target.items():
            first_url = ctx["fulltext_anchor_url"](target, anchors[0])
            if not first_url:
                continue
            w = ctx["works_by_id"].get(note.get("source_work_id"))
            label = w["title"] if w else _display_title(target)
            if len(anchors) == 1:
                items.append(f'<li><a href="{html.escape(first_url)}">Читать в «{html.escape(label)}»</a></li>')
            else:
                # несколько мест в одной работе — нумерованные переходы к каждому,
                # а не одинаковые на вид ссылки одна за другой
                spots = "".join(
                    f'<a class="p-note-link" href="{html.escape(spot_url)}">{i + 1}</a>'
                    for i, a in enumerate(anchors)
                    if (spot_url := ctx["fulltext_anchor_url"](target, a))
                )
                items.append(
                    f'<li><a href="{html.escape(first_url)}">Читать в «{html.escape(label)}»</a>'
                    f'<span class="p-note-links">{spots}</span></li>'
                )
        if items:
            fulltext_html = f'<section class="rel-block rel-fulltext"><ul class="rel-list">{"".join(items)}</ul></section>'

    downloads_html = ctx["downloads_widget"](note)

    return f"""
<article class="note-page">
  {crumbs}
  <h1 class="note-title">{html.escape(_display_title(note["id"]))}</h1>
  <div class="note-body">
    {body_html}
  </div>
  {tags_html}
  {fulltext_html}
  {rel_html}
  {downloads_html}
</article>
"""


def render_work(conspect_note, work, atomic_notes, source_note, ctx):
    body_html = mdconv.render_body(
        conspect_note["body"], ctx["resolve_link"], ctx["assets_base"], collapse_intro=True
    )

    source_html = ""
    if source_note:
        source_body_html = mdconv.render_body(
            source_note["body"], ctx["resolve_link"], ctx["assets_base"], collapse_intro=True
        )
        source_html = (
            '<section class="rel-block"><h2>Источник</h2>'
            f'<div class="note-body">{source_body_html}</div>'
            "</section>"
        )

    fulltext_url = ctx.get("fulltext_first_url", lambda wid: None)(work["id"])
    ft_html = ""
    if fulltext_url:
        ft_html = f'<a class="btn btn-primary" href="{html.escape(fulltext_url)}">Читать полный текст</a>'

    cards = "".join(_note_card(n, ctx, small=True) for n in atomic_notes)
    downloads_html = ctx["downloads_widget_work"](work)

    return f"""
<article class="work-page">
  <div class="crumbs"><a href="{ctx["site_base"]}/works/">Все работы</a></div>
  <h1 class="note-title">{html.escape(work["title"])}</h1>
  <p class="work-meta">{html.escape(work["author"] or "Фрейд")}</p>
  <div class="stat-tiles">
    <div class="stat-tile"><span class="stat-num">{work["atomic_note_count"]}</span><span class="stat-label">заметок</span></div>
    <div class="stat-tile stat-tile-dark"><span class="stat-num">{html.escape(work["year"] or "—")}</span><span class="stat-label">публикация</span></div>
  </div>
  <div class="work-actions">{ft_html}</div>
  <div class="note-body">
    {body_html}
  </div>
  {source_html}
  <section class="rel-block">
    <h2>Заметки этой работы</h2>
    <div class="card-grid">{cards}</div>
  </section>
  {downloads_html}
</article>
"""


def render_fulltext_chapter(work_title, work_meta, chapters, idx, ctx, base_url, anchor_notes=None):
    chapter = chapters[idx]
    body_html = mdconv.render_body(
        chapter["body"], ctx["resolve_link"], ctx["assets_base"], collapse_intro=(idx == 0)
    )
    body_html = _inject_note_markers(body_html, anchor_notes, ctx["note_url"])

    nav_items = []
    for i, ch in enumerate(chapters):
        url = base_url if i == 0 else f"{base_url}{i + 1}/"
        label = ch["title"] or "Начало"
        active = " active" if i == idx else ""
        nav_items.append(f'<a class="chapter-link{active}" href="{html.escape(url)}">{html.escape(label)}</a>')
    nav_html = f'<nav class="chapter-nav">{"".join(nav_items)}</nav>'

    prev_url = None if idx == 0 else (base_url if idx - 1 == 0 else f"{base_url}{idx}/")
    next_url = None if idx == len(chapters) - 1 else f"{base_url}{idx + 2}/"
    pager = '<div class="chapter-pager">'
    pager += f'<a class="btn" href="{html.escape(prev_url)}">← Предыдущая глава</a>' if prev_url else "<span></span>"
    pager += f'<a class="btn" href="{html.escape(next_url)}">Следующая глава →</a>' if next_url else ""
    pager += "</div>"

    title = chapter["title"] or work_title
    year = (work_meta or {}).get("year") or ""
    kicker = f"ГЛАВА {idx + 1:02d}" if chapter["title"] else "НАЧАЛО"
    return f"""
<article class="fulltext-page">
  <header class="chapter-hero">
    <div class="chapter-kicker"><span>{html.escape(kicker)}</span><span>{html.escape(year)}</span></div>
    <h1 class="chapter-title">{html.escape(title)}</h1>
    <div class="chapter-dashes"><span class="dash dash-bruise"></span><span class="dash dash-verdigris"></span></div>
  </header>
  <div class="crumbs"><a href="{ctx["work_url"](work_meta["id"])}">{html.escape(work_title)}</a> · полный текст</div>
  {nav_html}
  <div class="note-body fulltext-body">
    {body_html}
  </div>
  {pager}
</article>
"""


def render_hub(hub_note, ctx):
    body_html = mdconv.render_body(hub_note["body"], ctx["resolve_link"], ctx["assets_base"])
    downloads_html = ctx["downloads_widget_hub"](hub_note)
    return f"""
<article class="hub-page">
  <div class="crumbs"><a href="{ctx["site_base"]}/maps/">Все карты областей</a></div>
  <h1 class="note-title">{html.escape(_display_title(hub_note["id"]))}</h1>
  <div class="note-body">
    {body_html}
  </div>
  {downloads_html}
</article>
"""


def render_cases(cases, ctx):
    """cases: [(work, conspect_note, blurb)]"""
    cards = "".join(
        f'<a class="card" href="{ctx["work_url"](work["id"])}">'
        f'<span class="card-title">{html.escape(work["title"])}</span>'
        f'<span class="card-kicker">{html.escape(work["year"] or "")} · {work["atomic_note_count"]} заметок</span>'
        f"</a>"
        for work, _note, _blurb in cases
    )
    return f"""
<article class="index-page">
  <h1 class="note-title">Клинические случаи</h1>
  <p class="work-meta">Пять больших историй болезни, разобранных Фрейдом целиком — вход и в конспект, и в полный текст.</p>
  <div class="card-grid">{cards}</div>
</article>
"""


def render_texts(entries, ctx):
    """entries: [(work_or_none, full_text_note, base_url)]"""
    rows = "".join(
        f'<a class="row" href="{base_url}">'
        f'<span class="row-year">{html.escape((work["year"] if work else "") or "")}</span>'
        f'<span class="row-title">{html.escape(work["title"] if work else _display_title(ft["id"]))}</span>'
        f"</a>"
        for work, ft, base_url in entries
    )
    return f"""
<article class="index-page">
  <h1 class="note-title">Полные тексты</h1>
  <p class="work-meta">Переводы работ целиком, по главам — с переходами к заметкам, разбирающим конкретные абзацы.</p>
  <div class="rows">{rows}</div>
</article>
"""


def render_about(ctx):
    return f"""
<article class="index-page">
  <h1 class="note-title">О проекте</h1>
  <div class="note-body">
    <p>«Фрейдариум» — атомарная база работ Зигмунда Фрейда: каждая мысль —
    отдельная заметка со своими связями, а не сплошной текст, который читают
    по порядку.</p>
    <p>Собрано по методу Zettelkasten в Obsidian и опубликовано как открытый
    сайт и Telegram-приложение.</p>
    <p>Автор проекта — <a href="https://t.me/chtotonapsy" target="_blank" rel="noopener">@chtotonapsy</a> в Telegram.</p>
  </div>
</article>
"""


def render_search(ctx):
    return f"""
<article class="search-page">
  <h1 class="note-title">Поиск</h1>
  <div class="search-box">
    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
    <input type="search" id="searchInput" placeholder="Слово, тема, работа…" autocomplete="off">
  </div>
  <div class="search-filters" id="searchFilters">
    <button class="search-filter active" data-type="">Всё</button>
    <button class="search-filter" data-type="заметка">Заметки</button>
    <button class="search-filter" data-type="работа">Работы</button>
    <button class="search-filter" data-type="полный текст">Полные тексты</button>
    <button class="search-filter" data-type="карта">Карты</button>
  </div>
  <div class="search-results" id="searchResults"></div>
  <p class="search-empty" id="searchEmpty" hidden>Ничего не нашлось.</p>
</article>
<script type="module" src="{ctx["assets_base"]}/search.js"></script>
"""


def render_my_notes(ctx):
    return f"""
<article class="mynotes-page">
  <h1 class="note-title">Мои пометки</h1>
  <p class="work-meta">Закладки, выделения и заметки, которые вы оставили при чтении —
    хранятся у вас в браузере, а внутри Telegram ещё и синхронизируются между устройствами.</p>
  <div class="mynotes-empty" id="mynotesEmpty" hidden>Пока ничего нет — выделите текст на любой странице, чтобы отметить или прокомментировать его, или нажмите «В избранное» в шапке.</div>
  <section class="rel-block" id="mynotesBookmarks" hidden>
    <h2>Закладки</h2>
    <div class="rows" id="mynotesBookmarksList"></div>
  </section>
  <section class="rel-block" id="mynotesNotes" hidden>
    <h2>Заметки</h2>
    <div class="mynotes-list" id="mynotesNotesList"></div>
  </section>
  <section class="rel-block" id="mynotesHighlights" hidden>
    <h2>Выделения</h2>
    <div class="mynotes-list" id="mynotesHighlightsList"></div>
  </section>
</article>
<div class="sheet" id="exportFormatSheet" hidden data-pagefind-ignore>
  <div class="sheet-inner">
    <h3>Отправить в чат с ботом</h3>
    <button class="btn" data-export="md">MD-файл</button>
    <button class="btn" data-export="doc">DOC-файл</button>
    <button class="btn" data-export="text">Просто текст в чат</button>
    <button class="sheet-close" data-close-sheet>Отмена</button>
  </div>
</div>
<script src="{ctx["assets_base"]}/mynotes.js" defer></script>
"""


def render_tag(tag, notes, ctx):
    cards = "".join(_note_card(n, ctx) for n in notes)
    return f"""
<article class="tag-page">
  <div class="crumbs"><a href="{ctx["site_base"]}/tags/">Все теги</a></div>
  <h1 class="note-title">#{html.escape(tag)}</h1>
  <p class="work-meta">{len(notes)} заметок</p>
  <div class="card-grid">{cards}</div>
</article>
"""


ONBOARD_HTML = (
    '<div class="onboard" id="onboardCard">'
    '<button class="onboard-close" id="onboardClose" aria-label="Скрыть">&times;</button>'
    "<p><strong>Это не книга, которую читают от корки до корки.</strong> "
    "Здесь — тысячи отдельных мыслей Фрейда, каждая на своей карточке. Часть "
    "связей между ними — из его собственных текстов, часть — прослежена между "
    "разными работами уже при составлении базы.</p>"
    "<p>Начните с любой работы или темы и идите дальше по ссылкам "
    "«Дальше по мысли» внизу каждой заметки — или нажмите «Случайная заметка» "
    "и посмотрите, куда выведет.</p>"
    "</div>"
)


def _decade_groups(works_sorted):
    groups = {}
    for w in works_sorted:
        year = w["year"] or "9999"
        try:
            decade = f"{int(year[:4]) // 10 * 10}-е"
        except ValueError:
            decade = "без даты"
        groups.setdefault(decade, []).append(w)
    return groups


def render_home(works, hubs, tags_top, stats, ctx):
    works_sorted = sorted(works, key=lambda w: (w["year"] or "9999"))
    decades_html = ""
    for decade, group in _decade_groups(works_sorted).items():
        rows = "".join(
            f'<a class="row" href="{ctx["work_url"](w["id"])}">'
            f'<span class="row-year">{html.escape(w["year"] or "")}</span>'
            f'<span class="row-title">{html.escape(w["title"])}</span>'
            f'<span class="row-count">{w["atomic_note_count"]}</span></a>'
            for w in group
        )
        decades_html += (
            f"<details class=\"decade\"><summary>{decade} <span class=\"decade-count\">"
            f'{len(group)}</span></summary><div class="rows">{rows}</div></details>'
        )
    hub_cards = "".join(
        f'<a class="card card-sm" href="{ctx["hub_url"](h["id"])}"><span class="card-title">{html.escape(_display_title(h["id"]))}</span></a>'
        for h in hubs
    )
    tag_chips = "".join(_tag_chip(t, ctx["tag_url"]) for t in tags_top)
    sb = ctx["site_base"]

    # tag_url/hub_url и т.п. уже возвращают абсолютный путь с site_base —
    # приписывать sb к ним ещё раз нельзя (раньше давало двойной префикс
    # и 404 на карточке «Сны»); у остальных href — короткие относительные пути.
    dreams_url = ctx["tag_url"]("сны") or f"{sb}/tags/"
    entry_points = (
        "".join(
            f'<a class="card" href="{sb}{href}"><span class="card-title">{label}</span>'
            f'<span class="card-kicker">{sub}</span></a>'
            for href, label, sub in [
                ("/texts/", "Полные тексты", "Читать работу целиком, главами"),
                ("/cases/", "Клинические случаи", "Ганс, Крыса, Шребер, Волк, Дора"),
                ("/maps/", "Карты областей", "Структурные заметки по темам"),
            ]
        )
        + f'<a class="card" href="{dreams_url}"><span class="card-title">Сны</span>'
        f'<span class="card-kicker">Заметки-разборы сновидений</span></a>'
    )

    return f"""
<article class="home-page">
  <figure class="hero-banner">
    <img src="{ctx["assets_base"]}/hero-header.webp" alt="" width="1672" height="941" fetchpriority="high">
  </figure>
  <section class="hero">
    <h1 class="hero-title">Фрейдариум</h1>
    <p>Атомарная база работ Зигмунда Фрейда — {stats["atomic"]} заметок,
      {stats["works"]} работ, полные тексты, связи между мыслями.</p>
    <a class="btn btn-primary" href="{sb}/n/random/">Случайная заметка</a>
    <a class="btn" href="{sb}/search/">Поиск</a>
  </section>

  {ONBOARD_HTML}

  <section class="rel-block">
    <h2>С чего начать</h2>
    <div class="card-grid">{entry_points}</div>
  </section>

  <section class="rel-block">
    <h2>Работы по годам</h2>
    {decades_html}
  </section>

  <section class="rel-block">
    <h2>Карты областей</h2>
    <div class="card-grid">{hub_cards}</div>
  </section>

  <section class="rel-block">
    <h2>Частые темы</h2>
    <div class="chips">{tag_chips}</div>
    <a class="see-all" href="{sb}/tags/">Все теги →</a>
  </section>
</article>
"""
