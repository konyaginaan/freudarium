"""
Инлайнинг SVG-схем базы Фрейда на этапе сборки (Фаза 3 постпрода).

Раньше схемы вставлялись как `<img src="...">` — граница `<img>` не пропускает
CSS-переменные страницы внутрь SVG, поэтому переключатель тем сайта
(`:root[data-theme=...]`) их не касался, а `@import` шрифтов внутри `<img>`-SVG
вообще не загружается (все схемы рендерились запасным Georgia).

Здесь схема вставляется как обычный `<svg>`-узел прямо в разметку страницы:
- собственный `:root {...}` блок схемы снимается — большинство схем объявляют
  ровно те же имена переменных, что и страница (`--surface`, `--ink` и т.п.),
  поэтому просто убрать локальный `:root` и правила продолжают работать,
  теперь уже беря значения из настоящего `:root` страницы;
- переменные с именами, которых на странице нет (акцентные цвета вроде
  `--flesh`), не удаляются, а привязываются к корневому `<svg>` через класс-
  метку конкретного экземпляра — не глобально;
- один файл (см. RENAME_OVERRIDES) называет переменные иначе
  (`--page`/`--card`/…) — их имена сопоставлены с именами страницы вручную;
- жёстко зашитый фоновый прямоугольник (`fill="#EFE2D8"`) переводится на
  `var(--surface)`;
- классы и id внутри схемы получают префикс уникальный для файла — на одной
  странице («Групповая психология и анализ Я») встречается до 18 схем разом,
  без этого совпадающие класс `.cell`/`.title` и id `title`/`desc`/`arrow`
  перекрывали бы друг друга.

Падать громко: если файл не удаётся распознать (нет `<svg`, нет `<style>` —
структура, которой ни разу не встречалось на реальных 30 файлах), поднимается
исключение, а не тихий возврат «как есть».
"""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

_STYLE_BLOCK_RE = re.compile(r"<style>(.*?)</style>", re.DOTALL)
_IMPORT_LINE_RE = re.compile(r"[ \t]*@import\s+url\([^)]*\)\s*;\s*\n?")
_MEDIA_DARK_ROOT_RE = re.compile(
    r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{[^}]*\}\s*\}"
)
_ROOT_BLOCK_RE = re.compile(r":root\s*\{([^}]*)\}")
_VAR_DECL_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
_SVG_OPEN_RE = re.compile(r"<svg\b([^>]*)>")
_BG_RECT_RE = re.compile(r'<rect width="(\d+)" height="(\d+)" fill="#[0-9A-Fa-f]{3,8}"\s*/>')
_CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z_][\w-]*)")
_CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')
_ID_ATTR_RE = re.compile(r'id="([A-Za-z][\w-]*)"')
_ARIA_LABELLEDBY_RE = re.compile(r'aria-labelledby="([^"]*)"')
_HASH_REF_RE = re.compile(r'(url\(#|(?:xlink:)?href="#)([A-Za-z][\w-]*)')

KNOWN_PAGE_VARS = {
    "--surface", "--surface-2", "--surface-3", "--ink", "--ink-muted",
    "--bruise", "--border", "--shadow", "--panel-dark", "--panel-dark-ink",
}

# Единственный найденный при аудите файл с другой схемой имён переменных.
RENAME_OVERRIDES = {
    "Галлюцинаторный психоз желания (Фрейд, 1917).svg": {
        "--page": "--surface",
        "--card": "--surface-2",
        "--text": "--ink",
        "--muted": "--ink-muted",
        "--rule": "--border",
        "--mark-a": "--bruise",
    },
}


class SvgStructureError(Exception):
    pass


def _uid_for(fname: str) -> str:
    return "s" + hashlib.md5(fname.encode("utf-8")).hexdigest()[:8]


