from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .analytics import build_insights, build_recommendations, build_weekly_report, duration_hours
from .config import settings
from .db import Base, engine, get_db
from .models import Profile, RecommendationProgress, SessionToken, SleepEntry, User
from .schemas import (
    AuthPayload,
    AuthResponse,
    ChatRequest,
    ChatResponse,
    Dashboard,
    ProfileRead,
    SleepEntryCreate,
    SleepEntryRead,
    SleepEntryUpdate,
    WeeklyReport,
)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        actual = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
        return secrets.compare_digest(actual.hex(), digest_hex)
    except ValueError:
        return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
    yield


app = FastAPI(title="SleepPilot API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_entry(entry: SleepEntry) -> SleepEntryRead:
    return SleepEntryRead.model_validate({**entry.__dict__, "duration_hours": duration_hours(entry)})


def profile_for_user(db: Session, user: User) -> Profile:
    profile = user.profile
    if not profile:
        profile = Profile(user_id=user.id, name=user.email.split("@")[0].title())
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def current_user(authorization: str | None, db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = db.get(SessionToken, authorization.removeprefix("Bearer ").strip())
    if not token or token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    return current_user(authorization, db)


def auth_response(db: Session, user: User) -> AuthResponse:
    token = secrets.token_urlsafe(36)
    db.add(SessionToken(token=token, user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=30)))
    db.commit()
    return AuthResponse(token=token, profile=profile_for_user(db, user))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: AuthPayload, db: Session = Depends(get_db)) -> AuthResponse:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_response(db, user)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: AuthPayload, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return auth_response(db, user)


@app.post("/api/auth/demo", response_model=AuthResponse)
def demo_login(db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == "demo@sleeppilot.local"))
    if not user:
        user = User(email="demo@sleeppilot.local", password_hash=hash_password("demo"))
        db.add(user)
        db.commit()
        db.refresh(user)
    profile = profile_for_user(db, user)
    if not db.scalar(select(SleepEntry).where(SleepEntry.profile_id == profile.id)):
        seed_entries(db, profile)
    return auth_response(db, user)


@app.get("/api/profile", response_model=ProfileRead)
def profile(user: User = Depends(get_user), db: Session = Depends(get_db)) -> Profile:
    return profile_for_user(db, user)


@app.get("/api/entries", response_model=list[SleepEntryRead])
def entries(limit: int = Query(default=60, ge=1, le=100), user: User = Depends(get_user), db: Session = Depends(get_db)) -> list[SleepEntryRead]:
    profile = profile_for_user(db, user)
    records = db.scalars(select(SleepEntry).where(SleepEntry.profile_id == profile.id).order_by(SleepEntry.entry_date.desc()).limit(limit)).all()
    return [serialize_entry(entry) for entry in records]


