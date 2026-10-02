import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DB_PATH = Path("test_uself_alpha.db").resolve()
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def token_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def auth(token: str) -> dict[str, str]:
    return {"X-Participant-Token": token}


def create_room(client: TestClient, themes=None):
    themes = themes or ["toys"]
    response = client.post(
        "/api/sessions",
        json={"creator_alias": "Тимур", "creator_age": 30, "theme_slugs": themes},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload, token_from(payload["creator_url"]), token_from(payload["partner_url"])


def test_health_and_real_bank_loaded():
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] is True
        assert health["questions"] == 312
        themes = client.get("/api/themes").json()["themes"]
        counts = {t["slug"]: t["question_count"] for t in themes}
        assert counts == {
            "sex": 101,
            "toys": 20,
            "bdsm": 83,
            "anal": 22,
            "public": 23,
            "group": 32,
            "fetish": 31,
        }


def test_creator_selects_themes_partner_enters_own_profile():
    with TestClient(app) as client:
        room, creator_token, partner_token = create_room(client, ["toys", "anal"])
        assert room["question_count"] == 42

        creator = client.get("/api/me", headers=auth(creator_token)).json()
        partner = client.get("/api/me", headers=auth(partner_token)).json()
        assert creator["alias"] == "Тимур"
        assert creator["profile_complete"] is True
        assert partner["alias"] is None
        assert partner["profile_complete"] is False

        blocked = client.get("/api/questions", headers=auth(partner_token))
        assert blocked.status_code == 409

        joined = client.put(
            "/api/profile",
            headers=auth(partner_token),
            json={"alias": "Анна", "age": 27},
        )
        assert joined.status_code == 200
        partner = client.get("/api/me", headers=auth(partner_token)).json()
        assert partner["alias"] == "Анна"
        assert partner["age"] == 27
        assert partner["total"] == 42


def test_skips_are_allowed_answers_and_comments_autosave():
    with TestClient(app) as client:
        _, creator_token, partner_token = create_room(client, ["toys"])
        client.put("/api/profile", headers=auth(partner_token), json={"alias": "Анна", "age": 27})
        questions = client.get("/api/questions", headers=auth(creator_token)).json()["questions"]
        q = questions[0]

        saved = client.put(
            "/api/responses",
            headers=auth(creator_token),
            json={"session_question_id": q["id"], "value": "yes", "comment": "Хочу попробовать вместе."},
        )
        assert saved.status_code == 200
        me = client.get("/api/me", headers=auth(creator_token)).json()
        assert me["answered"] == 1
        assert me["comments"] == 1

        # Submission is allowed although 19 questions are still blank.
        submitted = client.post("/api/submit", headers=auth(creator_token), json={"confirm": True})
        assert submitted.status_code == 200
        waiting = client.get("/api/results", headers=auth(creator_token)).json()
        assert waiting["ready"] is False


def test_result_color_matrix_and_comments_visible_after_both_submit():
    with TestClient(app) as client:
        _, creator_token, partner_token = create_room(client, ["toys"])
        client.put("/api/profile", headers=auth(partner_token), json={"alias": "Анна", "age": 27})
        questions = client.get("/api/questions", headers=auth(creator_token)).json()["questions"]
        q1, q2, q3, q4, q5, q6 = questions[:6]

        combos = [
            (q1, "yes", "yes", "green"),
            (q2, "yes", "maybe", "blue"),
            (q3, "maybe", "maybe", "blue"),
            (q4, "yes", "no", "red"),
            (q5, "no", None, "red"),
            (q6, "yes", None, "neutral"),
        ]
        for index, (q, creator_value, partner_value, _) in enumerate(combos):
            client.put(
                "/api/responses",
                headers=auth(creator_token),
                json={
                    "session_question_id": q["id"],
                    "value": creator_value,
                    "comment": "Комментарий Тимура" if index == 0 else None,
                },
            )
            if partner_value is not None:
                client.put(
                    "/api/responses",
                    headers=auth(partner_token),
                    json={
                        "session_question_id": q["id"],
                        "value": partner_value,
                        "comment": "Комментарий Анны" if index == 0 else None,
                    },
                )

        # Results remain hidden until both have submitted.
        client.post("/api/submit", headers=auth(creator_token), json={"confirm": True})
        assert client.get("/api/results", headers=auth(creator_token)).json()["ready"] is False
        client.post("/api/submit", headers=auth(partner_token), json={"confirm": True})

        result = client.get("/api/results", headers=auth(partner_token)).json()
        assert result["ready"] is True
        by_id = {item["id"]: item for item in result["items"]}
        for q, _, _, expected in combos:
            assert by_id[q["id"]]["status"] == expected
        assert by_id[q1["id"]]["creator"]["comment"] == "Комментарий Тимура"
        assert by_id[q1["id"]]["partner"]["comment"] == "Комментарий Анны"
        assert by_id[q4["id"]]["creator"]["answer_label"] == "Да"
        assert by_id[q4["id"]]["partner"]["answer_label"] == "Нет"


def test_clicking_selected_answer_can_return_to_skipped_state_via_api_null():
    with TestClient(app) as client:
        _, creator_token, _ = create_room(client, ["toys"])
        q = client.get("/api/questions", headers=auth(creator_token)).json()["questions"][0]
        client.put(
            "/api/responses",
            headers=auth(creator_token),
            json={"session_question_id": q["id"], "value": "yes", "comment": None},
        )
        client.put(
            "/api/sponses",
            headers=auth(creator_token),
            json={"session_question_id": q["id"], "value": None, "comment": None},
        )
        me = client.get("/api/me", headers=auth(creator_token)).json()
        assert me["answered"] == 0
