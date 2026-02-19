"""Assessment score computation + DB query services."""

import math
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation, DailyStudyRecord, Edge, EdgeType, Message, MessageRole, Node, QuizAttempt, ReviewSchedule, Space


# ============ Pure Functions (no DB, easy to test) ============


def compute_continuity_score(d: int, g: int) -> float:
    """
    Compute continuity score (0-100) using Hill function (S-shaped saturation).

    Args:
        d: cumulative active days
        g: effective gap days (after reset rules)

    Returns:
        Score between 0 and 100, rounded to 1 decimal.
    """
    if d <= 0:
        return 0.0

    dp = d ** 1.807
    base = 100 * dp / (dp + 1.5)

    if g > 0:
        penalty = min(base, 40 * (1 - math.exp(-0.15 * g)))
    else:
        penalty = 0.0

    score = base - penalty
    return round(max(0.0, min(100.0, score)), 1)


def compute_continuity_state(study_dates: list[date]) -> dict:
    """
    Derive continuity metrics from a sorted list of study dates.

    Args:
        study_dates: List of dates the user was active (ascending order).

    Returns:
        Dict with keys: cumulative_active_days, effective_gap_days,
        current_streak, last_gap, score, reset_threshold.
    """
    reset_threshold = 4

    if not study_dates:
        return {
            "cumulative_active_days": 0,
            "effective_gap_days": 0,
            "current_streak": 0,
            "last_gap": 0,
            "score": 0.0,
            "reset_threshold": reset_threshold,
        }

    date_set = set(study_dates)
    d = len(date_set)
    today = date.today()

    # Calculate current_streak: consecutive days ending at today (or yesterday)
    current_streak = 0
    check_date = today
    # If today is not active, start from yesterday
    if check_date not in date_set:
        check_date = today - timedelta(days=1)
        if check_date not in date_set:
            # Not active today or yesterday -> streak = 0
            # g = days since last active date
            sorted_dates = sorted(date_set)
            last_active = sorted_dates[-1]
            g = (today - last_active).days
            score = compute_continuity_score(d, g)
            return {
                "cumulative_active_days": d,
                "effective_gap_days": g,
                "current_streak": 0,
                "last_gap": g,
                "score": score,
                "reset_threshold": reset_threshold,
            }

    while check_date in date_set:
        current_streak += 1
        check_date -= timedelta(days=1)

    # At this point, today or yesterday is guaranteed to be in date_set
    # (the early return above handles the case where neither is active).
    streak_start = today - timedelta(days=current_streak - 1)
    if today not in date_set:
        streak_start = (today - timedelta(days=1)) - timedelta(days=current_streak - 1)

    # The day before the streak started
    day_before_streak = streak_start - timedelta(days=1)

    # Find last_gap: gap length before the current streak
    min_date = min(date_set)
    if day_before_streak in date_set:
        # No gap before this streak
        last_gap = 0
    else:
        # Walk backwards to find last active day before gap
        gap_end = day_before_streak
        scan = gap_end
        while scan not in date_set and scan >= min_date:
            scan -= timedelta(days=1)

        if scan in date_set:
            last_gap = (gap_end - scan).days
        else:
            # No previous activity before gap — first session
            last_gap = 0

    # Apply reset rule
    if current_streak >= reset_threshold:
        g = 0  # Gap cleared
    else:
        g = last_gap

    score = compute_continuity_score(d, g)

    return {
        "cumulative_active_days": d,
        "effective_gap_days": g,
        "current_streak": current_streak,
        "last_gap": last_gap,
        "score": score,
        "reset_threshold": reset_threshold,
    }


def split_into_sessions(
    messages: list[dict], threshold_minutes: int = 30
) -> list[list[dict]]:
    """
    Split chronologically-sorted user messages into study sessions.

    A new session begins when the gap between consecutive messages
    is >= threshold_minutes.

    Args:
        messages: List of dicts with at least a "created_at" (datetime) key,
                  sorted ascending by created_at.
        threshold_minutes: Gap (in minutes) that triggers a new session.

    Returns:
        List of sessions, where each session is a list of message dicts.
    """
    if not messages:
        return []

    threshold = timedelta(minutes=threshold_minutes)
    sessions: list[list[dict]] = [[messages[0]]]

    for msg in messages[1:]:
        gap = msg["created_at"] - sessions[-1][-1]["created_at"]
        if gap >= threshold:
            sessions.append([msg])
        else:
            sessions[-1].append(msg)

    return sessions


