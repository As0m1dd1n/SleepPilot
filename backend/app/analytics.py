from statistics import mean, pstdev

from .models import SleepEntry
from .schemas import Insight, Recommendation, WeeklyReport


def duration_hours(entry: SleepEntry) -> float:
    return round((entry.wake_time - entry.bedtime).total_seconds() / 3600, 1)


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    x_mean, y_mean = mean(xs), mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = (sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys)) ** 0.5
    return round(numerator / denominator, 2) if denominator else 0.0


def build_insights(entries: list[SleepEntry]) -> list[Insight]:
    if not entries:
        return []
    quality = [entry.sleep_quality for entry in entries]
    durations = [duration_hours(entry) for entry in entries]
    caffeine = [entry.caffeine_mg for entry in entries]
    screens = [entry.screen_minutes for entry in entries]
    return [
        Insight(label="Average duration", value=f"{mean(durations):.1f} h", detail="Most adults need about 7–9 hours.", tone="good" if 7 <= mean(durations) <= 9 else "warning"),
        Insight(label="Caffeine and quality", value=f"{_corr(caffeine, quality):+.2f}", detail="A negative value means more caffeine often coincides with a lower rating.", tone="neutral"),
        Insight(label="Screens and quality", value=f"{_corr(screens, quality):+.2f}", detail="This is an association, not proof of causation.", tone="neutral"),
        Insight(label="Consistency", value=f"{pstdev(durations):.1f} h", detail="Variation in sleep duration between days.", tone="good" if pstdev(durations) < 1 else "warning"),
    ]


def build_recommendations(entries: list[SleepEntry], target_hours: float, completed_titles: set[str] | None = None) -> list[Recommendation]:
    completed_titles = completed_titles or set()
    if not entries:
        return [Recommendation(title="Start your diary", text="Add a few nights so SleepPilot can find your personal patterns.", completed="Start your diary" in completed_titles)]
    recommendations: list[Recommendation] = []
    avg_duration = mean(duration_hours(entry) for entry in entries)
    avg_screen = mean(entry.screen_minutes for entry in entries)
    late_caffeine = sum(entry.caffeine_mg > 150 for entry in entries)
    if avg_duration < target_hours - 0.5:
        recommendations.append(Recommendation(title="Protect your sleep window", text=f"Your average sleep is {avg_duration:.1f} h. Try moving bedtime 20–30 minutes earlier.", priority="high", completed="Protect your sleep window" in completed_titles))
    if avg_screen > 90:
        recommendations.append(Recommendation(title="Create a digital sunset", text=f"You average {avg_screen:.0f} minutes of screen time. Put away bright screens 45–60 minutes before bed.", priority="normal", completed="Create a digital sunset" in completed_titles))
    if late_caffeine:
        recommendations.append(Recommendation(title="Move caffeine earlier", text=f"On {late_caffeine} out of {len(entries)} days, caffeine intake was high. Try avoiding caffeine after 2 PM.", priority="normal", completed="Move caffeine earlier" in completed_titles))
    if not recommendations:
        recommendations.append(Recommendation(title="Keep your rhythm", text="Your baseline habits look steady. Keep a similar wake-up time on weekends.", completed="Keep your rhythm" in completed_titles))
    return recommendations


def build_weekly_report(entries: list[SleepEntry], target_hours: float) -> WeeklyReport:
    from datetime import date, timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    recent = [entry for entry in entries if start_date <= entry.entry_date <= end_date]
    durations = [duration_hours(entry) for entry in recent]
    qualities = [entry.sleep_quality for entry in recent]
    best = max(recent, key=lambda item: item.sleep_quality, default=None)
    average_duration = mean(durations) if durations else 0
    average_quality = mean(qualities) if qualities else 0
    focus = "Try adding more entries" if not recent else ("Increase sleep time" if average_duration < target_hours - 0.5 else "Maintain your current rhythm")
    summary = "There are no entries for this week yet." if not recent else f"You logged {len(recent)} nights. Average sleep is {average_duration:.1f} h, with a quality score of {average_quality:.1f}/5."
    return WeeklyReport(start_date=start_date, end_date=end_date, nights_logged=len(recent), average_duration=round(average_duration, 1), average_quality=round(average_quality, 1), best_day=best.entry_date.isoformat() if best else None, focus=focus, summary=summary)
