"""Рендер конкретных типов страниц: заметка, работа, глава полного текста,
карта области, тег, главная. Возвращают HTML тела страницы (без обёртки —
её добавляет layout.page)."""
import hashlib
import html
import re

from . import mdconv, provenance
from .layout import asset_v

_P_TAG_RE = re.compile(r'<p id="(p[a-zA-Z0-9]*)">(.*?)</p>', re.DOTALL)

# Метка для pagefind/резервного поиска (build.py) — согласована с кнопками
# фильтра в render_search() ниже: «полный текст» одним типом на всех не
# годился (обещал перевод там, где его нет), а pagefind и search.js должны
# возвращать одно и то же множество результатов на один и тот же фильтр.
PROV_SEARCH_TYPE = {
    "translation": "перевод",
    "assembled": "пересказ",
    "digest": "пересказ",
    "retelling": "пересказ",
}


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


# Комментарий/«Предложить правку» автору (Фаза 5, 30.07.2026) — открывает
# #feedbackSheet без цитаты (annotations.js: data-feedback-open). Правка с
# цитатой запускается иначе — выделением текста и кнопкой «Правка» в
# selToolbar, у неё готовая цитата, отдельная кнопка тут не нужна.
_FEEDBACK_LINK_HTML = (
    '<p class="feedback-link"><button class="chip-muted-btn" data-feedback-open>'
    "Заметили неточность или хотите что-то сказать автору? Написать →</button></p>"
)

# Публичная лента комментариев (Фаза 5, продолжение, 31.07.2026) — видна
# всем читателям, в отличие от _FEEDBACK_LINK_HTML выше (тот уходит только
# автору в личку). Разметка статическая — сам список комментариев грузит
# assets/comments.js с воркера уже на клиенте, в момент открытия страницы
# (build.py не знает о комментариях, они не существуют на этапе сборки).
_COMMENTS_SECTION_HTML = """
<section class="comments-section" id="commentsSection" data-pagefind-ignore>
  <h2>Комментарии</h2>
  <div class="comments-list"><p class="comments-empty">Загрузка…</p></div>
  <div class="comments-reply-banner" hidden>
    В ответ <span class="comments-reply-name"></span>
    <button type="button" data-cancel-reply aria-label="Отменить ответ">✕</button>
  </div>
  <form class="comments-form">
    <textarea rows="3" placeholder="Написать комментарий… (нужен Telegram)"></textarea>
    <button type="submit" class="btn btn-primary">Отправить</button>
  </form>
</section>
"""


# Цветные чипы тегов (см. референс-макет «Дневник снов», подготовка 30.07.2026)
# — тот же акцентный набор, что уже красит dash'и главы и подсветки выделений,
# не новая палитра. hashlib, не hash() — тот рандомизирован по процессам
# (PYTHONHASHSEED), один и тот же тег красился бы по-разному между сборками.
_CHIP_VARIANTS = ("chip-bruise", "chip-flesh", "chip-verdigris")