def compute_focus_score(sessions: list[list[dict]]) -> dict:
    """
    Compute focus score (0-100) from study sessions.

    Uses three factors:
    - depth_score (40%): avg user messages per session (Hill function)
    - duration_score (35%): avg session duration in minutes (Hill function)
    - rhythm_score (25%): proportion of inter-message gaps in [30s, 300s]

    Args:
        sessions: List of sessions, each a list of message dicts with
                  "created_at" (datetime) and "role" (str) keys.

    Returns:
        Dict with score, avg_session_depth, avg_session_duration_min,
        rhythm_score, total_sessions.
    """
    if not sessions:
        return {
            "score": 0.0,
            "total_sessions": 0,
            "avg_session_depth": 0.0,
            "avg_session_duration_min": 0.0,
            "rhythm_score": 0.0,
        }

    # Filter to sessions that contain at least one user message
    valid_sessions = [
        s for s in sessions
        if any(m["role"] == "user" for m in s)
    ]

    if not valid_sessions:
        return {
            "score": 0.0,
            "total_sessions": 0,
            "avg_session_depth": 0.0,
            "avg_session_duration_min": 0.0,
            "rhythm_score": 0.0,
        }

    # Factor 1: Depth — avg user messages per session
    depths = [
        sum(1 for m in s if m["role"] == "user")
        for s in valid_sessions
    ]
    avg_depth = sum(depths) / len(depths)
    d = avg_depth
    depth_score = 100 * d ** 1.5 / (d ** 1.5 + 5 ** 1.5)

    # Factor 2: Duration — avg session length in minutes
    durations = []
    for s in valid_sessions:
        duration_sec = (s[-1]["created_at"] - s[0]["created_at"]).total_seconds()
        durations.append(duration_sec / 60.0)
    avg_duration = sum(durations) / len(durations)
    t = avg_duration
    duration_score = 100 * t ** 2 / (t ** 2 + 12 ** 2) if t > 0 else 0.0

    # Factor 3: Rhythm — proportion of user-message gaps in [30s, 300s]
    optimal_count = 0
    total_gaps = 0
    for s in valid_sessions:
        user_msgs = [m for m in s if m["role"] == "user"]
        for i in range(1, len(user_msgs)):
            gap_sec = (
                user_msgs[i]["created_at"] - user_msgs[i - 1]["created_at"]
            ).total_seconds()
            total_gaps += 1
            if 30 <= gap_sec <= 300:
                optimal_count += 1

    rhythm = (optimal_count / total_gaps * 100) if total_gaps > 0 else 0.0

    score = 0.40 * depth_score + 0.35 * duration_score + 0.25 * rhythm
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "total_sessions": len(valid_sessions),
        "avg_session_depth": round(avg_depth, 2),
        "avg_session_duration_min": round(avg_duration, 2),
        "rhythm_score": round(rhythm, 1),
    }


def compute_comprehension_score(
    quiz_score_sum: int,
    quiz_total_score_sum: int,
    high_mastery_count: int,
    total_node_count: int,
) -> dict:
    """
    Compute comprehension score (0-100) from quiz accuracy and mastery ratio.

    Args:
        quiz_score_sum: Sum of user's quiz scores.
        quiz_total_score_sum: Sum of quiz total scores (max possible).
        high_mastery_count: Number of nodes with mastery >= 70.
        total_node_count: Total number of nodes (including mastery=NULL).

    Returns:
        Dict with score, quiz_accuracy, mastery_ratio.
    """
    quiz_accuracy = (
        (quiz_score_sum / quiz_total_score_sum * 100)
        if quiz_total_score_sum > 0
        else 0.0
    )

    mastery_ratio = (
        (high_mastery_count / total_node_count * 100)
        if total_node_count > 0
        else 0.0
    )

    score = 0.40 * quiz_accuracy + 0.60 * mastery_ratio
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "quiz_accuracy": round(quiz_accuracy, 1),
        "mastery_ratio": round(mastery_ratio, 1),
    }


