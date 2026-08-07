#!/usr/bin/env python3
"""
Публикует тело каждой карты области (type=="hub") в HUB_CONTENT_KV воркера
(см. ~/projects/freudarium-server/worker.js: GET /hub-content).

Карты — платный контент (см. templates/pages.py:render_hub): их HTML-тело
и .md НЕ попадают в статический docs/ (build.py их туда не пишет), а живут
только здесь, в KV, и отдаются авторизованным + оплатившим запросом.

Запуск (после обычной сборки — slug'и должны быть свежими, и с тем же
SITE_BASE, что и прод-сборка, иначе ссылки внутри карт будут вести не туда):
    SITE_BASE=/freudarium python3 push_hubs.py
Требует авторизованный `wrangler` (тот же аккаунт, что и для остальных KV
этого проекта, см. ~/projects/freudarium-server/wrangler.toml) — сам
вызывает `wrangler kv bulk put` в терминале.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from templates import downloads, mdconv

PROJECT_DIR = Path(__file__).parent
SERVER_DIR = PROJECT_DIR.parent / "freudarium-server"
VAULT_DIR = Path.home() / "Downloads" / "Обсидиан" / "купс группа" / "Фрейд"
EXPORT_DIR = Path.home() / "freud-export" / "data"
IMAGES_DIR = VAULT_DIR / "Изображения"
SLUGS_FILE = PROJECT_DIR / "slugs.json"

SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")
PREFIX_BY_TYPE = {"atomic": "n", "conspect": "w", "hub": "m", "full_text": "f"}
KV_BINDING = "HUB_CONTENT_KV"


def su(path: str) -> str:
    return f"{SITE_BASE}{path}"


def main():
    notes = json.loads((EXPORT_DIR / "notes.json").read_text(encoding="utf-8"))
    slug_map = json.loads(SLUGS_FILE.read_text(encoding="utf-8"))
    by_id = {n["id"]: n for n in notes}

    def note_url(nid):
        n = by_id.get(nid)
        if not n or n["id"] not in slug_map:
            return None
        prefix = PREFIX_BY_TYPE.get(n["type"])
        if not prefix:
            return None
        return su(f"/{prefix}/{slug_map[n['id']]}/")

    hubs = [n for n in notes if n["type"] == "hub"]
    entries = []
    for h in hubs:
        slug = slug_map.get(h["id"])
        if not slug:
            print(f"пропускаю {h['id']!r} — нет slug'а в {SLUGS_FILE.name}", file=sys.stderr)
            continue
        body_html = mdconv.render_body(h["body"], note_url, su("/assets"), images_dir=IMAGES_DIR)
        entries.append({"key": f"html:{slug}", "value": body_html})
        entries.append({"key": f"md:{slug}", "value": downloads.reconstruct_md(h)})

    batch_file = PROJECT_DIR / "_hub_kv_batch.json"
    batch_file.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    print(f"{len(hubs)} карт, {len(entries)} записей — батч записан в {batch_file.name}")
    print(f"Загружаю в {KV_BINDING} через wrangler kv bulk put...")
    subprocess.run(
        ["npx", "wrangler", "kv", "bulk", "put", str(batch_file), "--binding", KV_BINDING, "--remote"],
        cwd=str(SERVER_DIR),
        check=True,
    )
    batch_file.unlink()
    print("Готово.")


if __name__ == "__main__":
    main()
