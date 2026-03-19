"""AI 学习建议服务 — 根据近期活动和待复习项生成学习建议"""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm.client import OpenRouterClient
from db.models import ReviewSchedule, Space, StudyActivityLog

logger = logging.getLogger(__name__)

# ── In-memory cache ──
# Key: (user_id_str, slot_str) → {"result": dict, "expires": datetime}
# Slots (CST UTC+8): 00:00-07:59→prev_day_21, 08:00-11:59→today_08,
#                    12:00-17:59→today_12, 18:00-20:59→today_18, 21:00-23:59→today_21
_suggestion_cache: dict[tuple[str, str], dict] = {}
_MAX_CACHE_ENTRIES = 5000
_CST = timezone(timedelta(hours=8))
_UPDATE_HOURS_CST = [8, 12, 18, 21]


def _get_slot_info() -> tuple[str, datetime]:
    """返回 (当前槽标识符, 下次更新UTC时间)"""
    now_cst = datetime.now(_CST)
    today = now_cst.date()
    current_hour = now_cst.hour

    current_slot_hour = None
    for h in _UPDATE_HOURS_CST:
        if current_hour >= h:
            current_slot_hour = h

    if current_slot_hour is None:
        yesterday = today - timedelta(days=1)
        slot_str = f"{yesterday.strftime('%Y%m%d')}_21"
        next_dt = datetime(today.year, today.month, today.day, 8, 0, 0, tzinfo=_CST)
    else:
        slot_str = f"{today.strftime('%Y%m%d')}_{current_slot_hour:02d}"
        future = [h for h in _UPDATE_HOURS_CST if h > current_slot_hour]
        if future:
            next_dt = datetime(today.year, today.month, today.day, future[0], 0, 0, tzinfo=_CST)
        else:
            tomorrow = today + timedelta(days=1)
            next_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0, tzinfo=_CST)

    return slot_str, next_dt.astimezone(timezone.utc)


_PREFERENCE_LABELS: dict[str, str] = {
    "university": "大学课程",
    "quick": "快速掌握",
    "solid": "扎实学习",
    "hobby": "兴趣爱好",
    "exam": "应对考试",
    "work": "工作技能",
    "research": "学术研究",
    "practice": "动手实践",
}

SYSTEM_PROMPT = """\
你是 uStudy 学习助手。根据用户最近的学习活动和待复习项，给出一条学习建议。

规则：
- 如果有逾期或到期的复习项，优先建议复习
- 否则建议继续最近学过的科目
- 参考复习项的学习偏好（如有）决定是否建议复习，并给出更贴合的指引
- 如果学习偏好是"快速掌握"，该项通常不需要复习
- decision 必须是："继续学习" 或 "开始复习"
- subject 是具体的科目/主题名称
- guidance 是一句极简的学习指引（不超过20字）

以严格 JSON 格式输出：
{"decision": "继续学习|开始复习", "subject": "科目名", "guidance": "一句话"}\
"""


def _build_user_prompt(
    activities: list[StudyActivityLog],
    due_reviews: list[tuple[ReviewSchedule, StudyActivityLog, dict | None]],
) -> str:
    """构建用户 prompt（动态部分）"""
    lines: list[str] = []
    today = datetime.now(timezone.utc).date()

    if activities:
        lines.append("## 最近学习活动（最近2天）")
        for i, a in enumerate(activities, 1):
            depth = f", {a.study_depth}" if a.study_depth else ""
            subject = f", {a.subject_name}" if a.subject_name else ""
            lines.append(
                f"{i}. [{a.activity_date}] {a.title} "
                f"({a.activity_type}{subject}{depth})"
            )
        lines.append("")

    if due_reviews:
        lines.append("## 今日待复习项")
        for i, (r, activity, prefs) in enumerate(due_reviews, 1):
            overdue_days = (today - r.scheduled_date).days
            overdue_str = (
                f"逾期{overdue_days}天" if overdue_days > 0 else "今日到期"
            )
            depth = f", {r.study_depth}" if r.study_depth else ""

            pref_str = ""
            if isinstance(prefs, dict):
                preset_ids = prefs.get("preset_preferences", [])
                labels = []
                for pid in preset_ids:
                    label = _PREFERENCE_LABELS.get(pid)
                    if label:
                        labels.append(label)
                    else:
                        logger.warning("Unknown preset preference ID: %s", pid)
                custom = prefs.get("custom_preference", "")
                if custom:
                    labels.append(custom)
                if labels:
                    pref_str = f", 偏好: {'/'.join(labels)}"

            lines.append(
                f"{i}. {activity.title} "
                f"(复习第{r.review_number}次, {overdue_str}{depth}{pref_str})"
            )

    return "\n".join(lines)


def _parse_suggestion_json(response: str) -> dict | None:
    """3-level fallback JSON parser (matches codebase convention)."""
    # 1. Direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Loose brace extraction
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse suggestion JSON: %s", response[:200])
    return None