def compute_depth_score(
    conv_user_msg_counts: list[int],
    user_message_lengths: list[int],
    avg_mastery: float,
) -> dict:
    """
    Compute depth score (0-100) from three factors.

    Args:
        conv_user_msg_counts: User message count per conversation.
        user_message_lengths: Char lengths of user messages (already filtered >= 10).
        avg_mastery: Average mastery of studied nodes (0-100), 0 if none.

    Returns:
        Dict with score, avg_messages_per_conv, avg_message_length, mastery_score.
    """
    # Factor 1: Conversation depth — avg user messages per conversation
    if conv_user_msg_counts:
        avg_msgs = sum(conv_user_msg_counts) / len(conv_user_msg_counts)
        d = avg_msgs
        conv_depth_score = 100 * d ** 1.5 / (d ** 1.5 + 8 ** 1.5)
    else:
        avg_msgs = 0.0
        conv_depth_score = 0.0

    # Factor 2: Substantiveness — avg user message length
    if user_message_lengths:
        avg_len = sum(user_message_lengths) / len(user_message_lengths)
        substantiveness_score = 100 * avg_len ** 2 / (avg_len ** 2 + 80 ** 2)
    else:
        avg_len = 0.0
        substantiveness_score = 0.0

    # Factor 3: Mastery depth — direct value (already 0-100 scale)
    mastery_score = max(0.0, min(100.0, avg_mastery))

    score = 0.35 * conv_depth_score + 0.30 * substantiveness_score + 0.35 * mastery_score
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "avg_messages_per_conv": round(avg_msgs, 2),
        "avg_message_length": round(avg_len, 2),
        "mastery_score": round(mastery_score, 1),
    }


def compute_knowledge_structure_score(
    parent_solidity_ratios: list[float],
    advanced_edge_count: int,
    total_node_count: int,
) -> dict:
    """
    Compute knowledge structure score (0-100) from solidity and advanced ratio.

    Args:
        parent_solidity_ratios: For each qualifying parent, solid_children / total_children.
        advanced_edge_count: Number of ADVANCED edges.
        total_node_count: Total number of nodes.

    Returns:
        Dict with score, solidity, advanced_ratio.
    """
    solidity = (
        (sum(parent_solidity_ratios) / len(parent_solidity_ratios) * 100)
        if parent_solidity_ratios
        else 0.0
    )

    advanced_ratio = (
        min(advanced_edge_count / total_node_count * 500, 100)
        if total_node_count > 0
        else 0.0
    )

    score = 0.80 * solidity + 0.20 * advanced_ratio
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "solidity": round(solidity, 1),
        "advanced_ratio": round(advanced_ratio, 1),
    }


def compute_review_score(
    completed_count: int,
    overdue_count: int,
    on_time_count: int,
    avg_overdue_days: float,
) -> dict:
    """
    Compute review score (0-100) from completion rate, punctuality, and overdue penalty.

    Args:
        completed_count: Reviews with status='completed'.
        overdue_count: Reviews with status='pending' and scheduled_date <= today.
        on_time_count: Completed reviews where completed_at - scheduled_date <= 2 days.
        avg_overdue_days: Average days overdue for pending reviews past due.

    Returns:
        Dict with score, completion_rate, punctuality_rate, overdue_penalty.
    """
    total_due = completed_count + overdue_count
    if total_due == 0:
        return {
            "score": 0.0,
            "completion_rate": 0.0,
            "punctuality_rate": 0.0,
            "overdue_penalty": 0.0,
        }

    completion_rate = completed_count / total_due * 100
    punctuality_rate = (on_time_count / completed_count * 100) if completed_count > 0 else 0.0

    base = 0.60 * completion_rate + 0.40 * punctuality_rate

    if overdue_count > 0:
        penalty = min(base, 30 * (1 - math.exp(-0.1 * avg_overdue_days)))
    else:
        penalty = 0.0

    score = base - penalty
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "score": score,
        "completion_rate": round(completion_rate, 1),
        "punctuality_rate": round(punctuality_rate, 1),
        "overdue_penalty": round(penalty, 1),
    }


# ============ DB Query Service ============


