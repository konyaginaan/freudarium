"""Slug-утилиты. Для самих заметок используется slug из notes.json (уже
уникален и посчитан build_export.py), но URL заметки замораживается в
slugs.json на уровне сайта — переименование в Obsidian меняет slug в экспорте,
но НЕ должно менять уже опубликованный адрес. Для тегов своя генерация —
тот же алфавит транслитерации, что и в ~/freud-export/scripts/build_export.py."""
import hashlib
import re

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(title: str, seen: set) -> str:
    s = title.lower()
    out = []
    for ch in s:
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append("-")
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")[:80] or "note"
    candidate = slug
    if candidate in seen:
        h = hashlib.md5(title.encode("utf-8")).hexdigest()[:6]
        candidate = f"{slug}-{h}"
    seen.add(candidate)
    return candidate


def freeze_slugs(notes: list[dict], frozen: dict) -> dict:
    """
    frozen: {id: slug}, уже сохранённое ранее отображение (из slugs.json).
    Возвращает обновлённое отображение: старые id сохраняют свой slug
    навсегда, даже если заметка была переименована и notes.json прислал
    для неё новый 'slug'; новые id получают slug из notes.json, с проверкой
    на коллизию с уже занятыми (в т.ч. чужими старыми) slug'ами.
    """
    result = dict(frozen)
    seen = set(frozen.values())
    for n in notes:
        if n["id"] in result:
            continue
        candidate = n["slug"]
        if candidate in seen:
            h = hashlib.md5(n["id"].encode("utf-8")).hexdigest()[:6]
            candidate = f"{candidate}-{h}"[:80]
        seen.add(candidate)
        result[n["id"]] = candidate
    return result