@app.post("/api/entries", response_model=SleepEntryRead, status_code=201)
def create_entry(payload: SleepEntryCreate, user: User = Depends(get_user), db: Session = Depends(get_db)) -> SleepEntryRead:
    profile = profile_for_user(db, user)
    entry = SleepEntry(profile_id=profile.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serialize_entry(entry)


@app.put("/api/entries/{entry_id}", response_model=SleepEntryRead)
def update_entry(entry_id: int, payload: SleepEntryUpdate, user: User = Depends(get_user), db: Session = Depends(get_db)) -> SleepEntryRead:
    profile = profile_for_user(db, user)
    entry = db.scalar(select(SleepEntry).where(SleepEntry.id == entry_id, SleepEntry.profile_id == profile.id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for key, value in payload.model_dump().items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return serialize_entry(entry)


@app.delete("/api/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)) -> None:
    profile = profile_for_user(db, user)
    entry = db.scalar(select(SleepEntry).where(SleepEntry.id == entry_id, SleepEntry.profile_id == profile.id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


def seed_entries(db: Session, profile: Profile) -> None:
    now = datetime.now(timezone.utc)
    for days_ago, duration, quality, caffeine, screens, activity, mood in [
        (0, 7.8, 4, 80, 45, 35, 4), (1, 6.6, 3, 220, 130, 10, 3),
        (2, 8.2, 5, 40, 30, 50, 5), (3, 7.1, 4, 120, 75, 30, 4),
        (4, 6.3, 2, 280, 180, 5, 2), (5, 7.9, 4, 60, 50, 45, 4),
        (6, 8.0, 5, 0, 25, 60, 5),
    ]:
        bedtime = now - timedelta(days=days_ago + 1, hours=duration)
        wake_time = bedtime + timedelta(hours=duration)
        db.add(SleepEntry(profile_id=profile.id, entry_date=(now - timedelta(days=days_ago)).date(), bedtime=bedtime, wake_time=wake_time, sleep_quality=quality, caffeine_mg=caffeine, screen_minutes=screens, activity_minutes=activity, mood=mood))
    db.commit()


@app.post("/api/demo/seed", response_model=list[SleepEntryRead])
def seed_demo(user: User = Depends(get_user), db: Session = Depends(get_db)) -> list[SleepEntryRead]:
    profile = profile_for_user(db, user)
    db.query(SleepEntry).filter(SleepEntry.profile_id == profile.id).delete()
    db.commit()
    seed_entries(db, profile)
    records = db.scalars(select(SleepEntry).where(SleepEntry.profile_id == profile.id).order_by(SleepEntry.entry_date.asc())).all()
    return [serialize_entry(entry) for entry in records]


@app.post("/api/recommendations/{title}/complete", response_model=dict[str, bool])
def complete_recommendation(title: str, user: User = Depends(get_user), db: Session = Depends(get_db)) -> dict[str, bool]:
    profile = profile_for_user(db, user)
    progress = db.scalar(select(RecommendationProgress).where(RecommendationProgress.profile_id == profile.id, RecommendationProgress.title == title))
    if not progress:
        progress = RecommendationProgress(profile_id=profile.id, title=title)
        db.add(progress)
    progress.completed = not progress.completed
    db.commit()
    return {"completed": progress.completed}


@app.get("/api/dashboard", response_model=Dashboard)
def dashboard(user: User = Depends(get_user), db: Session = Depends(get_db)) -> Dashboard:
    profile = profile_for_user(db, user)
    records = db.scalars(select(SleepEntry).where(SleepEntry.profile_id == profile.id).order_by(SleepEntry.entry_date.asc())).all()
    serialized = [serialize_entry(entry) for entry in records]
    durations = [item.duration_hours for item in serialized]
    qualities = [item.sleep_quality for item in serialized]
    moods = [item.mood for item in serialized]
    completed = set(db.scalars(select(RecommendationProgress.title).where(RecommendationProgress.profile_id == profile.id, RecommendationProgress.completed.is_(True))).all())
    recommendations = build_recommendations(records, profile.target_sleep_hours, completed)
    goal_progress = min(100, round((sum(durations) / len(durations) / profile.target_sleep_hours) * 100)) if durations else 0
    return Dashboard(profile=profile, entries=serialized, average_duration=round(sum(durations) / len(durations), 1) if durations else 0, average_quality=round(sum(qualities) / len(qualities), 1) if qualities else 0, average_mood=round(sum(moods) / len(moods), 1) if moods else 0, sleep_consistency=round(max(0, 100 - (max(durations) - min(durations)) * 20)) if durations else 0, insights=build_insights(records), recommendations=recommendations, goal_progress=goal_progress)


@app.get("/api/reports/weekly", response_model=WeeklyReport)
def weekly_report(user: User = Depends(get_user), db: Session = Depends(get_db)) -> WeeklyReport:
    profile = profile_for_user(db, user)
    records = db.scalars(select(SleepEntry).where(SleepEntry.profile_id == profile.id)).all()
    return build_weekly_report(records, profile.target_sleep_hours)


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: User = Depends(get_user), db: Session = Depends(get_db)) -> ChatResponse:
    profile = profile_for_user(db, user)
    records = db.scalars(select(SleepEntry).where(SleepEntry.profile_id == profile.id).order_by(SleepEntry.entry_date.desc()).limit(30)).all()
    if not records:
        return ChatResponse(answer="Add a few nights to your diary so I can answer questions about your habits.", source="local")
    avg_duration = sum(duration_hours(item) for item in records) / len(records)
    avg_quality = sum(item.sleep_quality for item in records) / len(records)
    avg_screen = sum(item.screen_minutes for item in records) / len(records)
    avg_caffeine = sum(item.caffeine_mg for item in records) / len(records)
    message = payload.message.lower()
    if any(word in message for word in ("caffeine", "coffee")):
        answer = f"Across your last {len(records)} entries, you averaged {avg_caffeine:.0f} mg of caffeine. Track the trend: try avoiding caffeine after 2 PM for 3–5 days and compare the result."
    elif any(word in message for word in ("screen", "phone")):
        answer = f"You average {avg_screen:.0f} minutes of screen time. Compare a week with screens limited 45–60 minutes before bed; this is a safe experiment, not a medical diagnosis."
    elif any(word in message for word in ("why", "poor", "bad")):
        answer = f"Your averages are {avg_duration:.1f} h of sleep and a quality score of {avg_quality:.1f}/5. Start with sleep timing, late caffeine, and screens; your current data shows association, not causation."
    else:
        answer = f"Based on your diary: {avg_duration:.1f} h of sleep, quality {avg_quality:.1f}/5. Ask about caffeine, screens, or poor sleep and I will answer from your entries."
    return ChatResponse(answer=answer, source="local")
