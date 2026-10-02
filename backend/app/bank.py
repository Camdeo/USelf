import gzip
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Question


BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "question_bank_v1.json.gz"


def load_bank() -> dict:
    with gzip.open(BANK_PATH, "rt", encoding="utf-8") as handle:
        return json.load(handle)


BANK = load_bank()
THEME_META = {item["slug"]: item for item in BANK["themes"]}
VALID_THEME_SLUGS = set(THEME_META)


def seed_question_bank(db: Session) -> None:
    existing = {q.external_id: q for q in db.scalars(select(Question)).all()}
    block_intro = {
        (theme["slug"], block["id"]): block.get("intro") or None
        for theme in BANK["themes"]
        for block in theme["blocks"]
    }
    for index, row in enumerate(BANK["questions"], start=1):
        values = {
            "bank_order": index,
            "theme_slug": row["theme_slug"],
            "theme_title": row["theme_title"],
            "block_id": row["block_id"],
            "block_title": row["block_title"],
            "block_intro": block_intro.get((row["theme_slug"], row["block_id"])),
            "sort_order": int(row["sort_order"]),
            "text": row["text"],
            "side_code": row.get("side_code"),
            "side_label": row.get("side_label"),
            "attention_code": row.get("attention_code"),
            "attention_note": row.get("attention_note"),
            "knowledge_ref": row.get("knowledge_ref"),
            "review_flag": row.get("review_flag"),
            "review_note": row.get("review_note"),
            "is_active": True,
        }
        current = existing.get(row["external_id"])
        if current:
            for key, value in values.items():
                setattr(current, key, value)
        else:
            db.add(Question(external_id=row["external_id"], **values))
    db.commit()


def public_themes(db: Session) -> list[dict]:
    rows = db.scalars(select(Question).where(Question.is_active.is_(True)).order_by(Question.bank_order)).all()
    counts: dict[str, int] = {}
    for q in rows:
        counts[q.theme_slug] = counts.get(q.theme_slug, 0) + 1
    result = []
    for theme in sorted(BANK["themes"], key=lambda x: x["sort"]):
        result.append(
            {
                "slug": theme["slug"],
                "title": theme["title"],
                "question_count": counts.get(theme["slug"], 0),
                "blocks": [
                    {"id": b["id"], "title": b["title"], "intro": b.get("intro") or ""}
                    for b in theme["blocks"]
                ],
            }
        )
    return result