def _heuristic_suggestion(
    activities: list[StudyActivityLog],
    due_reviews: list[tuple[ReviewSchedule, StudyActivityLog]],
) -> dict:
    """Fallback: mirrors the existing Vue computed logic."""
    if due_reviews:
        _r, activity = due_reviews[0]
        return {
            "decision": "开始复习",
            "subject": activity.title,
            "guidance": "巩固已学内容，提升长期记忆",
            "title": f"建议复习: {activity.title}",
            "source": "heuristic",
        }

    if activities:
        a = activities[0]
        name = a.subject_name or a.title
        return {
            "decision": "继续学习",
            "subject": name,
            "guidance": "保持学习节奏，完成今日目标",
            "title": f"继续学习: {name}",
            "source": "heuristic",
        }

    return {
        "decision": "继续学习",
        "subject": "新知识",
        "guidance": "保持学习节奏，每天进步一点点",
        "title": "开始今天的学习吧",
        "source": "heuristic",
    }


def _get_cached(user_id: UUID) -> dict | None:
    """Return cached result if still valid (within current time slot)."""
    slot_str, _ = _get_slot_info()
    key = (str(user_id), slot_str)
    entry = _suggestion_cache.get(key)
    if entry and datetime.now(timezone.utc) < entry["expires"]:
        return entry["result"]
    return None


def _set_cache(user_id: UUID, result: dict) -> None:
    if len(_suggestion_cache) >= _MAX_CACHE_ENTRIES:
        _suggestion_cache.pop(next(iter(_suggestion_cache)), None)
    slot_str, next_update_utc = _get_slot_info()
    key = (str(user_id), slot_str)
    _suggestion_cache[key] = {
        "result": result,
        "generated_at": datetime.now(timezone.utc),
        "expires": next_update_utc,
    }


async def _fetch_recent_activities(
    user_id: UUID, db: AsyncSession
) -> list[StudyActivityLog]:
    """Fetch last 2 days of activities, limit 20."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=1)
    result = await db.execute(
        select(StudyActivityLog)
        .where(
            StudyActivityLog.user_id == user_id,
            StudyActivityLog.activity_date >= cutoff,
        )
        .order_by(StudyActivityLog.activity_time.desc())
        .limit(20)
    )
    return list(result.scalars().all())


async def _fetch_due_reviews(
    user_id: UUID, db: AsyncSession
) -> list[tuple[ReviewSchedule, StudyActivityLog, dict | None]]:
    """Fetch due/overdue reviews deduped by activity_id, limit 10.

    Returns:
        List of (ReviewSchedule, StudyActivityLog, learning_preferences) tuples.
    """
    today = datetime.now(timezone.utc).date()
    ranked_due_reviews = (
        select(
            ReviewSchedule.id.label("review_id"),
            func.row_number()
            .over(
                partition_by=ReviewSchedule.activity_id,
                order_by=(
                    ReviewSchedule.scheduled_date.asc(),
                    ReviewSchedule.review_number.asc(),
                    ReviewSchedule.id.asc(),
                ),
            )
            .label("rn"),
        )
        .where(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.status == "pending",
            ReviewSchedule.scheduled_date <= today,
        )
        .subquery()
    )

    result = await db.execute(
        select(ReviewSchedule, StudyActivityLog, Space.learning_preferences)
        .join(ranked_due_reviews, ReviewSchedule.id == ranked_due_reviews.c.review_id)
        .join(StudyActivityLog, ReviewSchedule.activity_id == StudyActivityLog.id)
        .outerjoin(Space, StudyActivityLog.space_id == Space.id)
        .where(ranked_due_reviews.c.rn == 1)
        .order_by(ReviewSchedule.scheduled_date.asc())
        .limit(10)
    )
    rows = result.all()
    # Eagerly load attributes to avoid lazy-load after session close
    for r, a, _prefs in rows:
        _ = (r.review_number, r.scheduled_date, r.study_depth, a.title)
    return list(rows)


async def get_ai_suggestion(
    user_id: UUID,
    db: AsyncSession,
    force_refresh: bool = False,
) -> dict:
    """
    Main entry point: returns a study suggestion dict with keys:
    decision, subject, guidance, title, source
    """
    # Check cache (valid within current time slot)
    if not force_refresh:
        cached = _get_cached(user_id)
        if cached:
            return cached

    # Cache expired or force refresh → regenerate
    activities = await _fetch_recent_activities(user_id, db)
    due_reviews = await _fetch_due_reviews(user_id, db)
    plain_reviews = [(r, a) for r, a, _prefs in due_reviews]

    # No data at all → heuristic immediately
    if not activities and not plain_reviews:
        result = _heuristic_suggestion(activities, plain_reviews)
        _set_cache(user_id, result)
        return result

    # Build prompt and call LLM
    user_prompt = _build_user_prompt(activities, due_reviews)
    try:
        from config import get_settings
        _settings = get_settings()
        client = OpenRouterClient(model_override=_settings.suggestion_model or None)
        raw = await client.complete(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=256,
        )
        parsed = _parse_suggestion_json(raw)
        if parsed and "decision" in parsed and "subject" in parsed:
            result = {
                "decision": parsed["decision"],
                "subject": parsed["subject"],
                "guidance": parsed.get("guidance", ""),
                "title": f"{parsed['decision']}: {parsed['subject']}",
                "source": "ai",
            }
            _set_cache(user_id, result)
            return result

        logger.warning("LLM returned incomplete suggestion: %s", parsed)
    except Exception:
        logger.exception("LLM suggestion call failed, using heuristic")

    # Fallback
    result = _heuristic_suggestion(activities, plain_reviews)
    _set_cache(user_id, result)
    return result
