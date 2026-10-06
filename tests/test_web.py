from sqlalchemy import select

from matchday.models import League, Prediction, User


def create_league(client, name="Ekipa"):
    response = client.post("/leagues", data={"name": name})
    assert response.status_code == 303
    return response.headers["location"]


def test_probes(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_anonymous_user_is_sent_to_login(client):
    assert client.get("/").headers["location"] == "/login"
    assert client.get("/leagues/1").headers["location"] == "/login"


def test_register_login_logout(client, register):
    register("michal")
    assert client.get("/").status_code == 200
    client.post("/logout")
    assert client.get("/").status_code == 303
    assert client.post("/login", data={"username": "michal", "password": "wrong-pass"}).status_code == 401
    assert client.post("/login", data={"username": "michal", "password": "correct-horse"}).status_code == 303


def test_username_must_be_unique(client, register):
    register("michal")
    client.post("/logout")
    assert client.post("/register", data={"username": "michal", "password": "another-one"}).status_code == 409


def test_password_is_stored_hashed(client, db, register):
    register("michal")
    user = db.scalar(select(User).where(User.username == "michal"))
    assert "correct-horse" not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_join_league_by_invite_code(client, db, register):
    register("owner")
    league_url = create_league(client)
    code = db.scalar(select(League.invite_code))
    client.post("/logout")

    register("friend")
    assert client.get(league_url).status_code == 404  # not a member yet
    assert client.post("/leagues/join", data={"code": "nope"}).status_code == 404
    assert client.post("/leagues/join", data={"code": code}).headers["location"] == league_url
    assert "friend" in client.get(league_url).text


def test_prediction_can_change_until_kickoff(client, db, make_match, register):
    register("michal")
    league_url = create_league(client)
    match = make_match(hours_from_now=2)
    for home, away in [(1, 0), (2, 2)]:
        form = {"home": home, "away": away, "back": league_url}
        assert client.post(f"/predictions/{match.id}", data=form).status_code == 303
    prediction = db.scalar(select(Prediction))
    db.refresh(prediction)
    assert (prediction.home_score, prediction.away_score) == (2, 2)


def test_prediction_is_locked_after_kickoff(client, make_match, register):
    register("michal")
    league_url = create_league(client)
    match = make_match(hours_from_now=-1)
    response = client.post(f"/predictions/{match.id}", data={"home": 1, "away": 0, "back": league_url})
    assert response.status_code == 409


def test_prediction_rejects_bad_scores_and_foreign_redirects(client, make_match, register):
    register("michal")
    league_url = create_league(client)
    match = make_match(hours_from_now=2)
    url = f"/predictions/{match.id}"
    assert client.post(url, data={"home": -1, "away": 0, "back": league_url}).status_code == 422
    assert client.post(url, data={"home": 1, "away": 0, "back": "https://evil.example"}).status_code == 422


def test_leaderboard_counts_points_of_finished_matches(client, db, make_match, register):
    register("michal")
    league_url = create_league(client)
    exact, outcome, miss = (make_match(hours_from_now=2) for _ in range(3))
    for match, (home, away) in [(exact, (2, 1)), (outcome, (1, 0)), (miss, (0, 1))]:
        client.post(f"/predictions/{match.id}", data={"home": home, "away": away, "back": league_url})
    # The matches are played: results arrive through the sync.
    for match, (home, away) in [(exact, (2, 1)), (outcome, (3, 0)), (miss, (1, 0))]:
        match.status, match.home_score, match.away_score = "FINISHED", home, away
    db.commit()

    page = client.get(league_url).text
    assert "<td>michal</td><td>4</td>" in page.replace("\n", "").replace(" ", "")