def _tag_chip(tag, tag_url):
    variant = _CHIP_VARIANTS[int(hashlib.md5(tag.encode("utf-8")).hexdigest(), 16) % len(_CHIP_VARIANTS)]
    url = tag_url(tag)
    if url:
        return f'<a class="chip {variant}" href="{html.escape(url)}">{html.escape(tag)}</a>'
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
    body_html = mdconv.render_body(note["body"], ctx["resolve_link"], ctx["assets_base"], images_dir=ctx["images_dir"])

    work = ctx["works_by_id"].get(note["source_work_id"]) if note.get("source_work_id") else None

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

    # «Читать в «Работа»» — раньше отдельным блоком-списком далеко под текстом
    # заметки (после тегов), никак не связанным на вид с блоком источника.
    # Смысл один и тот же («откуда эта мысль» + «где прочитать её в тексте
    # целиком»), поэтому оба сведены в один блок .note-source сразу под
    # заголовком: имя работы уже названо там, повторять его в самой ссылке
    # не нужно — если ссылка одна, «Читать в тексте →»; если несколько мест
    # в одной работе — та же нумерация кружками, что была.
    fulltext_reads = []
    refs = note.get("full_text_refs") or []
    if refs:
        by_target = {}
        for ref in refs:
            by_target.setdefault(ref["target"], []).append(ref.get("anchor"))
        for target, anchors in by_target.items():
            first_url = ctx["fulltext_anchor_url"](target, anchors[0])
            if not first_url:
                continue
            same_work = work and _display_title(target).startswith(work["title"])
            if same_work:
                read_label = "Читать в тексте →"
            else:
                read_label = f'Читать в «{html.escape(_display_title(target))}» →'
            if len(anchors) == 1:
                fulltext_reads.append(f'<a class="note-source-read" href="{html.escape(first_url)}">{read_label}</a>')
            else:
                # несколько мест в одной работе — нумерованные переходы к каждому,
                # а не одинаковые на вид ссылки одна за другой
                spots = "".join(
                    f'<a class="p-note-link" href="{html.escape(spot_url)}">{i + 1}</a>'
                    for i, a in enumerate(anchors)
                    if (spot_url := ctx["fulltext_anchor_url"](target, a))
                )
                fulltext_reads.append(
                    f'<a class="note-source-read" href="{html.escape(first_url)}">{read_label}</a>'
                    f'<span class="p-note-links">{spots}</span>'
                )

    source_html = ""
    if work:
        wurl = ctx["work_url"](note["source_work_id"])
        detail = f' · {html.escape(note["source_detail"])}' if note.get("source_detail") else ""
        source_html = (
            '<div class="note-source">'
            '<span class="note-source-label">Источник</span> '
            f'{html.escape(work["author"] or "Фрейд")} · '
            f'<a href="{html.escape(wurl)}">{html.escape(work["title"])}</a>'
            f' · {html.escape(work["year"] or "")}{detail}'
            + ("".join(f'<div class="note-source-links">{r}</div>' for r in fulltext_reads) if fulltext_reads else "")
            + "</div>"
        )

    downloads_html = ctx["downloads_widget"](note)

    return f"""
<article class="note-page">
  <h1 class="note-title">{html.escape(_display_title(note["id"]))}</h1>
  {source_html}
  <div class="note-body">
    {body_html}
  </div>
  {tags_html}
  {downloads_html}
  {rel_html}
  {_FEEDBACK_LINK_HTML}
  {_COMMENTS_SECTION_HTML}
</article>
"""


def render_work(conspect_note, work, atomic_notes, source_note, ctx):
    body_html = mdconv.render_body(
        conspect_note["body"], ctx["resolve_link"], ctx["assets_base"],
        collapse_intro=True, images_dir=ctx["images_dir"],
    )

    source_html = ""
    if source_note:
        source_body_html = mdconv.render_body(
            source_note["body"], ctx["resolve_link"], ctx["assets_base"],
            collapse_intro=True, images_dir=ctx["images_dir"],
        )
        source_html = (
            '<section class="rel-block"><h2>Источник</h2>'
            f'<div class="note-body">{source_body_html}</div>'
            "</section>"
        )

    fulltext_url = ctx.get("fulltext_first_url", lambda wid: None)(work["id"])
    ft_html = ""
    if fulltext_url:
        # Решение о честности происходит ИМЕННО здесь — до клика, а не
        # после: подпись кнопки и подпись класса определяют, что читатель
        # ожидает получить, ещё на этой странице.
        fid = ctx.get("work_to_fulltext", {}).get(work["id"])
        prov = ctx.get("fulltext_prov", {}).get(fid) if fid else None
        if prov and prov["cls"] != "translation":
            ft_html = f'<a class="btn btn-primary" href="{html.escape(fulltext_url)}">Читать пересказ</a>'
            if prov["ready_links"]:
                label, url = prov["ready_links"][0]
                ft_html += f' <a class="btn" href="{html.escape(url)}" target="_blank" rel="noopener">Читать настоящий перевод →</a>'
        else:
            ft_html = f'<a class="btn btn-primary" href="{html.escape(fulltext_url)}">Читать полный текст</a>'

    cards = "".join(_note_card(n, ctx, small=True) for n in atomic_notes)
    downloads_html = ctx["downloads_widget_work"](work)

    return f"""
<article class="work-page">
  <div class="crumbs"><a href="{ctx["site_base"]}/works/">Все работы</a></div>
  <h1 class="note-title">{html.escape(work["title"])}</h1>
  <p class="work-meta">{html.escape(work["author"] or "Фрейд")}</p>
  <div class="stat-tiles">
    <div class="stat-tile stat-tile-accent"><span class="stat-num">{html.escape(work["year"] or "—")}</span><span class="stat-label">год публикации</span></div>
    <div class="stat-tile"><span class="stat-num">{work["atomic_note_count"]}</span><span class="stat-label">заметок</span></div>
  </div>
  <div class="work-actions">{ft_html}</div>
  <div class="note-body">
    {body_html}
  </div>
  {source_html}
  {downloads_html}
  <section class="rel-block">
    <h2>Заметки этой работы</h2>
    <div class="card-grid">{cards}</div>
  </section>
  {_FEEDBACK_LINK_HTML}
  {_COMMENTS_SECTION_HTML}
</article>
"""