class ProfileStatsService:
    """Service for profile stats (study days, hours, mastery, coverage)."""

    @staticmethod
    async def get_profile_stats(db: AsyncSession, user_id: UUID) -> dict:
        """
        Compute profile stats: study_days, total_study_hours,
        avg_mastery (non-zero nodes), node_coverage_percent.
        """
        # Query 1: Study days count
        days_result = await db.execute(
            select(func.count())
            .select_from(DailyStudyRecord)
            .where(DailyStudyRecord.user_id == user_id)
        )
        study_days = days_result.scalar_one()

        # Query 2: Real app usage time from heartbeat records
        from usage.models import AppUsageDaily

        usage_result = await db.execute(
            select(func.coalesce(func.sum(AppUsageDaily.total_seconds), 0))
            .where(AppUsageDaily.user_id == user_id)
        )
        total_seconds = usage_result.scalar_one()
        total_study_hours = round(total_seconds / 3600, 1)

        # Query 3: Mastery stats (single query)
        mastery_result = await db.execute(
            select(
                func.avg(Node.mastery).filter(
                    Node.mastery.isnot(None), Node.mastery > 0
                ),
                func.count(Node.id).filter(
                    Node.mastery.isnot(None), Node.mastery > 0
                ),
                func.count(Node.id),
            )
            .join(Space, Node.space_id == Space.id)
            .where(Space.user_id == user_id)
        )
        mastery_row = mastery_result.one()
        avg_mastery = round(float(mastery_row[0]), 1) if mastery_row[0] is not None else 0.0
        nodes_with_mastery = mastery_row[1]
        total_nodes = mastery_row[2]

        node_coverage_percent = (
            round(nodes_with_mastery / total_nodes * 100, 1)
            if total_nodes > 0
            else 0.0
        )

        return {
            "study_days": study_days,
            "total_study_hours": total_study_hours,
            "avg_mastery": avg_mastery,
            "node_coverage_percent": node_coverage_percent,
        }


class ContinuityService:
    """Service for continuity assessment queries."""

    @staticmethod
    async def get_continuity_score(db: AsyncSession, user_id: UUID) -> dict:
        """
        Query study dates and compute continuity score.

        Returns dict with score, cumulative_active_days, effective_gap_days,
        current_streak, last_gap, reset_threshold.
        """
        result = await db.execute(
            select(DailyStudyRecord.study_date)
            .where(DailyStudyRecord.user_id == user_id)
            .order_by(DailyStudyRecord.study_date.asc())
        )
        study_dates = [row[0] for row in result.all()]
        return compute_continuity_state(study_dates)

    @staticmethod
    async def get_calendar(
        db: AsyncSession, user_id: UUID, months: int = 3
    ) -> dict:
        """
        Query activity records for the last N months.

        Returns dict with start_date, end_date, records list.
        """
        today = date.today()
        # Compute start_date as the 1st day of (months-1) months ago
        year = today.year
        month = today.month - (months - 1)
        while month <= 0:
            month += 12
            year -= 1
        start_date = date(year, month, 1)

        result = await db.execute(
            select(DailyStudyRecord.study_date, DailyStudyRecord.activity_count)
            .where(
                DailyStudyRecord.user_id == user_id,
                DailyStudyRecord.study_date >= start_date,
            )
            .order_by(DailyStudyRecord.study_date.asc())
        )
        records = [
            {"date": row[0], "activity_count": row[1]}
            for row in result.all()
        ]
        return {
            "start_date": start_date,
            "end_date": today,
            "records": records,
        }


class FocusService:
    """Service for focus score assessment."""

    @staticmethod
    async def get_focus_score(
        db: AsyncSession, user_id: UUID, week_offset: int = 0
    ) -> dict:
        """
        Compute focus score for a given week.

        Args:
            db: Database session.
            user_id: Current user's ID.
            week_offset: 0 = current week, 1 = last week, etc.

        Returns:
            Dict matching FocusScoreResponse fields.
        """
        today = date.today()
        # Monday of the target week
        current_monday = today - timedelta(days=today.weekday())
        week_start = current_monday - timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)

        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(
            week_end, datetime.max.time()
        )

        result = await db.execute(
            select(Message.role, Message.created_at)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.created_at >= start_dt,
                Message.created_at <= end_dt,
            )
            .order_by(Message.created_at.asc())
        )
        rows = result.all()

        if not rows:
            return {
                "score": 0.0,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_sessions": 0,
                "avg_session_depth": 0.0,
                "avg_session_duration_min": 0.0,
                "rhythm_score": 0.0,
                "active_days": 0,
            }

        messages = [
            {"role": row[0].value if hasattr(row[0], "value") else row[0],
             "created_at": row[1]}
            for row in rows
        ]

        active_days = len({m["created_at"].date() for m in messages})

        sessions = split_into_sessions(messages)
        focus = compute_focus_score(sessions)

        return {
            "score": focus["score"],
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_sessions": focus["total_sessions"],
            "avg_session_depth": focus["avg_session_depth"],
            "avg_session_duration_min": focus["avg_session_duration_min"],
            "rhythm_score": focus["rhythm_score"],
            "active_days": active_days,
        }


