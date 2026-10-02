from __future__ import annotations

import json
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .bank import BANK, VALID_THEME_SLUGS, public_themes, seed_question_bank
from .db import Base, SessionLocal, engine, get_db
from .models import Participant, Question, QuizSession, QuizSessionQuestion, Response
from .schemas import CreateSessionIn, ProfileIn, ResponseIn, SubmitIn
from .security import hash_token, new_token


ANSWER_LABELS = {"yes": "Да", "maybe": "Возможно", "no": "Нет", None: "Пропущено"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_question_bank(db)
    yield


app = FastAPI(title="USelf Alpha API", version="0.1.0", lifespan=lifespan)


def participant_from_token(db: Session, token: str) -> Participant:
    participant = db.scalar(select(Participant).where(Participant.access_token_hash == hash_token(token)))
    if not participant:
        raise HTTPException(status_code=401, detail="Недействительная приватная ссылка")
    return participant


def auth_participant(
    db: Session = Depends(get_db), x_participant_token: str | None = Header(default=None)
) -> Participant:
    if not x_participant_token:
        raise HTTPException(status_code=401, detail="Не указан токен участника")
    return participant_from_token(db, x_participant_token)


def participant_stats(db: Session, participant: Participant) -> dict:
    total = db.scalar(
        select(func.count()).select_from(QuizSessionQuestion).where(
            QuizSessionQuestion.quiz_session_id == participant.quiz_session_id
        )
    ) or 0
    answered = db.scalar(
        select(func.count()).select_from(Response).where(
            Response.participant_id == participant.id,
            Response.value.is_not(None),
        )
    ) or 0
    comments = db.scalar(
        select(func.count()).select_from(Response).where(
            Response.participant_id == participant.id,
            Response.comment.is_not(None),
        )
    ) or 0
    return {"total": total, "answered": answered, "comments": comments}


def classify(a: str | None, b: str | None) -> str:
    if a == "no" or b == "no":
        return "red"
    if a is None or b is None:
        return "neutral"
    if a == "yes" and b == "yes":
        return "green"
    return "blue"


@app.get("/health")
def health():
    return {"ok": True, "bank_version": BANK["version"], "questions": len(BANK["questions"])}


@app.get("/api/themes")
def themes(db: Session = Depends(get_db)):
    return {"themes": public_themes(db), "bank_version": BANK["version"]}


@app.post("/api/sessions")
def create_session(payload: CreateSessionIn, db: Session = Depends(get_db)):
    selected = list(dict.fromkeys(payload.theme_slugs))
    invalid = [slug for slug in selected if slug not in VALID_THEME_SLUGS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Неизвестные темы: {', '.join(invalid)}")

    questions = list(
        db.scalars(
            select(Question)
            .where(Question.is_active.is_(True), Question.theme_slug.in_(selected))
            .order_by(Question.bank_order)
        ).all()
    )
    if not questions:
        raise HTTPException(status_code=503, detail="Для выбранных тем нет вопросов")

    session = QuizSession(
        theme_slugs_json=json.dumps(selected, ensure_ascii=False),
        question_bank_version=BANK["version"],
    )
    db.add(session)
    db.flush()

    creator_token = new_token()
    partner_token = new_token()
    creator = Participant(
        quiz_session_id=session.id,
        role="creator",
        alias=payload.creator_alias,
        age=payload.creator_age,
        profile_complete=True,
        status="pending",
        access_token_hash=hash_token(creator_token),
    )
    partner = Participant(
        quiz_session_id=session.id,
        role="partner",
        profile_complete=False,
        status="pending",
        access_token_hash=hash_token(partner_token),
    )
    db.add_all([creator, partner])

    for position, q in enumerate(questions, start=1):
        db.add(
            QuizSessionQuestion(
                quiz_session_id=session.id,
                question_id=q.id,
                position=position,
                external_id_snapshot=q.external_id,
                theme_slug_snapshot=q.theme_slug,
                theme_title_snapshot=q.theme_title,
                block_id_snapshot=q.block_id,
                block_title_snapshot=q.block_title,
                block_intro_snapshot=q.block_intro,
                text_snapshot=q.text,
                side_label_snapshot=q.side_label,
                attention_note_snapshot=q.attention_note,
                review_flag_snapshot=q.review_flag,
            )
        )

    db.commit()
    return {
        "session_id": str(session.id),
        "creator_url": f"/?token={creator_token}",
        "partner_url": f"/?token={partner_token}",
        "question_count": len(questions),
        "theme_slugs": selected,
    }


@app.get("/api/me")
def me(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    session = db.get(QuizSession, participant.quiz_session_id)
    participants = list(
        db.scalars(select(Participant).where(Participant.quiz_session_id == participant.quiz_session_id)).all()
    )
    creator = next((p for p in participants if p.role == "creator"), None)
    partner = next((p for p in participants if p.role == "partner"), None)
    stats = participant_stats(db, participant)
    theme_slugs = json.loads(session.theme_slugs_json)
    theme_meta = {t["slug"]: t for t in public_themes(db)}
    return {
        "participant_id": str(participant.id),
        "role": participant.role,
        "alias": participant.alias,
        "age": participant.age,
        "profile_complete": participant.profile_complete,
        "status": participant.status,
        "session_status": session.status,
        "creator_alias": creator.alias if creator else None,
        "partner_alias": partner.alias if partner else None,
        "themes": [theme_meta[s] for s in theme_slugs if s in theme_meta],
        **stats,
    }


@app.put("/api/profile")
def update_profile(
    payload: ProfileIn,
    participant: Participant = Depends(auth_participant),
    db: Session = Depends(get_db),
):
    if participant.status == "completed":
        raise HTTPException(status_code=409, detail="Опрос уже завершён")
    participant.alias = payload.alias
    participant.age = payload.age
    participant.profile_complete = True
    db.commit()
    return {"ok": True}


@app.get("/api/questions")
def questions(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    if not participant.profile_complete:
        raise HTTPException(status_code=409, detail="Сначала укажи имя и возраст")

    session_questions = list(
        db.scalars(
            select(QuizSessionQuestion)
            .where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id)
            .order_by(QuizSessionQuestion.position)
        ).all()
    )
    responses = {
        response.session_question_id: response
        for response in db.scalars(select(Response).where(Response.participant_id == participant.id)).all()
    }
    return {
        "questions": [
            {
                "id": q.id,
                "position": q.position,
                "external_id": q.external_id_snapshot,
                "theme_slug": q.theme_slug_snapshot,
                "theme_title": q.theme_title_snapshot,
                "block_id": q.block_id_snapshot,
                "block_title": q.block_title_snapshot,
                "block_intro": q.block_intro_snapshot,
                "text": q.text_snapshot,
                "side_label": q.side_label_snapshot,
                "attention_note": q.attention_note_snapshot,
                "review_flag": q.review_flag_snapshot,
                "answer": responses[q.id].value if q.id in responses else None,
                "comment": responses[q.id].comment if q.id in responses else None,
            }
            for q in session_questions
        ]
    }


@app.put("/api/responses")
def put_response(
    payload: ResponseIn,
    participant: Participant = Depends(auth_participant),
    db: Session = Depends(get_db),
):
    if participant.status == "completed":
        raise HTTPException(status_code=409, detail="Опрос уже завершён")
    if not participant.profile_complete:
        raise HTTPException(status_code=409, detail="Сначала укажи имя и возраст")

    session_question = db.get(QuizSessionQuestion, payload.session_question_id)
    if not session_question or session_question.quiz_session_id != participant.quiz_session_id:
        raise HTTPException(status_code=404, detail="Вопрос не найден в этом тесте")

    response = db.scalar(
        select(Response).where(
            Response.participant_id == participant.id,
            Response.session_question_id == session_question.id,
        )
    )

    if payload.value is None and payload.comment is None:
        if response:
            db.delete(response)
    elif response:
        response.value = payload.value
        response.comment = payload.comment
    else:
        db.add(
            Response(
                participant_id=participant.id,
                session_question_id=session_question.id,
                value=payload.value,
                comment=payload.comment,
            )
        )

    participant.status = "in_progress"
    db.commit()
    return {"ok": True, **participant_stats(db, participant)}


@app.post("/api/submit")
def submit(
    payload: SubmitIn,
    participant: Participant = Depends(auth_participant),
    db: Session = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(status_code=422, detail="Нужно подтвердить завершение")
    if not participant.profile_complete:
        raise HTTPException(status_code=409, detail="Сначала укажи имя и возраст")
    if participant.status != "completed":
        participant.status = "completed"
        participant.completed_at = utcnow()

    participants = list(
        db.scalars(select(Participant).where(Participant.quiz_session_id == participant.quiz_session_id)).all()
    )
    if len(participants) == 2 and all(p.status == "completed" for p in participants):
        session = db.get(QuizSession, participant.quiz_session_id)
        session.status = "completed"
        session.completed_at = utcnow()
    db.commit()
    return {"ok": True}


@app.get("/api/results")
def results(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    participants = list(
        db.scalars(
            select(Participant)
            .where(Participant.quiz_session_id == participant.quiz_session_id)
            .order_by(Participant.created_at)
        ).all()
    )
    if len(participants) != 2 or not all(p.status == "completed" for p in participants):
        return {
            "ready": False,
            "message": "Результаты появятся, когда оба участника завершат свою часть теста.",
        }

    creator = next(p for p in participants if p.role == "creator")
    partner = next(p for p in participants if p.role == "partner")
    response_maps: dict[str, dict[int, Response]] = {}
    for p in (creator, partner):
        response_maps[p.role] = {
            r.session_question_id: r
            for r in db.scalars(select(Response).where(Response.participant_id == p.id)).all()
        }

    session_questions = list(
        db.scalars(
            select(QuizSessionQuestion)
            .where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id)
            .order_by(QuizSessionQuestion.position)
        ).all()
    )

    items = []
    counts: Counter[str] = Counter()
    for q in session_questions:
        cr = response_maps["creator"].get(q.id)
        pr = response_maps["partner"].get(q.id)
        creator_value = cr.value if cr else None
        partner_value = pr.value if pr else None
        status = classify(creator_value, partner_value)
        counts[status] += 1
        items.append(
            {
                "id": q.id,
                "position": q.position,
                "theme_slug": q.theme_slug_snapshot,
                "theme_title": q.theme_title_snapshot,
                "block_title": q.block_title_snapshot,
                "text": q.text_snapshot,
                "side_label": q.side_label_snapshot,
                "attention_note": q.attention_note_snapshot,
                "status": status,
                "creator": {
                    "alias": creator.alias,
                    "answer": creator_value,
                    "answer_label": ANSWER_LABELS[creator_value],
                    "comment": cr.comment if cr else None,
                },
                "partner": {
                    "alias": partner.alias,
                    "answer": partner_value,
                    "answer_label": ANSWER_LABELS[partner_value],
                    "comment": pr.comment if pr else None,
                },
            }
        )

    return {
        "ready": True,
        "creator": {"alias": creator.alias, "age": creator.age},
        "partner": {"alias": partner.alias, "age": partner.age},
        "counts": {key: counts.get(key, 0) for key in ("green", "blue", "red", "neutral")},
        "items": items,
    }


# Static frontend. API routes above are more specific and keep working normally.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(FRONTEND_DIR / "index.html")