def _process_style(style_body: str, fname: str, uid: str) -> str:
    style_body = _IMPORT_LINE_RE.sub("", style_body)
    root_m = _ROOT_BLOCK_RE.search(style_body)
    local_vars = (
        {name: val.strip() for name, val in _VAR_DECL_RE.findall(root_m.group(1))}
        if root_m else {}
    )
    for old, new in RENAME_OVERRIDES.get(fname, {}).items():
        if old in local_vars:
            style_body = style_body.replace(f"var({old})", f"var({new})")
            del local_vars[old]
    leftover = {n: v for n, v in local_vars.items() if n not in KNOWN_PAGE_VARS}

    style_body = _MEDIA_DARK_ROOT_RE.sub("", style_body)
    style_body = _ROOT_BLOCK_RE.sub("", style_body)

    class_names = sorted(set(_CLASS_SELECTOR_RE.findall(style_body)), key=len, reverse=True)
    for name in class_names:
        style_body = re.sub(rf"\.{re.escape(name)}\b", f".{uid}-{name}", style_body)

    if leftover:
        decls = " ".join(f"{name}: {val};" for name, val in leftover.items())
        style_body += f"\nsvg.{uid} {{ {decls} }}\n"
    style_body += "\n.svg-embed-bg { fill: var(--surface); }\n"
    return style_body, class_names


def render_embed(fname: str, images_dir: Path, alt: str = "") -> str:
    """Возвращает готовую разметку `<figure class="svg-embed">…</figure>`
    для встраивания SVG-файла `fname` из `images_dir` прямо в страницу.
    """
    fp = images_dir / fname
    text = fp.read_text(encoding="utf-8")

    svg_open_m = _SVG_OPEN_RE.search(text)
    style_m = _STYLE_BLOCK_RE.search(text)
    if not svg_open_m or not style_m:
        raise SvgStructureError(f"неожиданная структура SVG: {fname}")

    uid = _uid_for(fname)
    new_style_body, class_names = _process_style(style_m.group(1), fname, uid)
    text = text[:style_m.start(1)] + new_style_body + text[style_m.end(1):]

    text = _BG_RECT_RE.sub(
        lambda m: f'<rect width="{m.group(1)}" height="{m.group(2)}" class="svg-embed-bg"/>',
        text, count=1,
    )

    for name in class_names:
        def _sub_class_attr(m, name=name, uid=uid):
            tokens = m.group(1).split()
            tokens = [f"{uid}-{name}" if t == name else t for t in tokens]
            return f'class="{" ".join(tokens)}"'
        text = re.sub(rf'class="([^"]*\b{re.escape(name)}\b[^"]*)"', _sub_class_attr, text)

    ids = sorted(set(_ID_ATTR_RE.findall(text)), key=len, reverse=True)
    for id_ in ids:
        text = re.sub(rf'id="{re.escape(id_)}"', f'id="{uid}-{id_}"', text)
        text = _HASH_REF_RE.sub(
            lambda m, id_=id_, uid=uid: (
                f"{m.group(1)}{uid}-{id_}" if m.group(2) == id_ else m.group(0)
            ),
            text,
        )

    def _sub_aria(m):
        tokens = m.group(1).split()
        tokens = [f"{uid}-{t}" if t in ids else t for t in tokens]
        return f'aria-labelledby="{" ".join(tokens)}"'
    text = _ARIA_LABELLEDBY_RE.sub(_sub_aria, text)

    svg_open_m = _SVG_OPEN_RE.search(text)
    attrs = svg_open_m.group(1)
    new_open = f'<svg{attrs} class="{uid}">'
    text = text[:svg_open_m.start()] + new_open + text[svg_open_m.end():]

    return f'<figure class="svg-embed">{text.strip()}</figure>'


@lru_cache(maxsize=None)
def _render_embed_cached(fname: str, images_dir_str: str) -> str:
    return render_embed(fname, Path(images_dir_str))


def render_embed_cached(fname: str, images_dir: Path) -> str:
    return _render_embed_cached(fname, str(images_dir))
