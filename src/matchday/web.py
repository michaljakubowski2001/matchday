import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from matchday.config import Settings, get_settings
from matchday.db import get_session
from matchday.models import League, Match, Membership, Prediction, User
from matchday.scoring import points
from matchday.security import hash_password, verify_password

HERE = Path(__file__).parent
DbSession = Annotated[Session, Depends(get_session)]


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Matchday", docs_url=None, redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.secure_cookies,
        same_site="lax",
        max_age=30 * 24 * 3600,
    )
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    local_tz = ZoneInfo(settings.timezone)
    templates.env.filters["local"] = lambda value: value.astimezone(local_tz).strftime("%d.%m %H:%M")

    def current_user(request: Request, session: DbSession) -> User | None:
        user_id = request.session.get("user_id")
        return session.get(User, user_id) if user_id else None

    def require_user(user: Annotated[User | None, Depends(current_user)]) -> User:
        if user is None:
            raise HTTPException(status_code=303, headers={"Location": "/login"})
        return user

    CurrentUser = Annotated[User, Depends(require_user)]

    def user_leagues(session: Session, user: User) -> list[League]:
        query = select(League).join(Membership).where(Membership.user_id == user.id).order_by(League.name)
        return list(session.scalars(query))

    def render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    # --- probes -----------------------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(session: DbSession) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ready"}

    # --- accounts ---------------------------------------------------------------------------------

    @app.get("/register")
    def register_form(request: Request):
        return render(request, "auth.html", mode="register")

    @app.post("/register")
    def register(
        request: Request,
        session: DbSession,
        username: Annotated[str, Form(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")],
        password: Annotated[str, Form(min_length=8, max_length=128)],
    ):
        user = User(username=username, password_hash=hash_password(password))
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return render(request, "auth.html", 409, mode="register", error="Ta nazwa jest już zajęta.")
        request.session["user_id"] = user.id
        return redirect("/")

    @app.get("/login")
    def login_form(request: Request):
        return render(request, "auth.html", mode="login")

    @app.post("/login")
    def login(
        request: Request,
        session: DbSession,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ):
        user = session.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(user.password_hash, password):
            return render(request, "auth.html", 401, mode="login", error="Zły login lub hasło.")
        request.session.clear()
        request.session["user_id"] = user.id
        return redirect("/")

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return redirect("/login")

    # --- leagues ----------------------------------------------------------------------------------

    @app.get("/")
    def index(request: Request, session: DbSession, user: Annotated[User | None, Depends(current_user)]):
        if user is None:
            return redirect("/login")
        return render(request, "index.html", user=user, leagues=user_leagues(session, user))

    @app.post("/leagues")
    def create_league(
        session: DbSession, user: CurrentUser, name: Annotated[str, Form(min_length=1, max_length=64)]
    ):
        league = League(name=name, invite_code=secrets.token_urlsafe(6), owner_id=user.id)
        session.add(league)
        session.flush()
        session.add(Membership(league_id=league.id, user_id=user.id))
        session.commit()
        return redirect(f"/leagues/{league.id}")

    @app.post("/leagues/join")
    def join_league(
        request: Request, session: DbSession, user: CurrentUser, code: Annotated[str, Form(max_length=16)]
    ):
        league = session.scalar(select(League).where(League.invite_code == code.strip()))
        if league is None:
            return render(
                request,
                "index.html",
                404,
                user=user,
                leagues=user_leagues(session, user),
                error="Nie ma ligi z tym kodem.",
            )
        if not session.scalar(select(Membership).filter_by(league_id=league.id, user_id=user.id)):
            session.add(Membership(league_id=league.id, user_id=user.id))
            session.commit()
        return redirect(f"/leagues/{league.id}")

    @app.get("/leagues/{league_id}")
    def league_page(request: Request, league_id: int, session: DbSession, user: CurrentUser):
        league = session.get(League, league_id)
        member_ids = [m.user_id for m in league.members] if league else []
        if league is None or user.id not in member_ids:
            raise HTTPException(status_code=404)

        matches = session.scalars(select(Match).order_by(Match.kickoff)).all()
        predictions = session.scalars(
            select(Prediction)
            .where(Prediction.user_id.in_(member_ids))
            .options(selectinload(Prediction.match))
        ).all()
        mine = {p.match_id: p for p in predictions if p.user_id == user.id}

        totals = {m.user.username: 0 for m in league.members}
        names = {m.user_id: m.user.username for m in league.members}
        for prediction in predictions:
            if prediction.match.finished:
                totals[names[prediction.user_id]] += points(
                    (prediction.home_score, prediction.away_score),
                    (prediction.match.home_score, prediction.match.away_score),
                )
        table = sorted(totals.items(), key=lambda row: (-row[1], row[0]))

        now = datetime.now(UTC)
        return render(
            request,
            "league.html",
            user=user,
            league=league,
            table=table,
            upcoming=[m for m in matches if m.kickoff > now],
            played=[m for m in matches if m.finished][::-1],
            mine=mine,
            points=points,
        )

    # --- predictions ------------------------------------------------------------------------------

    @app.post("/predictions/{match_id}")
    def predict(
        match_id: int,
        session: DbSession,
        user: CurrentUser,
        home: Annotated[int, Form(ge=0, le=20)],
        away: Annotated[int, Form(ge=0, le=20)],
        back: Annotated[str, Form(pattern=r"^/leagues/\d+$")],
    ):
        match = session.get(Match, match_id)
        if match is None:
            raise HTTPException(status_code=404)
        if match.kickoff <= datetime.now(UTC):
            raise HTTPException(status_code=409, detail="Mecz już się rozpoczął.")
        prediction = session.scalar(select(Prediction).filter_by(user_id=user.id, match_id=match.id))
        if prediction is None:
            session.add(Prediction(user_id=user.id, match_id=match.id, home_score=home, away_score=away))
        else:
            prediction.home_score, prediction.away_score = home, away
        session.commit()
        return redirect(back)

    return app
