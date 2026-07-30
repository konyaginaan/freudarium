"""
Мини-конвертер тела заметки (markdown-подобный текст экспорта Фрейда) в HTML.

Не универсальный markdown — заточен именно под то, что реально встречается
в теле заметок ~/freud-export/data/notes.json (см. подготовку 12): заголовки
##/###, **жирный**, *курсив*, `код`, списки - и 1., цитаты >, таблицы |,
разделитель ---, обычные markdown-ссылки [текст](url), вики-ссылки [[id]] и
[[id|алиас]], эмбеды ![[файл.ext]], строки-метаполя «Ключ:: значение», строки
«→ [[...]]» (переходы — не рендерятся в теле, уже показаны отдельной панелью
связей) и хвостовые block-id « ^pN» у абзацев полных текстов.
"""
import html
import re

MDLINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
EMBED_RE = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
ARROW_LINE_RE = re.compile(r"^→\s*\[\[")
META_LINE_RE = re.compile(r"^([^\n:]{1,40})::\s*(.*)$")
BLOCKID_TAIL_RE = re.compile(r"\s*\^([a-zA-Z0-9]+)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BOLD_LABEL_START_RE = re.compile(r"^\*\*[^*\n]+\.\*\*")
# «**Метка** → [[a]], [[b]], ...» — пункт карты области со списком заметок темы
STATION_LINE_RE = re.compile(r"^(.*?)→\s*((?:\[\[[^\]]+\]\](?:,\s*)?)+)\s*$")

_INLINE_RE = re.compile(
    r"(?P<embed>!\[\[[^\]]+\]\])"
    r"|(?P<wiki>\[\[[^\]]+\]\])"
    r"|(?P<mdlink>\[[^\]]+\]\(https?://[^\s)]+\))"
    r"|(?P<bold>\*\*.+?\*\*)"
    r"|(?P<italic>(?<!\*)\*[^*\n]+\*(?!\*))"
    r"|(?P<code>`[^`]+`)"
    r"|(?P<url>https?://[^\s<]+)"
)


def _inline(text: str, resolve_link, asset_base: str) -> str:
    """Инлайновая разметка внутри текста одного блока (text — «сырой», неэкранированный)."""
    out = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        if m.group("embed"):
            em = EMBED_RE.match(m.group("embed"))
            fname = em.group(1).strip()
            alt = html.escape((em.group(2) or fname).strip())
            out.append(
                f'<img class="note-embed" src="{asset_base}/images/{html.escape(fname)}" alt="{alt}" loading="lazy">'
            )
        elif m.group("wiki"):
            wm = WIKILINK_RE.match(m.group("wiki"))
            target = wm.group(1).strip()
            alias = (wm.group(2) or target).strip()
            url = resolve_link(target)
            if url:
                out.append(f'<a href="{html.escape(url)}">{html.escape(alias)}</a>')
            else:
                out.append(f'<span class="link-broken">{html.escape(alias)}</span>')
        elif m.group("mdlink"):
            lm = MDLINK_RE.match(m.group("mdlink"))
            out.append(
                f'<a href="{html.escape(lm.group(2))}" target="_blank" rel="noopener">{html.escape(lm.group(1))}</a>'
            )
        elif m.group("bold"):
            out.append(f"<strong>{html.escape(m.group('bold')[2:-2])}</strong>")
        elif m.group("italic"):
            out.append(f"<em>{html.escape(m.group('italic')[1:-1])}</em>")
        elif m.group("code"):
            out.append(f"<code>{html.escape(m.group('code')[1:-1])}</code>")
        elif m.group("url"):
            u = m.group("url")
            out.append(f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(u)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def split_intro_blocks(body: str):
    """
    Отделяет ведущие «служебные» блоки (Источник/Оригинал/Конспект/цитата
    архивного экземпляра и т.п. — то, что стоит в самом начале конспектов,
    источников и полных текстов до настоящего содержания) от остального
    текста. Границей считается первый блок, начинающийся с заголовка или
    с жирной метки вида «**Тезис.**» — оттуда начинается собственно текст.
    Возвращает (intro_или_None, rest) — intro is None, если коллапсировать нечего.
    """
    blocks = re.split(r"\n\s*\n", body.strip("\n "))
    i = 0
    while i < len(blocks):
        first_line = blocks[i].strip().split("\n")[0]
        if HEADING_RE.match(first_line) or BOLD_LABEL_START_RE.match(first_line):
            break
        i += 1
    if i == 0:
        return None, body
    return "\n\n".join(blocks[:i]), "\n\n".join(blocks[i:])


def render_body(body: str, resolve_link, asset_base: str = "", collapse_intro: bool = False) -> str:
    """
    resolve_link(id) -> url заметки на сайте, или None (тогда рендерится
    как обычный текст без ссылки — внешние/битые ссылки экспорта).
    asset_base — префикс пути к /assets (для эмбедов-картинок).
    collapse_intro — свернуть ведущий служебный блок (см. split_intro_blocks)
    в <details>, закрытый по умолчанию (для конспектов/источников/полных текстов).
    Возвращает готовый HTML (без обёртки <article>).
    """
    if collapse_intro:
        intro, rest = split_intro_blocks(body)
        if intro:
            intro_html = _render_blocks(intro, resolve_link, asset_base)
            rest_html = _render_blocks(rest, resolve_link, asset_base)
            return (
                '<details class="src-details"><summary>Источник и детали</summary>'
                f"{intro_html}</details>{rest_html}"
            )
    return _render_blocks(body, resolve_link, asset_base)


def _render_blocks(body: str, resolve_link, asset_base: str = "") -> str:
    blocks = re.split(r"\n\s*\n", body.strip("\n "))
    html_parts = []
    list_buffer = None  # ('ul'|'ol', [items])

    def flush_list():
        nonlocal list_buffer
        if list_buffer:
            tag, items = list_buffer
            html_parts.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            list_buffer = None

    for block in blocks:
        lines = block.split("\n")
        stripped_lines = [l.strip() for l in lines]
        if not any(stripped_lines):
            continue

        # Блок-цепочка «→ [[...]]» — переходы, уже показаны отдельной панелью.
        if all((not l) or ARROW_LINE_RE.match(l) for l in stripped_lines):
            continue

        # Заголовок
        hm = HEADING_RE.match(stripped_lines[0])
        if hm and len(stripped_lines) == 1:
            flush_list()
            level = min(len(hm.group(1)) + 1, 6)  # заметка внутри страницы — на уровень ниже
            html_parts.append(f"<h{level}>{_inline(hm.group(2), resolve_link, asset_base)}</h{level}>")
            continue

        # Разделитель
        if stripped_lines[0] in ("---", "***", "___") and len(stripped_lines) == 1:
            flush_list()
            html_parts.append("<hr>")
            continue

        # Блок метаполей «Ключ:: значение» (несколько строк подряд)
        if all(META_LINE_RE.match(l) for l in stripped_lines if l):
            flush_list()
            rows = []
            for l in stripped_lines:
                if not l:
                    continue
                mm = META_LINE_RE.match(l)
                rows.append(
                    f"<dt>{html.escape(mm.group(1))}</dt><dd>{_inline(mm.group(2), resolve_link, asset_base)}</dd>"
                )
            html_parts.append(f'<dl class="note-meta">{"".join(rows)}</dl>')
            continue

        # Цитата
        if all((not l) or l.startswith(">") for l in stripped_lines):
            flush_list()
            text = " ".join(l[1:].strip() for l in stripped_lines if l)
            html_parts.append(f"<blockquote>{_inline(text, resolve_link, asset_base)}</blockquote>")
            continue

        # Таблица (заголовок + строка-разделитель + строки данных)
        if (
            stripped_lines[0].startswith("|")
            and len(stripped_lines) >= 2
            and set(stripped_lines[1].replace("|", "").replace(":", "").strip()) <= {"-", " "}
        ):
            flush_list()

            def cells(row):
                return [c.strip() for c in row.strip("|").split("|")]

            head = cells(stripped_lines[0])
            body_rows = [cells(r) for r in stripped_lines[2:] if r.strip()]
            thead = "".join(f"<th>{_inline(c, resolve_link, asset_base)}</th>" for c in head)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{_inline(c, resolve_link, asset_base)}</td>" for c in row) + "</tr>"
                for row in body_rows
            )
            html_parts.append(
                f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead>'
                f"<tbody>{tbody}</tbody></table></div>"
            )
            continue

        # Списки
        if all((not l) or re.match(r"^[-*]\s+", l) for l in stripped_lines):
            if not (list_buffer and list_buffer[0] == "ul"):
                flush_list()
                list_buffer = ("ul", [])
            for l in stripped_lines:
                if not l:
                    continue
                item_text = re.sub(r"^[-*]\s+", "", l)
                # «**Тема** → [[a]], [[b]], ...» (карты областей) — заметки темы
                # отдельными пунктами вложенного списка, а не одной строкой через запятую
                sm = STATION_LINE_RE.match(item_text)
                if sm and sm.group(2).count("[[") > 1:
                    label_html = _inline(sm.group(1).strip(), resolve_link, asset_base)
                    sub_items = []
                    for wm in WIKILINK_RE.finditer(sm.group(2)):
                        target = wm.group(1).strip()
                        alias = (wm.group(2) or target).strip()
                        url = resolve_link(target)
                        if url:
                            sub_items.append(f'<li><a href="{html.escape(url)}">{html.escape(alias)}</a></li>')
                        else:
                            sub_items.append(f'<li><span class="link-broken">{html.escape(alias)}</span></li>')
                    list_buffer[1].append(
                        f'{label_html}<ul class="hub-links">{"".join(sub_items)}</ul>'
                    )
                else:
                    list_buffer[1].append(_inline(item_text, resolve_link, asset_base))
            continue
        if all((not l) or re.match(r"^\d+\.\s+", l) for l in stripped_lines):
            if not (list_buffer and list_buffer[0] == "ol"):
                flush_list()
                list_buffer = ("ol", [])
            for l in stripped_lines:
                if l:
                    list_buffer[1].append(_inline(re.sub(r"^\d+\.\s+", "", l), resolve_link, asset_base))
            continue

        flush_list()

        # Одиночный эмбед на всю строку — отдельный визуальный блок (шире текста).
        if len(stripped_lines) == 1:
            em = EMBED_RE.match(stripped_lines[0])
            if em:
                fname = em.group(1).strip()
                alt = html.escape((em.group(2) or fname).strip())
                html_parts.append(
                    f'<figure class="note-figure"><img src="{asset_base}/images/{html.escape(fname)}" '
                    f'alt="{alt}" loading="lazy"></figure>'
                )
                continue

        # Обычный абзац; ищем хвостовой block-id ^pN у полных текстов.
        text = " ".join(l for l in lines if l.strip())
        anchor_id = None
        bm = BLOCKID_TAIL_RE.search(text)
        if bm:
            anchor_id = bm.group(1)
            text = text[: bm.start()]
        attr = f' id="{html.escape(anchor_id)}"' if anchor_id else ""
        html_parts.append(f"<p{attr}>{_inline(text, resolve_link, asset_base)}</p>")

    flush_list()
    return "\n".join(html_parts)


def strip_arrows_and_field_lines(body: str) -> str:
    """Для превью/сниппетов: убрать → -строки и обычные ##-заголовки, вернуть чистый текст."""
    lines = []
    for line in body.split("\n"):
        s = line.strip()
        if not s or ARROW_LINE_RE.match(s) or HEADING_RE.match(s) or META_LINE_RE.match(s):
            continue
        lines.append(s)
    return " ".join(lines)