class DepthService:
    """Service for depth score assessment."""

    @staticmethod
    async def get_depth_score(
        db: AsyncSession, user_id: UUID, week_offset: int = 0
    ) -> dict:
        """
        Compute depth score for a given week.

        Args:
            db: Database session.
            user_id: Current user's ID.
            week_offset: 0 = current week, 1 = last week, etc.

        Returns:
            Dict matching DepthScoreResponse fields.
        """
        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        week_start = current_monday - timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)

        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(week_end, datetime.max.time())

        # Query 1: Messages with conversation_id, role, content
        result = await db.execute(
            select(
                Message.conversation_id,
                Message.role,
                func.length(Message.content),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.created_at >= start_dt,
                Message.created_at <= end_dt,
                Message.role == MessageRole.USER,
            )
        )
        rows = result.all()

        # Group by conversation: count user msgs and collect lengths
        conv_counts: dict[UUID, int] = {}
        all_lengths: list[int] = []
        for conv_id, _role, content_len in rows:
            conv_counts[conv_id] = conv_counts.get(conv_id, 0) + 1
            if content_len is not None and content_len >= 10:
                all_lengths.append(content_len)

        conv_user_msg_counts = list(conv_counts.values())
        total_conversations = len(conv_counts)

        # Query 2: Mastery data across all user's spaces
        mastery_result = await db.execute(
            select(
                func.avg(Node.mastery),
                func.count(Node.mastery),
                func.count(Node.id),
            )
            .join(Space, Node.space_id == Space.id)
            .where(Space.user_id == user_id)
        )
        mastery_row = mastery_result.one()
        avg_mastery = float(mastery_row[0]) if mastery_row[0] is not None else 0.0
        studied_node_count = mastery_row[1]
        total_node_count = mastery_row[2]

        depth = compute_depth_score(conv_user_msg_counts, all_lengths, avg_mastery)

        return {
            "score": depth["score"],
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_conversations": total_conversations,
            "avg_messages_per_conv": depth["avg_messages_per_conv"],
            "avg_message_length": depth["avg_message_length"],
            "mastery_score": depth["mastery_score"],
            "studied_node_count": studied_node_count,
            "total_node_count": total_node_count,
        }


class ComprehensionService:
    """Service for comprehension score assessment (global snapshot)."""

    @staticmethod
    async def get_comprehension_score(db: AsyncSession, user_id: UUID) -> dict:
        """
        Compute comprehension score from quiz accuracy and mastery ratio.

        Returns dict matching ComprehensionScoreResponse fields.
        """
        # Query 1: Quiz accuracy — SUM(score), SUM(total_score)
        quiz_result = await db.execute(
            select(
                func.coalesce(func.sum(QuizAttempt.score), 0),
                func.coalesce(func.sum(QuizAttempt.total_score), 0),
            ).where(QuizAttempt.user_id == user_id)
        )
        quiz_row = quiz_result.one()
        quiz_score_sum = int(quiz_row[0])
        quiz_total_score_sum = int(quiz_row[1])

        # Query 2: Mastery ratio — COUNT(mastery >= 70), COUNT(all nodes)
        mastery_result = await db.execute(
            select(
                func.count(Node.id).filter(Node.mastery >= 70),
                func.count(Node.id),
            )
            .join(Space, Node.space_id == Space.id)
            .where(Space.user_id == user_id)
        )
        mastery_row = mastery_result.one()
        high_mastery_count = mastery_row[0]
        total_node_count = mastery_row[1]

        comp = compute_comprehension_score(
            quiz_score_sum, quiz_total_score_sum,
            high_mastery_count, total_node_count,
        )

        return {
            "score": comp["score"],
            "quiz_accuracy": comp["quiz_accuracy"],
            "mastery_ratio": comp["mastery_ratio"],
            "quiz_score_sum": quiz_score_sum,
            "quiz_total_score_sum": quiz_total_score_sum,
            "high_mastery_node_count": high_mastery_count,
            "total_node_count": total_node_count,
        }


