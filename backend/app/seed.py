import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Question

DATA = Path(__file__).resolve().parent.parent / "data" / "questions.demo.json"

def seed_questions(db: Session):
    if db.scalar(select(Question.id).limit(1)) is not None:
        return
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    for row in rows:
        db.add(Question(**row))
    db.commit()