def _provenance_banner(prov, compact):
    """Плашка честности «полного текста» — над навигацией по главам.
    compact=False только на главе 1 (полный текст объяснения); compact=True
    на главах 2+ — читатель, попавший туда из поиска, тоже должен видеть
    предупреждение, а не только тот, кто начал с начала (это и было
    прежней дырой: вступление попадало ТОЛЬКО в тело главы 1)."""
    if prov["cls"] == "translation":
        sync = ""
        if prov["ready_links"]:
            links = ", ".join(
                f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(l)}</a>'
                for l, u in prov["ready_links"]
            )
            sync = f' — сверить с готовым переводом: {links}'
        status_suffix = f' · {html.escape(prov["status"])}' if prov["status"] else ""
        return (
            '<div class="prov-banner prov-banner-translation">'
            f'<span class="prov-chip prov-chip-translation">{html.escape(prov["label"])}</span>{sync}{status_suffix}'
            "</div>"
        )

    if prov["ready_links"]:
        label, url = prov["ready_links"][0]
        read_action = f'<a class="prov-read" href="{html.escape(url)}" target="_blank" rel="noopener">Читать настоящий перевод →</a>'
    else:
        read_action = '<span class="prov-no-link">перевода в открытом доступе не нашлось</span>'

    if compact:
        return (
            '<div class="prov-banner prov-banner-compact">'
            f'<span class="prov-chip">{html.escape(prov["label"])}</span> — это не перевод. {read_action}'
            "</div>"
        )

    if prov["ready_links"]:
        actions_html = "".join(
            f'<a class="btn btn-primary prov-read" href="{html.escape(u)}" target="_blank" rel="noopener">'
            + ("Читать настоящий перевод →" if len(prov["ready_links"]) == 1 else f"Читать: {html.escape(l)} →")
            + "</a>"
            for l, u in prov["ready_links"]
        )
    else:
        actions_html = (
            '<p class="prov-no-link">Готового перевода в открытом доступе найти не удалось — '
            "библиография оригинала ниже, в «Источник и детали».</p>"
        )
    status_html = f'<p class="prov-status">Статус: {html.escape(prov["status"])}</p>' if prov["status"] else ""
    return (
        '<div class="prov-banner">'
        f'<span class="prov-chip">{html.escape(prov["label"])}</span>'
        '<p class="prov-explain">Это не перевод. ' + html.escape(prov["explanation"]) + "</p>"
        f'<div class="prov-actions">{actions_html}</div>{status_html}'
        "</div>"
    )


