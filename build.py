#!/usr/bin/env python3
"""
Генератор сайта «Фрейдариум» из ~/freud-export/data/ + Фрейд/Изображения/.
Выход — docs/ (публикуется через GitHub Pages). Без внешних зависимостей
(кроме опционального `npx pagefind` для поиска на этапе 3).

Запуск:  python3 build.py
Базовый префикс пути (для деплоя без домена, напр. /freud) — переменной
окружения:  SITE_BASE=/freud python3 build.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from templates import downloads, layout, mdconv, pages, provenance
from templates import slugs as slugmod

PROJECT_DIR = Path(__file__).parent
VAULT_DIR = Path.home() / "Downloads" / "Обсидиан" / "купс группа" / "Фрейд"
EXPORT_DIR = Path.home() / "freud-export" / "data"
IMAGES_DIR = VAULT_DIR / "Изображения"
OUT_DIR = PROJECT_DIR / "docs"
SLUGS_FILE = PROJECT_DIR / "slugs.json"

SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")
TAG_MIN_COUNT = 3
PUBLISHED_TYPES = {"atomic", "conspect", "full_text", "hub"}

CHAPTER_SPLIT_RE = re.compile(r"^(#{1,2})\s+(.*)$", re.M)
ANCHOR_RE = re.compile(r"\^([a-zA-Z0-9]+)")


def su(path: str) -> str:
    """site url: добавляет SITE_BASE к абсолютному пути."""
    return f"{SITE_BASE}{path}"


def write_text(rel_path: str, content: str):
    p = OUT_DIR / rel_path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def write_bytes(rel_path: str, data: bytes):
    p = OUT_DIR / rel_path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def split_chapters(body: str):
    matches = list(CHAPTER_SPLIT_RE.finditer(body))
    if not matches:
        return [{"title": None, "body": body}]
    chapters = []
    intro = body[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chapters.append({"title": m.group(2).strip(), "body": body[start:end].strip("\n ")})
    if intro:
        chapters[0]["body"] = intro + "\n\n" + chapters[0]["body"]
    return chapters


def main():
    notes = json.loads((EXPORT_DIR / "notes.json").read_text(encoding="utf-8"))
    works = json.loads((EXPORT_DIR / "works.json").read_text(encoding="utf-8"))
    tags_index = json.loads((EXPORT_DIR / "tags.json").read_text(encoding="utf-8"))

    by_id = {n["id"]: n for n in notes}
    works_by_id = {w["id"]: w for w in works}
    backlinks_by_id = {n["id"]: n.get("backlinks", []) for n in notes}
    asset_files = {p.name for p in IMAGES_DIR.glob("*.*")} if IMAGES_DIR.exists() else set()

    # ── заморозка slug'ов (URL не меняются при переименовании в Obsidian) ──
    frozen = json.loads(SLUGS_FILE.read_text(encoding="utf-8")) if SLUGS_FILE.exists() else {}
    slug_map = slugmod.freeze_slugs(notes, frozen)
    SLUGS_FILE.write_text(
        json.dumps(slug_map, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )

    def slug_of(nid):
        return slug_map.get(nid)

    # ── главы полных текстов + провенанс (перевод/пересказ/…, см.
    # templates/provenance.py) ──
    # ВАЖНО: n["body"] не мутируется — его читает downloads.reconstruct_md
    # ниже (docs/dl/f/<slug>.md должен остаться точной копией файла
    # хранилища). Главы считаются от provenance["body_rest"] (тело БЕЗ
    # шапки) — так шапка не запекается в тело главы 1, и её больше не нужно
    # вырезать эвристикой collapse_intro/split_intro_blocks на стороне
    # рендера (см. templates/mdconv.py).
    fulltext_chapters = {}
    fulltext_anchor_chapter = {}
    fulltext_prov = {}
    _prov_counts = {}
    for n in notes:
        if n["type"] == "full_text":
            prov = provenance.describe(n["id"], n["body"])
            fulltext_prov[n["id"]] = prov
            _prov_counts[prov["cls"]] = _prov_counts.get(prov["cls"], 0) + 1
            chs = split_chapters(prov["body_rest"])
            fulltext_chapters[n["id"]] = chs
            amap = {}
            for idx, ch in enumerate(chs):
                for am in ANCHOR_RE.finditer(ch["body"]):
                    amap.setdefault(am.group(1), idx)
            fulltext_anchor_chapter[n["id"]] = amap
    # Молчаливая потеря класса/текста здесь — тот же класс бага, что уже
    # ломал сборку 29.07 (см. план) — печатаем счётчики и требуем сумму 47,
    # чтобы будущая правка формулировки в хранилище не прошла незамеченной.
    _prov_total = sum(_prov_counts.values())
    print(f"[provenance] {_prov_counts} (всего {_prov_total})")
    assert _prov_total == len(fulltext_chapters), (
        f"provenance: {_prov_total} классифицировано, но {len(fulltext_chapters)} full_text-заметок — "
        "кто-то не попал в fulltext_prov"
    )

    def fulltext_base_url(nid):
        return su(f"/f/{slug_of(nid)}/")

    def fulltext_anchor_url(nid, anchor):
        chs = fulltext_chapters.get(nid)
        if chs is None:
            return None
        base = fulltext_base_url(nid)
        if anchor is None:
            return base
        idx = fulltext_anchor_chapter.get(nid, {}).get(anchor, 0)
        return (base if idx == 0 else f"{base}{idx + 1}/") + f"#{anchor}"

    # соответствие работа (conspect id) → её full_text id, по имени работы
    work_to_fulltext = {}
    for w in works:
        expect = f'{w["title"]} — полный текст, {w["author"] or "Фрейд"}, {w["year"]}'
        if expect in fulltext_chapters:
            work_to_fulltext[w["id"]] = expect

    def fulltext_first_url(work_id):
        fid = work_to_fulltext.get(work_id)
        return fulltext_base_url(fid) if fid else None

    def note_url(nid):
        n = by_id.get(nid)
        if not n or n["type"] not in PUBLISHED_TYPES:
            return None
        s = slug_of(nid)
        if n["type"] == "atomic":
            return su(f"/n/{s}/")
        if n["type"] == "conspect":
            return su(f"/w/{s}/")
        if n["type"] == "hub":
            return su(f"/m/{s}/")
        if n["type"] == "full_text":
            return fulltext_base_url(nid)
        return None

    def work_url(conspect_id):
        return note_url(conspect_id)

    def hub_url(hub_id):
        return note_url(hub_id)

    # ── теги: публикуем только с частотой >= TAG_MIN_COUNT среди
    # опубликованных типов заметок ──
    tag_seen_slugs = set()
    tag_slug = {}
    tag_notes = {}
    for tag, info in tags_index.items():
        member_ids = [nid for nid in info["note_ids"] if by_id.get(nid, {}).get("type") in PUBLISHED_TYPES]
        if len(member_ids) < TAG_MIN_COUNT:
            continue
        tag_notes[tag] = member_ids
        tag_slug[tag] = slugmod.slugify(tag, tag_seen_slugs)

    def tag_url(tag):
        if tag not in tag_slug:
            return None
        return su(f"/t/{tag_slug[tag]}/")

    def resolve_link(target_id):
        return note_url(target_id)

    assets_base = su("/assets")

    def downloads_widget(note):
        import html as html_mod
        s = slug_of(note["id"])
        prefix = {"atomic": "n", "conspect": "w", "hub": "m", "full_text": "f"}[note["type"]]
        md_url = su(f"/dl/{prefix}/{s}.md")
        title = note["id"]
        html = (
            f'<section class="rel-block downloads">'
            f'<button class="btn" data-open-download'
            f' data-dl-md-url="{md_url}"'
            f' data-dl-note-id="{html_mod.escape(note["id"])}"'
            f' data-dl-title="{html_mod.escape(title)}">Скачать</button>'
            f"</section>"
        )
        return html

    def downloads_widget_work(work):
        s = slug_of(work["id"])
        zip_url = su(f"/dl/w/{s}.zip")
        return (
            f'<section class="rel-block downloads">'
            f'<a class="btn" href="{zip_url}" download>Скачать всю работу (.zip)</a>'
            f"</section>"
        )

    def downloads_widget_hub(hub_note):
        # Раньше — прямая ссылка на статический dl/m/*.zip; карта области
        # теперь платная (см. render_hub), поэтому кнопка ведёт не на файл,
        # а через access.js/hub-gate.js: у оплативших — запрос в воркер за
        # текстом карты (GET /hub-content?kind=md), у остальных — шторка
        # «Купить».
        import html as html_mod
        s = slug_of(hub_note["id"])
        return (
            f'<section class="rel-block downloads">'
            f'<button class="btn btn-primary" data-hub-download data-hub-slug="{html_mod.escape(s)}">'
            f"Скачать текст карты</button>"
            f"</section>"
        )

    ctx = {
        "resolve_link": resolve_link,
        "note_url": note_url,
        "work_url": work_url,
        "hub_url": hub_url,
        "tag_url": tag_url,
        "fulltext_anchor_url": fulltext_anchor_url,
        "fulltext_first_url": fulltext_first_url,
        "fulltext_prov": fulltext_prov,
        "work_to_fulltext": work_to_fulltext,
        "works_by_id": works_by_id,
        "backlinks_by_id": backlinks_by_id,
        "site_base": SITE_BASE,
        "assets_base": assets_base,
        "images_dir": IMAGES_DIR,
        "by_id": by_id,
        "slug_of": slug_of,
        "downloads_widget": downloads_widget,
        "downloads_widget_work": downloads_widget_work,
        "downloads_widget_hub": downloads_widget_hub,
    }

    def snippet(note, n=140):
        text = mdconv.strip_arrows_and_field_lines(note["body"])
        return (text[:n] + "…") if len(text) > n else text

    def emit_page(url, title, description, body_html, back_href=None, back_label="Назад",
                  pagefind_filters=None, pagefind_ignore=False, pre_main_html=""):
        rel = url[len(SITE_BASE):] if SITE_BASE and url.startswith(SITE_BASE) else url
        html_out = layout.page(
            title=title,
            description=description,
            body_html=body_html,
            site_base=SITE_BASE,
            canonical_path=url,
            back_href=back_href,
            back_label=back_label,
            pagefind_filters=pagefind_filters,
            pagefind_ignore=pagefind_ignore,
            pre_main_html=pre_main_html,
        )
        write_text(rel.rstrip("/") + "/index.html" if not rel.endswith(".html") else rel, html_out)

    # обратная карта: (full_text_id, anchor) -> [note_id, ...] — для переходов
    # «из полного текста — в заметки», см. templates/pages._inject_note_markers
    fulltext_anchor_notes = {}
    for n in notes:
        if n["type"] != "atomic":
            continue
        for ref in n.get("full_text_refs") or []:
            if ref.get("anchor"):
                fulltext_anchor_notes.setdefault(ref["target"], {}).setdefault(ref["anchor"], []).append(n["id"])

    # пять клинических случаев (закрытый список, см. память freud-canon-progress-2026-07)
    CASE_NAMES = ["Маленький Ганс", "Человек-Крыса", "Шребер", "Человек-Волк", "Дора"]
    cases = [(w, by_id[w["id"]], "") for w in works if w["title"] in CASE_NAMES]

    # ══════════════ страницы заметок ══════════════
    for n in notes:
        if n["type"] not in PUBLISHED_TYPES:
            continue
        url = note_url(n["id"])
        if not url:
            continue

        if n["type"] == "atomic":
            back_href = work_url(n["source_work_id"]) if n.get("source_work_id") else su("/")
            body_html = pages.render_note(n, ctx)
            work = works_by_id.get(n.get("source_work_id"))
            pf_filters = {"type": "заметка"}
            if work:
                pf_filters["work"] = work["title"]
            emit_page(url, n["id"], snippet(n), body_html, back_href=back_href, pagefind_filters=pf_filters)

        elif n["type"] == "conspect":
            work = works_by_id.get(n["id"])
            if not work:
                continue
            atomic_notes = sorted(
                (a for a in notes if a["type"] == "atomic" and a.get("source_work_id") == n["id"]),
                key=lambda a: a["id"],
            )
            source_note = None
            if work.get("source_note_id"):
                source_note = by_id.get(work["source_note_id"])
            body_html = pages.render_work(n, work, atomic_notes, source_note, ctx)
            emit_page(url, work["title"], snippet(n), body_html, back_href=su("/works/"),
                      pagefind_filters={"type": "работа", "work": work["title"]})

        elif n["type"] == "hub":
            body_html = pages.render_hub(n, ctx)
            # snippet(n) — обычно первые ~140 символов тела заметки для
            # <meta description> (SEO); карта области платная, а
            # description — открытый текст HTML-страницы, значит нельзя
            # брать снипет из настоящего тела, иначе платный текст утечёт
            # туда мимо всей проверки доступа.
            hub_description = "Карта области «Фрейдариума» — платный доступ."
            emit_page(url, pages._display_title(n["id"]), hub_description, body_html, back_href=su("/maps/"),
                      pagefind_filters={"type": "карта"})

        elif n["type"] == "full_text":
            chs = fulltext_chapters[n["id"]]
            work = next((w for w in works if work_to_fulltext.get(w["id"]) == n["id"]), None)
            work_title = work["title"] if work else n["id"]
            base_url = fulltext_base_url(n["id"])
            anchor_notes = fulltext_anchor_notes.get(n["id"], {})
            prov = fulltext_prov[n["id"]]
            for idx in range(len(chs)):
                page_url = base_url if idx == 0 else f"{base_url}{idx + 1}/"
                body_html = pages.render_fulltext_chapter(work_title, work, chs, idx, ctx, base_url, anchor_notes, prov)
                back_href = work_url(work["id"]) if work else su("/")
                emit_page(
                    page_url,
                    f"{work_title} — {chs[idx]['title'] or prov['label']}",
                    "",
                    body_html,
                    back_href=back_href,
                    pagefind_filters={"type": pages.PROV_SEARCH_TYPE[prov["cls"]], "work": work_title},
                )

    # ══════════════ теги ══════════════
    for tag, member_ids in tag_notes.items():
        member_notes = sorted((by_id[i] for i in member_ids if by_id[i]["type"] == "atomic"), key=lambda a: a["id"])
        if not member_notes:
            continue
        body_html = pages.render_tag(tag, member_notes, ctx)
        emit_page(tag_url(tag), f"#{tag}", f"{len(member_notes)} заметок с темой «{tag}»", body_html,
                  back_href=su("/tags/"), pagefind_ignore=True)

    # ══════════════ клинические случаи, полные тексты, о проекте, поиск ══════════════
    cases_html = pages.render_cases(cases, ctx)
    emit_page(su("/cases/"), "Клинические случаи", "Пять историй болезни Фрейда", cases_html,
              back_href=su("/"), pagefind_ignore=True)

    text_entries = []
    for w in works:
        fid = work_to_fulltext.get(w["id"])
        if fid:
            text_entries.append((w, by_id[fid], fulltext_base_url(fid)))
    text_entries.sort(key=lambda e: (e[0]["year"] or "9999"))
    texts_html = pages.render_texts(text_entries, ctx)
    emit_page(su("/texts/"), "Полные тексты", "Работы Фрейда целиком, по главам", texts_html,
              back_href=su("/"), pagefind_ignore=True)

    about_html = pages.render_about(ctx)
    emit_page(su("/about/"), "О проекте", "", about_html, back_href=su("/"), pagefind_ignore=True)

    privacy_html = pages.render_privacy(ctx)
    emit_page(
        su("/privacy/"), "Политика обработки персональных данных", "", privacy_html,
        back_href=su("/"), pagefind_ignore=True,
    )

    search_html = pages.render_search(ctx)
    emit_page(su("/search/"), "Поиск", "", search_html, back_href=su("/"), pagefind_ignore=True)

    mynotes_html = pages.render_my_notes(ctx)
    emit_page(su("/notes/"), "Мои заметки", "", mynotes_html, back_href=su("/"), pagefind_ignore=True)

    # ══════════════ индексы: works/, tags/, maps/ ══════════════
    def simple_list_page(url, title, rows_html, back_href):
        body = f'<article class="index-page"><h1 class="note-title">{title}</h1>{rows_html}</article>'
        emit_page(url, title, "", body, back_href=back_href)

    works_rows = "".join(
        f'<a class="row" href="{work_url(w["id"])}"><span class="row-year">{w["year"] or ""}</span>'
        f'<span class="row-title">{w["title"]}</span><span class="row-count">{w["atomic_note_count"]}</span></a>'
        for w in sorted(works, key=lambda w: (w["year"] or "9999"))
    )
    simple_list_page(su("/works/"), "Все работы", f'<div class="rows">{works_rows}</div>', su("/"))

    hubs = [n for n in notes if n["type"] == "hub"]
    hub_cards = "".join(
        f'<a class="card card-sm" href="{hub_url(h["id"])}"><span class="card-title">{pages._display_title(h["id"])}</span></a>'
        for h in sorted(hubs, key=lambda h: h["id"])
    )
    simple_list_page(su("/maps/"), "Карты областей", f'<div class="card-grid">{hub_cards}</div>', su("/"))

    # ── автоссылки понятий в тексте заметок на карты областей (фидбек
    # пользователя 31.07.2026): «невроз», «сексуальность» и т.п. в прозе
    # должны вести на соответствующую карту. Ключ строим из СОБСТВЕННЫХ
    # тегов хаба, не из заголовка — тот часто многословный и почти
    # никогда не встречается в прозе дословно. Берём только теги,
    # размеченные ровно на ОДНОМ хабе — иначе неясно, куда вести (у
    # «религия» и «метапсихология» в корпусе по два хаба — пропускаем).
    # Дефис в теге («невроз-навязчивости») — склейка для слага, в прозе
    # слова идут через пробел, возвращаем как было.
    _HUB_KEYWORD_GENERIC_TAGS = {"концепт", "Фрейд", "синтез", "хаб", "ключевая-мысль"}
    # Слишком общеупотребимые вне психоаналитического контекста слова —
    # риск ложных срабатываний на неродственных упоминаниях (проверено на
    # корпусе 31.07.2026: это САМЫЕ частые обычные слова среди тегов-
    # кандидатов, не специфичные именно для этой карты).
    _HUB_KEYWORD_TOO_GENERIC = {"техника", "культура", "экономия", "удовольствие", "сны"}
    tag_to_hub_ids: dict[str, list[str]] = {}
    for h in hubs:
        for t in h.get("tags") or []:
            if t in _HUB_KEYWORD_GENERIC_TAGS:
                continue
            tag_to_hub_ids.setdefault(t, []).append(h["id"])
    hub_keywords: dict[str, str] = {}
    for t, hub_ids in tag_to_hub_ids.items():
        if len(hub_ids) != 1:
            continue
        phrase = t.replace("-", " ")
        if phrase in _HUB_KEYWORD_TOO_GENERIC:
            continue
        hub_keywords[phrase] = hub_url(hub_ids[0])
    write_text(
        "assets/hub-keywords.js",
        "window.__HUB_KEYWORDS__=" + json.dumps(hub_keywords, ensure_ascii=False) + ";",
    )

    tags_sorted = sorted(tag_notes.items(), key=lambda kv: -len(kv[1]))
    tag_rows = "".join(
        f'<a class="row" href="{tag_url(t)}"><span class="row-title">#{t}</span>'
        f'<span class="row-count">{len(ids)}</span></a>'
        for t, ids in tags_sorted
    )
    tag_filter_html = (
        '<input type="search" id="tagFilterInput" class="tag-filter-input" '
        'placeholder="Найти тег…" aria-label="Найти тег">'
    )
    simple_list_page(su("/tags/"), "Все теги", f'{tag_filter_html}<div class="rows" id="tagRows">{tag_rows}</div>', su("/"))

    # ══════════════ главная ══════════════
    top_tags = [t for t, _ in tags_sorted if t not in ("Фрейд", "концепт")][:24]
    stats = {
        "atomic": sum(1 for n in notes if n["type"] == "atomic"),
        "works": len(works),
    }
    home_html = pages.render_home(works, hubs, top_tags, stats, ctx)
    emit_page(su("/"), "Фрейдариум", "Атомарная база работ Зигмунда Фрейда", home_html,
              pre_main_html=pages.render_home_banner(ctx))

    # ══════════════ 404 ══════════════
    # Без этого файла GitHub Pages отдаёт свою собственную заглушку — совсем
    # без нашей шапки/меню/кнопки «назад» (и с CSP, блокирующим любой JS), так
    # что уйти с неё можно было только перезапуском приложения. 404.html в
    # корне публикуемой папки — стандартный способ GitHub Pages подменить эту
    # заглушку своей: тот же layout, что и у всех остальных страниц.
    notfound_html = f"""
