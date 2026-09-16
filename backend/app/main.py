from collections import defaultdict
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db, SessionLocal
from .models import QuizSession, Participant, ParticipantRole, ParticipantStatus, Question, QuizSessionQuestion, Answer, AnswerValue
from .schemas import CreateSessionIn, AnswerIn, SubmitIn
from .security import new_token, hash_token
from .seed import seed_questions

app = FastAPI(title="USelf Test API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_questions(db)

def participant_from_token(db: Session, token: str) -> Participant:
    p = db.scalar(select(Participant).where(Participant.access_token_hash == hash_token(token)))
    if not p:
        raise HTTPException(401, "Недействительная приватная ссылка")
    return p

def auth_participant(db: Session = Depends(get_db), x_participant_token: str | None = Header(default=None)):
    if not x_participant_token:
        raise HTTPException(401, "Не указан токен участника")
    return participant_from_token(db, x_participant_token)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/sessions")
def create_session(payload: CreateSessionIn, db: Session = Depends(get_db)):
    questions = list(db.scalars(select(Question).where(Question.is_active == True).order_by(Question.id)).all())
    if not questions:
        raise HTTPException(503, "Банк вопросов пуст")
    session = QuizSession()
    db.add(session)
    db.flush()
    creator_token, partner_token = new_token(), new_token()
    creator = Participant(quiz_session_id=session.id, role=ParticipantRole.creator, alias=payload.creator_alias, access_token_hash=hash_token(creator_token))
    partner = Participant(quiz_session_id=session.id, role=ParticipantRole.partner, alias=payload.partner_alias, access_token_hash=hash_token(partner_token))
    db.add_all([creator, partner])
    for i, q in enumerate(questions, start=1):
        db.add(QuizSessionQuestion(
            quiz_session_id=session.id, question_id=q.id, position=i,
            text_snapshot=q.text, category_snapshot=q.category, block_snapshot=q.block,
            direction_snapshot=q.direction, safety_note_snapshot=q.safety_note,
        ))
    db.commit()
    return {
        "session_id": str(session.id),
        "creator_url": f"/quiz?token={creator_token}",
        "partner_url": f"/quiz?token={partner_token}",
    }

@app.get("/me")
def me(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(QuizSessionQuestion).where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id)) or 0
    answered = db.scalar(select(func.count()).select_from(Answer).where(Answer.participant_id == participant.id)) or 0
    return {"alias": participant.alias, "role": participant.role.value, "status": participant.status.value, "answered": answered, "total": total}

@app.get("/questions")
def questions(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    qs = list(db.scalars(select(QuizSessionQuestion).where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id).order_by(QuizSessionQuestion.position)).all())
    answers = {a.session_question_id: a.value.value for a in db.scalars(select(Answer).where(Answer.participant_id == participant.id)).all()}
    return [{
        "id": q.id, "position": q.position, "text": q.text_snapshot,
        "category": q.category_snapshot, "block": q.block_snapshot,
        "direction": q.direction_snapshot, "safety_note": q.safety_note_snapshot,
        "answer": answers.get(q.id),
    } for q in qs]

@app.put("/answers")
def put_answer(payload: AnswerIn, participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    if participant.status == ParticipantStatus.completed:
        raise HTTPException(409, "Опрос уже завершён")
    sq = db.get(QuizSessionQuestion, payload.session_question_id)
    if not sq or sq.quiz_session_id != participant.quiz_session_id:
        raise HTTPException(404, "Вопрос не найден в этой комнате")
    answer = db.scalar(select(Answer).where(Answer.participant_id == participant.id, Answer.session_question_id == sq.id))
    value = AnswerValue(payload.value)
    if answer:
        answer.value = value
    else:
        db.add(Answer(participant_id=participant.id, session_question_id=sq.id, value=value))
    participant.status = ParticipantStatus.in_progress
    db.commit()
    return {"ok": True}

@app.post("/submit")
def submit(_: SubmitIn, participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(QuizSessionQuestion).where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id)) or 0
    answered = db.scalar(select(func.count()).select_from(Answer).where(Answer.participant_id == participant.id)) or 0
    if answered != total:
        raise HTTPException(409, f"Нужно ответить на все вопросы: {answered}/{total}")
    participant.status = ParticipantStatus.completed
    participant.completed_at = datetime.utcnow()
    participants = list(db.scalars(select(Participant).where(Participant.quiz_session_id == participant.quiz_session_id)).all())
    if all(p.status == ParticipantStatus.completed for p in participants):
        session = db.get(QuizSession, participant.quiz_session_id)
        session.status = "completed"
        session.completed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}

@app.get("/results")
def results(participant: Participant = Depends(auth_participant), db: Session = Depends(get_db)):
    participants = list(db.scalars(select(Participant).where(Participant.quiz_session_id == participant.quiz_session_id)).all())
    if len(participants) != 2 or not all(p.status == ParticipantStatus.completed for p in participants):
        return {"ready": False, "message": "Результаты появятся, когда оба участника завершат опрос"}
    answer_maps = []
    for p in participants:
        answer_maps.append({a.session_question_id: a.value for a in db.scalars(select(Answer).where(Answer.participant_id == p.id)).all()})
    qs = list(db.scalars(select(QuizSessionQuestion).where(QuizSessionQuestion.quiz_session_id == participant.quiz_session_id).order_by(QuizSessionQuestion.position)).all())
    groups = defaultdict(list)
    rank = {AnswerValue.yes: 2, AnswerValue.maybe: 1}
    for q in qs:
        a, b = answer_maps[0].get(q.id), answer_maps[1].get(q.id)
        if a in rank and b in rank:
            score = rank[a] + rank[b]
            strength = "strong" if score == 4 else "explore" if score == 3 else "maybe"
            groups[q.category_snapshot].append({
                "id": q.id, "text": q.text_snapshot, "block": q.block_snapshot,
                "direction": q.direction_snapshot, "safety_note": q.safety_note_snapshot,
                "strength": strength,
            })
    return {"ready": True, "categories": [{"name": k, "matches": v} for k, v in groups.items()], "match_count": sum(len(v) for v in groups.values())}


# Production frontend. The root Dockerfile builds Vite into /app/frontend/dist.
# API routes are declared above, so these UI routes do not shadow them.
STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/quiz", include_in_schema=False)
    def frontend_quiz():
        return FileResponse(STATIC_DIR / "index.html")