def render_fulltext_chapter(work_title, work_meta, chapters, idx, ctx, base_url, anchor_notes=None, prov=None):
    chapter = chapters[idx]
    body_html = mdconv.render_body(chapter["body"], ctx["resolve_link"], ctx["assets_base"], images_dir=ctx["images_dir"])
    body_html = _inject_note_markers(body_html, anchor_notes, ctx["note_url"])

    banner_html = _provenance_banner(prov, compact=(idx != 0)) if prov else ""
    # Раньше вступление (шапка файла) попадало в тело главы 1 и вырезалось
    # оттуда эвристикой collapse_intro/split_intro_blocks (потолок 700
    # символов/4 блока — источник несогласованности между файлами, см.
    # templates/provenance.py). Теперь шапка приходит явным полем
    # (prov["header_text"]), без эвристики и без риска утечь в тело.
    source_details_html = ""
    if idx == 0 and prov and prov["header_text"]:
        header_html = mdconv.render_body(prov["header_text"], ctx["resolve_link"], ctx["assets_base"], images_dir=ctx["images_dir"])
        source_details_html = f'<details class="src-details"><summary>Источник и детали</summary>{header_html}</details>'

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
  <div class="crumbs"><a href="{ctx["work_url"](work_meta["id"])}">{html.escape(work_title)}</a> · {"полный текст" if prov and prov["cls"] == "translation" else "пересказ"}</div>
  {banner_html}
  {nav_html}
  <div class="note-body fulltext-body">
    {source_details_html}
    {body_html}
  </div>
  {pager}
  {_FEEDBACK_LINK_HTML}
  {_COMMENTS_SECTION_HTML}
</article>
"""


def render_hub(hub_note, ctx):
    body_html = mdconv.render_body(hub_note["body"], ctx["resolve_link"], ctx["assets_base"], images_dir=ctx["images_dir"])
    downloads_html = ctx["downloads_widget_hub"](hub_note)

    # Шапка-карточка по референсу дизайн-обогащения (30.07.2026) — та же
    # тёмная «глава»-шапка, что у полных текстов (.chapter-hero), плюс пара
    # stat-tiles: заметок в links_out хаба и работ, из которых они взяты.
    # links_out хаба содержит не только атомарные заметки, но и ссылки на
    # другие карты — считаем только type == "atomic", иначе число «заметок»
    # завышено соседними хабами.
    by_id = ctx.get("by_id", {})
    linked_atomic = [
        by_id[lid] for lid in hub_note.get("links_out", [])
        if by_id.get(lid, {}).get("type") == "atomic"
    ]
    work_ids = {a["source_work_id"] for a in linked_atomic if a.get("source_work_id")}
    title = _display_title(hub_note["id"])

    return f"""
<article class="hub-page">
  <header class="chapter-hero">
    <div class="chapter-kicker"><span>КАРТА ОБЛАСТИ</span></div>
    <h1 class="chapter-title">{html.escape(title)}</h1>
    <div class="chapter-dashes"><span class="dash dash-bruise"></span><span class="dash dash-verdigris"></span></div>
  </header>
  <div class="crumbs"><a href="{ctx["site_base"]}/maps/">Все карты областей</a></div>
  <div class="stat-tiles">
    <div class="stat-tile stat-tile-accent"><span class="stat-num">{len(linked_atomic)}</span><span class="stat-label">заметок в карте</span></div>
    <div class="stat-tile"><span class="stat-num">{len(work_ids)}</span><span class="stat-label">работ</span></div>
  </div>
  <div class="note-body">
    {body_html}
  </div>
  {downloads_html}
  {_FEEDBACK_LINK_HTML}
  {_COMMENTS_SECTION_HTML}
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
    prov_by = ctx.get("fulltext_prov", {})

    def row(work, ft, base_url):
        prov = prov_by.get(ft["id"])
        chip = f'<span class="prov-chip prov-chip-row{" prov-chip-translation" if prov and prov["cls"] == "translation" else ""}">{html.escape(prov["label"])}</span>' if prov else ""
        return (
            f'<a class="row" href="{base_url}">'
            f'<span class="row-year">{html.escape((work["year"] if work else "") or "")}</span>'
            f'<span class="row-title">{html.escape(work["title"] if work else _display_title(ft["id"]))}</span>'
            f"{chip}</a>"
        )

    translations = [e for e in entries if prov_by.get(e[1]["id"], {}).get("cls") == "translation"]
    retellings = [e for e in entries if prov_by.get(e[1]["id"], {}).get("cls") != "translation"]

    sections = ""
    if translations:
        sections += (
            "<h2>Переводы с оригинала</h2>"
            f'<div class="rows">{"".join(row(*e) for e in translations)}</div>'
        )
    if retellings:
        sections += (
            "<h2>Пересказы и изложения</h2>"
            "<p class=\"work-meta\">Собраны из атомарных заметок или конспекта этого хранилища, "
            "не переведены построчно с оригинала — подробнее на странице каждого текста.</p>"
            f'<div class="rows">{"".join(row(*e) for e in retellings)}</div>'
        )

    return f"""
<article class="index-page">
  <h1 class="note-title">Полные тексты</h1>
  <p class="work-meta">Часть работ переведена с оригинала целиком, по главам; часть — пересказана
    или собрана из атомарных заметок этого хранилища. Какая есть какая — обозначено ниже
    и на странице каждого текста; подробнее — на странице «О проекте».</p>
  {sections}
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
    <p>Раздел «Полные тексты» — не всегда переводы. Часть работ переведена с
    оригинала целиком; часть — пересказана своими словами или собрана из
    атомарных заметок этого хранилища (в формате Тезис / Аргументы / Вывод —
    для больших теоретических трудов, или изложения по конспекту). Пересказ
    не выдаётся за перевод: на каждой такой странице сказано об этом прямо,
    рядом — ссылка на настоящий перевод там, где он есть в открытом доступе.</p>
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
    <button class="search-filter" data-type="перевод">Переводы</button>
    <button class="search-filter" data-type="пересказ">Пересказы</button>
    <button class="search-filter" data-type="карта">Карты</button>
  </div>
  <div class="search-results" id="searchResults"></div>
  <p class="search-empty" id="searchEmpty" hidden>Ничего не нашлось.</p>
</article>
<script type="module" src="{ctx["assets_base"]}/search.js?v={asset_v("search.js")}"></script>
"""


