from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    target_sleep_hours: float


class AuthPayload(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=4, max_length=128)


class AuthResponse(BaseModel):
    token: str
    profile: ProfileRead


class SleepEntryCreate(BaseModel):
    entry_date: date
    bedtime: datetime
    wake_time: datetime
    sleep_quality: int = Field(ge=1, le=5)
    caffeine_mg: int = Field(default=0, ge=0, le=2000)
    screen_minutes: int = Field(default=0, ge=0, le=1440)
    activity_minutes: int = Field(default=0, ge=0, le=1440)
    mood: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_times(self) -> "SleepEntryCreate":
        if self.wake_time <= self.bedtime:
            raise ValueError("wake_time must be later than bedtime")
        return self


class SleepEntryRead(SleepEntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    profile_id: int
    duration_hours: float


class SleepEntryUpdate(SleepEntryCreate):
    pass


class Insight(BaseModel):
    label: str
    value: str
    detail: str
    tone: str = "neutral"


class Recommendation(BaseModel):
    title: str
    text: str
    priority: str = "normal"
    completed: bool = False


class Dashboard(BaseModel):
    profile: ProfileRead
    entries: list[SleepEntryRead]
    average_duration: float
    average_quality: float
    average_mood: float
    sleep_consistency: float
    insights: list[Insight]
    recommendations: list[Recommendation]
    goal_progress: float


class WeeklyReport(BaseModel):
    start_date: date
    end_date: date
    nights_logged: int
    average_duration: float
    average_quality: float
    best_day: str | None
    focus: str
    summary: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    source: str
