"""Source-backed aggregates for the fixed-course teacher dashboard."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Edge,
    EdgeType,
    Node,
    NodeMasteryEvent,
    NodeUserMastery,
    Quiz,
    QuizAttempt,
    SpaceMember,
    SpaceMemberRole,
    StudyActivityLog,
    User,
)
from teacher.schemas import (
    ActivityMixItem,
    DailyActivityPoint,
    KnowledgeNodeResponse,
    KnowledgeResponse,
    LearningSummaryResponse,
    MasteryTrendPoint,
    OverviewResponse,
    PeriodResponse,
    QuizSummaryResponse,
    StudentDetailResponse,
    StudentListItem,
    StudentListResponse,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
ALLOWED_DAYS = {7, 30, 90}


@dataclass(frozen=True)
class PeriodWindow:
    days: int
    start_local: datetime
    end_local: datetime
    previous_start_local: datetime

    @property
    def start_utc(self) -> datetime:
        return self.start_local.astimezone(timezone.utc)

    @property
    def end_utc(self) -> datetime:
        return self.end_local.astimezone(timezone.utc)

    @property
    def previous_start_utc(self) -> datetime:
        return self.previous_start_local.astimezone(timezone.utc)

    def response(self) -> PeriodResponse:
        return PeriodResponse(
            days=self.days,
            start_date=self.start_local.date(),
            end_date=(self.end_local - timedelta(days=1)).date(),
            previous_start_date=self.previous_start_local.date(),
            previous_end_date=(self.start_local - timedelta(days=1)).date(),
            generated_at=datetime.now(timezone.utc),
        )


def build_period(days: int, now: datetime | None = None) -> PeriodWindow:
    if days not in ALLOWED_DAYS:
        raise ValueError("days must be one of 7, 30, or 90")
    local_now = (now or datetime.now(timezone.utc)).astimezone(SHANGHAI)
    end_local = datetime.combine(local_now.date() + timedelta(days=1), time.min, SHANGHAI)
    start_local = end_local - timedelta(days=days)
    return PeriodWindow(days, start_local, end_local, start_local - timedelta(days=days))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _percent(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100.0 / denominator, 1)


def _rounded_average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _snapshot_metrics(
    states: dict[tuple[UUID, UUID], int], student_count: int, node_count: int
) -> tuple[int, float | None, float | None]:
    values = list(states.values())
    denominator = student_count * node_count
    return len(values), _percent(len(values), denominator), _rounded_average(values)


class TeacherAnalyticsService:
    def __init__(self, db: AsyncSession, space_id: UUID, days: int):
        self.db = db
        self.space_id = space_id
        self.period = build_period(days)

    async def _students(self, search: str | None = None) -> list[tuple[UUID, str]]:
        stmt = (
            select(User.id, User.nickname)
            .join(SpaceMember, SpaceMember.user_id == User.id)
            .where(
                SpaceMember.space_id == self.space_id,
                SpaceMember.role == SpaceMemberRole.MEMBER,
            )
            .order_by(User.nickname, User.id)
        )
        if search and search.strip():
            stmt = stmt.where(User.nickname.ilike(f"%{search.strip()}%"))
        return [(row.id, row.nickname) for row in (await self.db.execute(stmt)).all()]

    async def _node_rows(self) -> list[tuple[UUID, str]]:
        rows = (
            await self.db.execute(
                select(Node.id, Node.label)
                .where(Node.space_id == self.space_id)
                .order_by(Node.label)
            )
        ).all()
        return [(row.id, row.label) for row in rows]

    async def _current_mastery(
        self, student_ids: list[UUID]
    ) -> dict[tuple[UUID, UUID], int]:
        if not student_ids:
            return {}
        rows = (
            await self.db.execute(
                select(NodeUserMastery.user_id, NodeUserMastery.node_id, NodeUserMastery.mastery)
                .join(Node, Node.id == NodeUserMastery.node_id)
                .where(
                    Node.space_id == self.space_id,
                    NodeUserMastery.user_id.in_(student_ids),
                )
            )
        ).all()
        return {(row.user_id, row.node_id): row.mastery for row in rows}

    async def _mastery_events(
        self, student_ids: list[UUID], end_utc: datetime
    ) -> list[NodeMasteryEvent]:
        if not student_ids:
            return []
        return list(
            (
                await self.db.execute(
                    select(NodeMasteryEvent)
                    .where(
                        NodeMasteryEvent.space_id == self.space_id,
                        NodeMasteryEvent.user_id.in_(student_ids),
                        NodeMasteryEvent.created_at < end_utc,
                    )
                    .order_by(NodeMasteryEvent.created_at, NodeMasteryEvent.id)
                )
            ).scalars()
        )

    async def _mastery_trend(
        self, student_ids: list[UUID], node_count: int
    ) -> tuple[list[MasteryTrendPoint], dict[tuple[UUID, UUID], int]]:
        events = await self._mastery_events(student_ids, self.period.end_utc)
        states: dict[tuple[UUID, UUID], int] = {}
        previous_states: dict[tuple[UUID, UUID], int] = {}
        event_index = 0

        while event_index < len(events) and _aware(events[event_index].created_at) < self.period.start_utc:
            event = events[event_index]
            previous_states[(event.user_id, event.node_id)] = event.new_mastery
            event_index += 1
        states.update(previous_states)

        points: list[MasteryTrendPoint] = []
        for offset in range(self.period.days):
            point_date = self.period.start_local.date() + timedelta(days=offset)
            cutoff_local = datetime.combine(point_date + timedelta(days=1), time.min, SHANGHAI)
            cutoff_utc = cutoff_local.astimezone(timezone.utc)
            while event_index < len(events) and _aware(events[event_index].created_at) < cutoff_utc:
                event = events[event_index]
                states[(event.user_id, event.node_id)] = event.new_mastery
                event_index += 1
            assessed, coverage, average = _snapshot_metrics(
                states, len(student_ids), node_count
            )
            points.append(
                MasteryTrendPoint(
                    date=point_date,
                    assessed_pairs=assessed,
                    coverage_rate=coverage,
                    avg_mastery=average,
                )
            )
        return points, previous_states

    async def _quiz_metrics(
        self, student_ids: list[UUID], start: datetime, end: datetime
    ) -> tuple[int, int, float | None]:
        if not student_ids:
            return 0, 0, None
        rows = (
            await self.db.execute(
                select(QuizAttempt.user_id, QuizAttempt.score, QuizAttempt.total_score)
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .where(
                    Quiz.space_id == self.space_id,
                    QuizAttempt.user_id.in_(student_ids),
                    QuizAttempt.status == "completed",
                    QuizAttempt.submitted_at >= start,
                    QuizAttempt.submitted_at < end,
                )
            )
        ).all()
        valid = [row for row in rows if row.total_score and row.total_score > 0]
        accuracy = _percent(
            sum(row.score for row in valid), sum(row.total_score for row in valid)
        )
        return len({row.user_id for row in rows}), len(rows), accuracy

    async def get_overview(self) -> OverviewResponse:
        students = await self._students()
        student_ids = [student_id for student_id, _ in students]
        nodes = await self._node_rows()
        current_mastery = await self._current_mastery(student_ids)
        assessed, coverage, avg_mastery = _snapshot_metrics(
            current_mastery, len(student_ids), len(nodes)
        )
        trend, previous_states = await self._mastery_trend(student_ids, len(nodes))
        _, previous_coverage, previous_avg = _snapshot_metrics(
            previous_states, len(student_ids), len(nodes)
        )

        calendar_end_local = self.period.end_local
        calendar_start_local = calendar_end_local - timedelta(days=90)
        calendar_start_utc = calendar_start_local.astimezone(timezone.utc)
        activity_query_start = min(
            self.period.previous_start_utc,
            calendar_start_utc,
        )
        activity_rows = (
            await self.db.execute(
                select(StudyActivityLog.user_id, StudyActivityLog.activity_type, StudyActivityLog.activity_time)
                .where(
                    StudyActivityLog.space_id == self.space_id,
                    StudyActivityLog.user_id.in_(student_ids) if student_ids else False,
                    StudyActivityLog.activity_time >= activity_query_start,
                    StudyActivityLog.activity_time < self.period.end_utc,
                )
            )
        ).all()
        users_by_date: dict[date, list[UUID]] = defaultdict(list)
        types_by_date: dict[date, Counter[str]] = defaultdict(Counter)
        mix: Counter[str] = Counter()
        current_active: set[UUID] = set()
        previous_active: set[UUID] = set()
        for row in activity_rows:
            stamp = _aware(row.activity_time)
            local_date = stamp.astimezone(SHANGHAI).date()
            users_by_date[local_date].append(row.user_id)
            types_by_date[local_date][row.activity_type] += 1
            if stamp >= self.period.start_utc:
                current_active.add(row.user_id)
                mix[row.activity_type] += 1
            elif stamp >= self.period.previous_start_utc:
                previous_active.add(row.user_id)

        daily = []
        for offset in range(self.period.days):
            day = self.period.start_local.date() + timedelta(days=offset)
            users = users_by_date.get(day, [])
            day_mix = types_by_date.get(day, Counter())
            daily.append(
                DailyActivityPoint(
                    date=day,
                    active_students=len(set(users)),
                    active_rate=_percent(len(set(users)), len(students)),
                    activity_count=len(users),
                    activity_mix=[
                        ActivityMixItem(activity_type=kind, count=count)
                        for kind, count in sorted(
                            day_mix.items(), key=lambda item: (-item[1], item[0])
                        )
                    ],
                )
            )

        activity_calendar = []
        for offset in range(90):
            day = calendar_start_local.date() + timedelta(days=offset)
            users = users_by_date.get(day, [])
            day_mix = types_by_date.get(day, Counter())
            activity_calendar.append(
                DailyActivityPoint(
                    date=day,
                    active_students=len(set(users)),
                    active_rate=_percent(len(set(users)), len(students)),
                    activity_count=len(users),
                    activity_mix=[
                        ActivityMixItem(activity_type=kind, count=count)
                        for kind, count in sorted(
                            day_mix.items(), key=lambda item: (-item[1], item[0])
                        )
                    ],
                )
            )

        quiz_participants, quiz_attempts, quiz_accuracy = await self._quiz_metrics(
            student_ids, self.period.start_utc, self.period.end_utc
        )
        _, _, previous_quiz_accuracy = await self._quiz_metrics(
            student_ids, self.period.previous_start_utc, self.period.start_utc
        )
        return OverviewResponse(
            period=self.period.response(),
            students_total=len(students),
            active_students=len(current_active),
            active_rate=_percent(len(current_active), len(students)),
            active_rate_previous=_percent(len(previous_active), len(students)),
            assessed_pairs=assessed,
            knowledge_coverage=coverage,
            knowledge_coverage_previous=previous_coverage,
            avg_mastery=avg_mastery,
            avg_mastery_previous=previous_avg,
            quiz_participants=quiz_participants,
            quiz_attempts=quiz_attempts,
            quiz_accuracy=quiz_accuracy,
            quiz_accuracy_previous=previous_quiz_accuracy,
            daily_activity=daily,
            activity_calendar=activity_calendar,
            activity_mix=[
                ActivityMixItem(activity_type=kind, count=count)
                for kind, count in sorted(mix.items(), key=lambda item: (-item[1], item[0]))
            ],
        )

    async def _chapter_map(self, nodes: list[tuple[UUID, str]]) -> dict[UUID, str]:
        label_by_id = dict(nodes)
        edge_rows = (
            await self.db.execute(
                select(Edge.from_node_id, Edge.to_node_id).where(
                    Edge.space_id == self.space_id,
                    Edge.type == EdgeType.KNOWLEDGE_TREE,
                )
            )
        ).all()
        parent_by_child = {row.to_node_id: row.from_node_id for row in edge_rows}
        root_ids = [node_id for node_id, label in nodes if label == "数据结构"]
        root_id = root_ids[0] if root_ids else None
        result: dict[UUID, str] = {}
        for node_id, label in nodes:
            cursor = node_id
            parent = parent_by_child.get(cursor)
            seen: set[UUID] = set()
            while parent is not None and parent != root_id and parent not in seen:
                seen.add(parent)
                cursor = parent
                parent = parent_by_child.get(cursor)
            result[node_id] = label_by_id.get(cursor, label)
        return result

    def _knowledge_nodes(
        self,
        nodes: list[tuple[UUID, str]],
        chapter_map: dict[UUID, str],
        student_ids: list[UUID],
        mastery: dict[tuple[UUID, UUID], int],
    ) -> list[KnowledgeNodeResponse]:
        result = []
        for node_id, label in nodes:
            values = [
                mastery[(student_id, node_id)]
                for student_id in student_ids
                if (student_id, node_id) in mastery
            ]
            mastered = sum(value >= 80 for value in values)
            result.append(
                KnowledgeNodeResponse(
                    node_id=node_id,
                    label=label,
                    chapter=chapter_map[node_id],
                    assessed_students=len(values),
                    coverage_rate=_percent(len(values), len(student_ids)),
                    avg_mastery=_rounded_average(values),
                    mastered_students=mastered,
                    mastered_rate=_percent(mastered, len(values)),
                )
            )
        return result

    async def get_knowledge(self) -> KnowledgeResponse:
        students = await self._students()
        student_ids = [student_id for student_id, _ in students]
        nodes = await self._node_rows()
        mastery = await self._current_mastery(student_ids)
        chapter_map = await self._chapter_map(nodes)
        node_items = self._knowledge_nodes(nodes, chapter_map, student_ids, mastery)
        weak = [
            item
            for item in node_items
            if item.assessed_students >= 3
            and item.coverage_rate is not None
            and item.coverage_rate >= 30
            and item.avg_mastery is not None
        ]
        weak.sort(key=lambda item: (item.avg_mastery, -item.coverage_rate, item.label))
        trend, _ = await self._mastery_trend(student_ids, len(nodes))
        return KnowledgeResponse(
            period=self.period.response(),
            nodes=node_items,
            weak_nodes=weak[:10],
            trend=trend,
        )

    async def _student_items(self, students: list[tuple[UUID, str]]) -> list[StudentListItem]:
        student_ids = [student_id for student_id, _ in students]
        nickname_map = dict(students)
        nodes = await self._node_rows()
        mastery = await self._current_mastery(student_ids)

        activity_rows = (
            await self.db.execute(
                select(StudyActivityLog.user_id, StudyActivityLog.activity_time).where(
                    StudyActivityLog.space_id == self.space_id,
                    StudyActivityLog.user_id.in_(student_ids) if student_ids else False,
                )
            )
        ).all()
        last_active: dict[UUID, datetime] = {}
        period_activity_count: Counter[UUID] = Counter()
        active_dates: dict[UUID, set[date]] = defaultdict(set)
        for row in activity_rows:
            stamp = _aware(row.activity_time)
            if row.user_id not in last_active or stamp > _aware(last_active[row.user_id]):
                last_active[row.user_id] = stamp
            if self.period.start_utc <= stamp < self.period.end_utc:
                period_activity_count[row.user_id] += 1
                active_dates[row.user_id].add(stamp.astimezone(SHANGHAI).date())

        quiz_rows = (
            await self.db.execute(
                select(QuizAttempt.user_id, QuizAttempt.score, QuizAttempt.total_score)
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .where(
                    Quiz.space_id == self.space_id,
                    QuizAttempt.user_id.in_(student_ids) if student_ids else False,
                    QuizAttempt.status == "completed",
                    QuizAttempt.submitted_at >= self.period.start_utc,
                    QuizAttempt.submitted_at < self.period.end_utc,
                )
            )
        ).all()
        quizzes: dict[UUID, list[tuple[int, int]]] = defaultdict(list)
        for row in quiz_rows:
            if row.total_score and row.total_score > 0:
                quizzes[row.user_id].append((row.score, row.total_score))

        items: list[StudentListItem] = []
        for student_id in student_ids:
            values = [
                value
                for (user_id, _), value in mastery.items()
                if user_id == student_id
            ]
            quiz_values = quizzes.get(student_id, [])
            items.append(
                StudentListItem(
                    user_id=student_id,
                    nickname=nickname_map[student_id],
                    last_active_at=last_active.get(student_id),
                    active_days=len(active_dates.get(student_id, set())),
                    activity_count=period_activity_count[student_id],
                    assessed_node_count=len(values),
                    coverage_rate=_percent(len(values), len(nodes)),
                    avg_mastery=_rounded_average(values),
                    mastered_node_count=sum(value >= 80 for value in values),
                    quiz_attempt_count=len(quiz_values),
                    quiz_accuracy=_percent(
                        sum(score for score, _ in quiz_values),
                        sum(total for _, total in quiz_values),
                    ),
                )
            )
        return items

    async def get_students(
        self,
        search: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> StudentListResponse:
        students = await self._students(search)
        items = await self._student_items(students)
        sorters = {
            "last_active": lambda item: item.last_active_at.timestamp() if item.last_active_at else -1,
            "coverage": lambda item: item.coverage_rate if item.coverage_rate is not None else -1,
            "mastery": lambda item: item.avg_mastery if item.avg_mastery is not None else -1,
            "quiz_accuracy": lambda item: item.quiz_accuracy if item.quiz_accuracy is not None else -1,
        }
        items.sort(key=lambda item: (sorters[sort](item), item.nickname), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return StudentListResponse(
            period=self.period.response(),
            items=items[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def get_student_detail(self, student_id: UUID) -> StudentDetailResponse | None:
        student = (
            await self.db.execute(
                select(User.id, User.nickname)
                .join(SpaceMember, SpaceMember.user_id == User.id)
                .where(
                    User.id == student_id,
                    SpaceMember.space_id == self.space_id,
                    SpaceMember.role == SpaceMemberRole.MEMBER,
                )
            )
        ).one_or_none()
        if student is None:
            return None

        student_tuple = [(student.id, student.nickname)]
        student_item = (await self._student_items(student_tuple))[0]
        nodes = await self._node_rows()
        mastery = await self._current_mastery([student_id])
        chapter_map = await self._chapter_map(nodes)
        knowledge_nodes = self._knowledge_nodes(nodes, chapter_map, [student_id], mastery)
        mastery_trend, _ = await self._mastery_trend([student_id], len(nodes))

        quiz_rows = (
            await self.db.execute(
                select(QuizAttempt, Quiz.title)
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .where(
                    Quiz.space_id == self.space_id,
                    QuizAttempt.user_id == student_id,
                    QuizAttempt.status == "completed",
                    QuizAttempt.submitted_at >= self.period.start_utc,
                    QuizAttempt.submitted_at < self.period.end_utc,
                )
                .order_by(QuizAttempt.submitted_at.desc())
                .limit(10)
            )
        ).all()
        recent_quizzes = [
            QuizSummaryResponse(
                quiz_id=attempt.quiz_id,
                title=title,
                submitted_at=attempt.submitted_at,
                score_percent=_percent(attempt.score, attempt.total_score),
                strengths=list(attempt.strengths or []),
                weaknesses=list(attempt.weaknesses or []),
                suggestions=list(attempt.suggestions or []),
            )
            for attempt, title in quiz_rows
        ]

        activity_rows = list(
            (
                await self.db.execute(
                    select(StudyActivityLog)
                    .where(
                        StudyActivityLog.space_id == self.space_id,
                        StudyActivityLog.user_id == student_id,
                        StudyActivityLog.activity_time >= self.period.start_utc,
                        StudyActivityLog.activity_time < self.period.end_utc,
                    )
                    .order_by(StudyActivityLog.activity_time.desc())
                    .limit(20)
                )
            ).scalars()
        )
        summaries = [
            LearningSummaryResponse(
                id=item.id,
                activity_time=item.activity_time,
                activity_type=item.activity_type,
                title=item.title,
                summary=item.summary,
                study_depth=item.study_depth,
                related_node_labels=list(item.related_node_labels or []),
                source=item.source,
            )
            for item in activity_rows
        ]
        return StudentDetailResponse(
            period=self.period.response(),
            student=student_item,
            knowledge_nodes=knowledge_nodes,
            mastery_trend=mastery_trend,
            recent_quizzes=recent_quizzes,
            learning_summaries=summaries,
        )