<article class="notfound-page">
  <h1 class="note-title">Страница не найдена</h1>
  <p class="work-meta">Такой страницы нет — ссылка могла устареть или содержать опечатку.</p>
  <a class="btn btn-primary" href="{su("/")}">На главную</a>
  <a class="btn" href="{su("/search/")}">Поиск</a>
</article>
"""
    emit_page(su("/404.html"), "Страница не найдена", "", notfound_html, back_href=su("/"))

    # ══════════════ резервный индекс поиска ══════════════
    # На случай, если pagefind (WASM + Web Worker) не запустится в вебвью
    # Telegram — лёгкий JSON по заголовкам/тегам/работам, простой substring-
    # поиск на клиенте без воркеров и WASM, см. assets/search.js.
    # full_text не входит — его метка «перевод»/«пересказ» решается по
    # provenance (см. ветку ниже), одно значение на все full_text не годится.
    TYPE_LABEL_RU = {"atomic": "заметка", "conspect": "работа", "hub": "карта"}
    search_index = []
    for n in notes:
        if n["type"] not in PUBLISHED_TYPES:
            continue
        u = note_url(n["id"])
        if not u:
            continue
        title = pages._display_title(n["id"]) if n["type"] == "hub" else (
            works_by_id[n["id"]]["title"] if n["type"] == "conspect" and n["id"] in works_by_id else n["id"]
        )
        work = works_by_id.get(n.get("source_work_id"))
        if n["type"] == "full_text":
            type_label = pages.PROV_SEARCH_TYPE[fulltext_prov[n["id"]]["cls"]]
        else:
            type_label = TYPE_LABEL_RU.get(n["type"], n["type"])
        search_index.append({
            "title": title,
            "url": u,
            "type": type_label,
            "work": work["title"] if work else None,
            "tags": n.get("tags") or [],
        })
    write_text("assets/search-index.json", json.dumps(search_index, ensure_ascii=False))

    # ══════════════ случайная заметка ══════════════
    random_ids = [n["id"] for n in notes if n["type"] == "atomic"]
    random_urls = [note_url(i) for i in random_ids]
    write_text(
        "assets/random-urls.json",
        json.dumps(random_urls, ensure_ascii=False),
    )
    random_html = (
        '<article class="note-page"><p>Выбираем случайную заметку…</p></article>'
        f'<script src="{assets_base}/random.js?v={layout.asset_v("random.js")}"></script>'
    )
    emit_page(su("/n/random/"), "Случайная заметка", "", random_html, back_href=su("/"))

    # ══════════════ скачивание: .md на заметку ══════════════
    prefix_by_type = {"atomic": "n", "conspect": "w", "hub": "m", "full_text": "f"}

    # Карта области (type=="hub") — платный контент (см. render_hub):
    # её .md не публикуется статически, тело живёт только в HUB_CONTENT_KV
    # воркера (наполняется push_hubs.py) и отдаётся авторизованным запросом.
    def dl_url(nid):
        n = by_id.get(nid)
        if not n or n["type"] not in PUBLISHED_TYPES or n["type"] == "hub":
            return None
        return su(f"/dl/{prefix_by_type[n['type']]}/{slug_of(nid)}.md")

    for n in notes:
        if n["type"] not in PUBLISHED_TYPES or n["type"] == "hub":
            continue
        s = slug_of(n["id"])
        prefix = prefix_by_type[n["type"]]
        write_text(f"dl/{prefix}/{s}.md", downloads.reconstruct_md(n))

    # «Скачать с окружением» (app.js): заметка + links_out + backlinks,
    # список файлов на клиента — сам zip собирается в браузере.
    for n in notes:
        if n["type"] != "atomic":
            continue
        related_ids = [n["id"]] + [i for i in n["links_out"] if i != n["id"]] + [
            i for i in backlinks_by_id.get(n["id"], []) if i != n["id"]
        ]
        seen = set()
        files = []
        for rid in related_ids:
            if rid in seen:
                continue
            seen.add(rid)
            url = dl_url(rid)
            if url:
                files.append({"name": f"{rid}.md", "url": url})
        write_text(
            f"assets/related/{n['id']}.json",
            json.dumps({"files": files}, ensure_ascii=False),
        )

    # ── zip на работу целиком ──
    for w in works:
        conspect = by_id.get(w["id"])
        if not conspect:
            continue
        entries = {f"{w['id']}.md": downloads.reconstruct_md(conspect).encode("utf-8")}
        if w.get("source_note_id") and by_id.get(w["source_note_id"]):
            sn = by_id[w["source_note_id"]]
            entries[f"{sn['id']}.md"] = downloads.reconstruct_md(sn).encode("utf-8")
        fid = work_to_fulltext.get(w["id"])
        if fid:
            entries[f"{by_id[fid]['id']}.md"] = downloads.reconstruct_md(by_id[fid]).encode("utf-8")
        images_needed = set()
        for a in notes:
            if a["type"] == "atomic" and a.get("source_work_id") == w["id"]:
                entries[f"{a['id']}.md"] = downloads.reconstruct_md(a).encode("utf-8")
                images_needed.update(a.get("embeds", []))
        for img in images_needed:
            fp = IMAGES_DIR / img
            if fp.exists():
                entries[f"Изображения/{img}"] = fp.read_bytes()
        write_bytes(f"dl/w/{slug_of(w['id'])}.zip", downloads.build_zip(entries))

    # Карты областей больше не бандлятся в zip (см. пометку у dl_url выше) —
    # их собственный текст доступен для скачивания только после оплаты,
    # через воркер (assets/hub-gate.js → GET /hub-content?kind=md).

    # ── вся база ──
    # Карты областей исключены и отсюда — иначе их платный текст утекал бы
    # одним архивом мимо любой проверки доступа.
    vault_entries = {}
    for n in notes:
        if n["type"] in PUBLISHED_TYPES and n["type"] != "hub":
            vault_entries[f"{n['id']}.md"] = downloads.reconstruct_md(n).encode("utf-8")
    for img in asset_files:
        fp = IMAGES_DIR / img
        vault_entries[f"Изображения/{img}"] = fp.read_bytes()
    write_bytes("dl/freud-vault.zip", downloads.build_zip(vault_entries))
    if (EXPORT_DIR / "notes.json").exists():
        # Сырой notes.json поставщика содержит тела ВСЕХ заметок, включая
        # карты областей — те платные. Публикуем копию с пустыми телами
        # у карт вместо байт-в-байт копии исходника (works/tags/stats —
        # структурные данные без прозы, их можно копировать как есть).
        public_notes = [dict(n, body="") if n["type"] == "hub" else n for n in notes]
        write_text("dl/data/notes.json", json.dumps(public_notes, ensure_ascii=False))
        for fname in ("works.json", "tags.json", "stats.json"):
            src = EXPORT_DIR / fname
            if src.exists():
                write_bytes(f"dl/data/{fname}", src.read_bytes())

    # ══════════════ статика ══════════════
    if IMAGES_DIR.exists():
        for svg in IMAGES_DIR.glob("*.svg"):
            write_bytes(f"assets/images/{svg.name}", svg.read_bytes())

    for asset_name in (
        "style.css", "app.js", "tg.js", "random.js", "search.js", "annotations.js", "mynotes.js",
        "comments.js", "conceptlinks.js", "access.js", "hub-gate.js", "logo.svg", "hero-header.webp",
    ):
        src = PROJECT_DIR / "assets" / asset_name
        if src.exists():
            write_bytes(f"assets/{asset_name}", src.read_bytes())
    icon_src = PROJECT_DIR / "assets" / "icons" / "icon.svg"
    if icon_src.exists():
        write_bytes("assets/icons/icon.svg", icon_src.read_bytes())
    for font in (PROJECT_DIR / "assets" / "fonts").glob("*"):
        write_bytes(f"assets/fonts/{font.name}", font.read_bytes())

    manifest_tpl = (PROJECT_DIR / "assets" / "manifest.webmanifest.template").read_text(encoding="utf-8")
    manifest = (
        manifest_tpl.replace("__START__", su("/")).replace("__SCOPE__", su("/") or "/").replace("__ASSETS__", assets_base)
    )
    write_text("manifest.webmanifest", manifest)

    write_text(".nojekyll", "")

    # ══════════════ поисковый индекс (pagefind) ══════════════
    try:
        result = subprocess.run(
            ["npx", "--yes", "pagefind", "--site", str(OUT_DIR), "--output-subdir", "pagefind"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print("[pagefind] не удалось собрать индекс:\n" + result.stderr, file=sys.stderr)
        else:
            print("[pagefind] индекс собран")
    except (OSError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[pagefind] пропущено ({e}) — поиск не будет работать локально до `npx pagefind`", file=sys.stderr)

    print(f"Готово: {sum(1 for n in notes if n['type'] in PUBLISHED_TYPES)} страниц заметок, "
          f"{len(works)} работ, {len(hubs)} карт, {len(tag_notes)} тегов.")


if __name__ == "__main__":
    main()