def render_my_notes(ctx):
    return f"""
<article class="mynotes-page">
  <h1 class="note-title" id="mynotesTitle">Мои заметки</h1>
  <p class="work-meta" id="mynotesIntro">Всё, что вы отметили при чтении, — закладки страниц, выделения, заметки с
    комментарием, — хранится у вас в браузере, а внутри Telegram ещё и синхронизируется между устройствами.</p>
  <div class="mynotes-empty" id="mynotesEmpty" hidden>Пока ничего нет — выделите текст на любой странице, чтобы отметить или прокомментировать его, или нажмите «В избранное» в шапке.</div>
  <div class="mynotes-list" id="mynotesList"></div>
</article>
<script src="{ctx["assets_base"]}/mynotes.js?v={asset_v("mynotes.js")}" defer></script>
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


def render_home_banner(ctx):
    # Баннер рендерится ВНЕ <main> (между шапкой и main, см. pre_main_html в
    # layout.page): main несёт overflow-x:hidden против горизонтального скролла,
    # а overflow режет и трансформированных потомков — любой трюк с расширением
    # баннера изнутри колонки (margin: calc(50% - 50vw), transform) оказывался
    # обрезан по ширине колонки на широких экранах. Снаружи main баннер — обычный
    # блок на всю ширину body, резать его некому и расширять нечего.
    return f"""
  <figure class="hero-banner">
    <img src="{ctx["assets_base"]}/hero-header.webp" alt="" width="1672" height="941" fetchpriority="high">
  </figure>"""


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
                ("/texts/", "Полные тексты", "Переводы и пересказы целиком, по главам"),
                ("/cases/", "Клинические случаи", "Ганс, Крыса, Шребер, Волк, Дора"),
                ("/maps/", "Карты областей", "Структурные заметки по темам"),
            ]
        )
        + f'<a class="card" href="{dreams_url}"><span class="card-title">Сны</span>'
        f'<span class="card-kicker">Заметки-разборы сновидений</span></a>'
    )

    return f"""
<article class="home-page">
  <section class="hero">
    <h1 class="hero-title">Фрейдариум</h1>
    <p>Атомарная база работ Зигмунда Фрейда — {stats["atomic"]} заметок,
      {stats["works"]} работ, полные тексты, связи между мыслями.</p>
    <a class="btn btn-primary" id="heroPrimaryBtn" href="{sb}/n/random/">Случайная заметка</a>
    <a class="btn" href="{sb}/search/">Поиск</a>
    <a class="see-all" id="heroRandomLink" href="{sb}/n/random/" hidden>Или откройте случайную заметку →</a>
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
