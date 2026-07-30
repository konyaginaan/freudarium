"""Реконструкция .md из notes.json (совместимо с Obsidian) + сборка zip-архивов
для скачивания: одна работа, одна карта области, вся база. Скачивание заметки
с окружением и произвольных наборов делает браузерный JS (assets/app.js) из
уже опубликованных docs/dl/n/<slug>.md — здесь эти файлы только пишутся."""
import io
import zipfile


def reconstruct_md(note: dict) -> str:
    lines = []
    if note.get("tags"):
        lines.append("---")
        lines.append("tags: [" + ", ".join(note["tags"]) + "]")
        lines.append("---")
        lines.append("")
    if note.get("source_work_id"):
        detail = f" {note['source_detail']}" if note.get("source_detail") else ""
        lines.append(f"Источник:: [[{note['source_work_id']}]]{detail}")
        lines.append("")
    lines.append(note["body"].strip("\n"))
    if note.get("full_text_refs"):
        refs = " ".join(
            f"[[{r['target']}#^{r['anchor']}]]" if r.get("anchor") else f"[[{r['target']}]]"
            for r in note["full_text_refs"]
        )
        lines.append("")
        lines.append(f"Полный-текст:: {refs}")
    return "\n".join(lines) + "\n"


def safe_filename(note_id: str) -> str:
    return note_id.replace("/", "-") + ".md"


def build_zip(entries: dict[str, bytes]) -> bytes:
    """entries: {путь_внутри_архива: содержимое_байтами}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in sorted(entries.items()):
            zf.writestr(path, data)
    return buf.getvalue()