class ReviewAssessmentService:
    """Service for review score assessment."""

    @staticmethod
    async def get_review_score(db: AsyncSession, user_id: UUID) -> dict:
        """
        Compute review score from completed vs overdue reviews and punctuality.

        Returns dict matching ReviewScoreResponse fields.
        """
        today = date.today()

        # Query 1: COUNT completed + COUNT on-time (merged, both filter status='completed')
        completed_result = await db.execute(
            select(
                func.count().label("completed_count"),
                func.count().filter(
                    ReviewSchedule.completed_at.isnot(None),
                    func.date(ReviewSchedule.completed_at) - ReviewSchedule.scheduled_date <= 2,
                ).label("on_time_count"),
            )
            .select_from(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "completed",
            )
        )
        completed_row = completed_result.one()
        completed_count = completed_row[0]
        on_time_count = completed_row[1]

        # Query 2: COUNT + AVG overdue days for pending reviews past due
        # Use func.current_date() so subtraction stays in SQL (date - date = int in PostgreSQL)
        overdue_result = await db.execute(
            select(
                func.count(),
                func.coalesce(
                    func.avg(func.current_date() - ReviewSchedule.scheduled_date), 0
                ),
            )
            .select_from(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
            )
        )
        overdue_row = overdue_result.one()
        overdue_count = overdue_row[0]
        avg_overdue_days = float(overdue_row[1])

        review = compute_review_score(
            completed_count, overdue_count, on_time_count, avg_overdue_days,
        )

        return {
            "score": review["score"],
            "completion_rate": review["completion_rate"],
            "punctuality_rate": review["punctuality_rate"],
            "overdue_penalty": review["overdue_penalty"],
            "completed_count": completed_count,
            "overdue_count": overdue_count,
            "on_time_count": on_time_count,
            "avg_overdue_days": round(avg_overdue_days, 1),
        }


class KnowledgeStructureService:
    """Service for knowledge structure score assessment (global snapshot)."""

    @staticmethod
    async def get_knowledge_structure_score(db: AsyncSession, user_id: UUID) -> dict:
        """
        Compute knowledge structure score from solidity and advanced ratio.

        Returns dict matching KnowledgeStructureScoreResponse fields.
        """
        # Query 1: All nodes with mastery
        node_result = await db.execute(
            select(Node.id, Node.mastery)
            .join(Space, Node.space_id == Space.id)
            .where(Space.user_id == user_id)
        )
        node_rows = node_result.all()
        node_mastery: dict[UUID, int | None] = {row[0]: row[1] for row in node_rows}
        total_node_count = len(node_mastery)

        # Query 2: KNOWLEDGE_TREE edges
        tree_result = await db.execute(
            select(Edge.from_node_id, Edge.to_node_id)
            .join(Space, Edge.space_id == Space.id)
            .where(
                Space.user_id == user_id,
                Edge.type == EdgeType.KNOWLEDGE_TREE,
            )
        )
        tree_rows = tree_result.all()

        # Query 3: ADVANCED edge count
        adv_result = await db.execute(
            select(func.count())
            .select_from(Edge)
            .join(Space, Edge.space_id == Space.id)
            .where(
                Space.user_id == user_id,
                Edge.type == EdgeType.ADVANCED,
            )
        )
        advanced_edge_count = adv_result.scalar_one()

        # Build parent → children mapping from KNOWLEDGE_TREE edges
        parent_children: dict[UUID, list[UUID]] = {}
        for from_id, to_id in tree_rows:
            parent_children.setdefault(from_id, []).append(to_id)

        # Compute solidity ratios for qualifying parents (mastery >= 50)
        parent_solidity_ratios: list[float] = []
        qualifying_parent_count = 0
        for parent_id, children_ids in parent_children.items():
            parent_m = node_mastery.get(parent_id)
            if parent_m is None or parent_m < 50:
                continue
            qualifying_parent_count += 1
            solid = sum(
                1 for cid in children_ids
                if (node_mastery.get(cid) or 0) >= 60
            )
            parent_solidity_ratios.append(solid / len(children_ids))

        struct = compute_knowledge_structure_score(
            parent_solidity_ratios, advanced_edge_count, total_node_count,
        )

        return {
            "score": struct["score"],
            "solidity": struct["solidity"],
            "advanced_ratio": struct["advanced_ratio"],
            "qualifying_parent_count": qualifying_parent_count,
            "total_node_count": total_node_count,
            "advanced_edge_count": advanced_edge_count,
        }
