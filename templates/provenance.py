"""Честная маркировка «полных текстов»: определяет, является ли конкретный
файл настоящим переводом Фрейда или чем-то другим (склейка атомарных
заметок, изложение по конспекту, сжатый пересказ) — и что показать читателю
в каждом случае.

Каждый файл в хранилище сам объявляет свой тип в шапке («Перевод с
немецкого оригинала», «Текст собран из построчных атомарных заметок»,
«Пересказ сути», «Изложение сути работы по главам») — этого достаточно для
автоматической классификации, ручная разметка 47 файлов не нужна.
Прогнано и проверено на всех 47 текущих файлах (audit 30.07.2026): 15
translation / 9 digest / 12 retelling / 11 assembled, 0 неразобранных.

Только для отображения на сайте — не трогает build_export.py и имена
файлов в хранилище (см. план в ~/.claude/plans/11-47-peppy-journal.md,
раздел «Про переименование файлов — не делаем»).
"""
import re

# Строка с готовым переводом — исключается из текста ПЕРЕД классификацией
# (иначе слово «перевод» в ней ложно матчит паттерн translation) и отдельно
# разбирается на ссылки (их может быть больше одной на строке, через запятую).
_READY_LINE_RE = re.compile(r"^[ \t]*Готовый перевод на русском[^\n]*$", re.M)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_STATUS_RE = re.compile(r"^Статус:\s*(.+)$", re.M)

# Порядок проверок принципиален, не косметика: часть пересказов содержит
# буквальный оборот «НЕ построчный перевод» — если проверять translation
# первым, они распознаются как переводы. assembled/digest/retelling всегда
# проверяются раньше translation.
_CLASS_PATTERNS = [
    ("assembled", re.compile(
        r"собран[оа]?\s+из\s+построчных\s+(?:атомарных\s+)?заметок|каждая\s+отдельная\s+мысль\s+дана\s+как",
        re.I,
    )),
    ("digest", re.compile(r"изложение\s+сути", re.I)),
    ("retelling", re.compile(
        r"пересказ\s+сути|сжатый\s+пересказ|пересказ\s+с\s+немецкого\s+оригинала", re.I,
    )),
    ("translation", re.compile(r"построчный\s+перевод|перевод\s+с\s+немецкого\s+оригинала", re.I)),
]

CLASS_LABELS = {
    "translation": "Перевод с оригинала",
    "assembled": "Собрано из заметок",
    "digest": "Изложение по конспекту",
    "retelling": "Пересказ",
}

# Показывается на странице у не-переводов, над кнопкой/отказом (см. describe()).
CLASS_EXPLANATIONS = {
    "assembled": "Текст ниже собран из атомарных заметок этого хранилища и подан как Тезис / Аргументы / Вывод. Это не перевод — слова не Фрейда.",
    "digest": "Изложение сути по главам, собранное из конспекта этого хранилища. Это не перевод — слова не Фрейда.",
    "retelling": "Сжатый пересказ: каждый довод передан точно, но своими словами, а не переведён построчно.",
}

# Ручное исключение. «Толкование сновидений»: её «Готовый перевод» ведёт на
# голый корень freudproject.ru с явной оговоркой в самом файле, что
# канонического перевода 1-го издания в открытом доступе не нашли —
# показывать это кнопкой «Читать настоящий перевод» нельзя, это будет
# увереннее неправым, чем нынешнее состояние. Пусть остаётся честное
# «перевода в открытом доступе не нашлось».
OVERRIDES = {
    "Толкование сновидений — полный текст, Фрейд, 1900": {"ready_links": []},
}


def split_header(body):
    """Шапка — ведущие блоки (абзацы, разделённые пустой строкой) до первого
    markdown-заголовка (#/##) или блока, заканчивающегося на ^pN (первый
    абзац самого содержания). Проверено на всех 47 файлах — граница везде
    на блоке 2–4, само содержание (rest) никогда не задевается."""
    blocks = re.split(r"\n\s*\n", body.strip())
    header_blocks = []
    rest_idx = len(blocks)
    for i, block in enumerate(blocks):
        if re.match(r"^#{1,2}\s", block) or re.search(r"\^[a-zA-Z0-9]+\s*$", block.strip()):
            rest_idx = i
            break
        header_blocks.append(block)
    return "\n\n".join(header_blocks), "\n\n".join(blocks[rest_idx:])


def classify(header_text):
    stripped = _READY_LINE_RE.sub("", header_text)
    for name, rx in _CLASS_PATTERNS:
        if rx.search(stripped):
            return name
    return None


def ready_links(body):
    """[(подпись, url), ...] из строки «Готовый перевод…» — их может быть
    несколько на одной строке через запятую (напр. «Вводные лекции»,
    «Предварительное сообщение»)."""
    m = _READY_LINE_RE.search(body)
    if not m:
        return []
    return _MD_LINK_RE.findall(m.group(0))


def status(body):
    m = _STATUS_RE.search(body)
    return m.group(1).strip() if m else None


def describe(note_id, body):
    """Единственная точка входа. Падает громко (не в translation!) на
    нераспознанной шапке — правка формулировки в хранилище должна ломать
    сборку, а не молча повышать пересказ до перевода."""
    header, body_rest = split_header(body)
    cls = classify(header)
    if cls is None:
        raise SystemExit(
            f"provenance.describe: не удалось определить тип полного текста «{note_id}» — "
            "проверьте формулировку шапки (см. _CLASS_PATTERNS в templates/provenance.py)"
        )
    links = ready_links(body)
    override = OVERRIDES.get(note_id)
    if override and "ready_links" in override:
        links = override["ready_links"]
    return {
        "cls": cls,
        "label": CLASS_LABELS[cls],
        "explanation": CLASS_EXPLANATIONS.get(cls),
        "ready_links": links,
        "status": status(body),
        "header_text": header,
        # Тело БЕЗ шапки — от него считаются главы (split_chapters в build.py),
        # чтобы шапка не оказывалась запечённой в тело главы 1 (как было с
        # эвристикой collapse_intro/split_intro_blocks в mdconv.py).
        "body_rest": body_rest,
    }
