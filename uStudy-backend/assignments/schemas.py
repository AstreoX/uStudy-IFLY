"""Pydantic contracts for teacher assignments and student submissions."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QuestionType = Literal["single_choice", "multiple_choice", "true_false", "short_answer", "code"]
Difficulty = Literal["easy", "medium", "hard"]
OjLanguage = Literal["python3", "cpp20"]
OjVerdict = Literal[
    "accepted", "wrong_answer", "compile_error", "runtime_error",
    "time_limit_exceeded", "memory_limit_exceeded", "output_limit_exceeded",
    "dangerous_syscall", "system_error",
]


class OjSample(BaseModel):
    input: str = Field(max_length=65536)
    output: str = Field(max_length=65536)
    explanation: str | None = Field(None, max_length=5000)

    @field_validator("input", "output")
    @classmethod
    def validate_sample_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 65536:
            raise ValueError("each public sample field is limited to 64 KiB")
        return value


class OjPublicConfig(BaseModel):
    allowed_languages: list[OjLanguage] = Field(default_factory=lambda: ["python3", "cpp20"], min_length=1)
    default_language: OjLanguage = "python3"
    starter_code: dict[OjLanguage, str] = Field(default_factory=dict)
    input_description: str = Field(default="", max_length=10000)
    output_description: str = Field(default="", max_length=10000)
    samples: list[OjSample] = Field(min_length=1, max_length=20)
    time_limit_ms: int = Field(default=2000, ge=100, le=10_000)
    memory_limit_mb: int = Field(default=256, ge=64, le=512)
    output_limit_kb: int = Field(default=64, ge=1, le=64)
    compare_mode: Literal["standard", "float"] = "standard"
    float_absolute_tolerance: float = Field(default=1e-6, gt=0, le=0.1)
    float_relative_tolerance: float = Field(default=1e-6, gt=0, le=0.1)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_float_tolerance(cls, value):
        if isinstance(value, dict) and "float_tolerance" in value:
            value = dict(value)
            legacy = value.pop("float_tolerance")
            value.setdefault("float_absolute_tolerance", legacy)
            value.setdefault("float_relative_tolerance", legacy)
        return value

    @model_validator(mode="after")
    def validate_languages(self):
        self.allowed_languages = list(dict.fromkeys(self.allowed_languages))
        if self.default_language not in self.allowed_languages:
            raise ValueError("default_language must be included in allowed_languages")
        if any(language not in self.allowed_languages for language in self.starter_code):
            raise ValueError("starter_code languages must be included in allowed_languages")
        if any(len(source.encode("utf-8")) > 65536 for source in self.starter_code.values()):
            raise ValueError("each starter code template is limited to 64 KiB")
        total_sample_bytes = sum(
            len(sample.input.encode("utf-8")) + len(sample.output.encode("utf-8"))
            for sample in self.samples
        )
        if total_sample_bytes > 256 * 1024:
            raise ValueError("public samples are limited to 256 KiB in total")
        description_bytes = len(self.input_description.encode("utf-8")) + len(
            self.output_description.encode("utf-8")
        )
        if description_bytes > 40 * 1024:
            raise ValueError("input/output descriptions are limited to 40 KiB in total")
        return self


class OjCodeAnswer(BaseModel):
    language: OjLanguage
    source: str = Field(min_length=1, max_length=65536)

    @field_validator("source")
    @classmethod
    def validate_source_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 65536:
            raise ValueError("source is limited to 64 KiB")
        return value


class OjReferenceSolution(OjCodeAnswer):
    pass


class OjHiddenCase(BaseModel):
    id: str | None = None
    input: str = Field(max_length=2_000_000)
    expected_output: str | None = Field(None, max_length=2_000_000)

    @model_validator(mode="after")
    def validate_case_bytes(self):
        if len(self.input.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("hidden input is limited to 2 MiB")
        if self.expected_output is not None and len(self.expected_output.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("hidden expected output is limited to 2 MiB")
        return self


class OjHiddenGroup(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    weight: float = Field(gt=0, le=100)
    cases: list[OjHiddenCase] = Field(min_length=1, max_length=100)


class OjProblemWriteRequest(BaseModel):
    public_config: OjPublicConfig
    reference_solution: OjReferenceSolution
    hidden_groups: list[OjHiddenGroup] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_groups(self):
        if self.reference_solution.language not in self.public_config.allowed_languages:
            raise ValueError("reference solution language must be allowed")
        if len({group.name for group in self.hidden_groups}) != len(self.hidden_groups):
            raise ValueError("hidden group names must be unique")
        if sum(len(group.cases) for group in self.hidden_groups) > 100:
            raise ValueError("at most 100 hidden cases are allowed")
        hidden_bytes = sum(
            len(case.input.encode("utf-8"))
            + len((case.expected_output or "").encode("utf-8"))
            for group in self.hidden_groups for case in group.cases
        )
        if hidden_bytes > 50 * 1024 * 1024:
            raise ValueError("hidden test data is limited to 50 MiB")
        if abs(sum(group.weight for group in self.hidden_groups) - 100.0) > 1e-6:
            raise ValueError("hidden group weights must total 100")
        return self


class OjProblemResponse(OjProblemWriteRequest):
    draft_id: str
    checksum: str
    validated_checksum: str | None = None
    validation_status: str = "unvalidated"
    assignment_version: int


class OjValidationResponse(BaseModel):
    job_id: UUID


class OjSampleRunRequest(OjCodeAnswer):
    pass


class OjCapabilitiesResponse(BaseModel):
    enabled: bool
    languages: list[OjLanguage]


class OjSampleRunAcceptedResponse(BaseModel):
    run_id: UUID
    status: str


class OjRunResponse(BaseModel):
    run_id: UUID
    status: str
    verdict: OjVerdict | None = None
    score: float | None = None
    groups: list[dict[str, Any]] = Field(default_factory=list)
    samples: list[dict[str, Any]] = Field(default_factory=list)
    compile_output: str | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class QuestionGenerationConfig(BaseModel):
    question_type: QuestionType
    count: int = Field(ge=0, le=20)
    score: float = Field(gt=0, le=100)


class AssignmentGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=5000)
    difficulty: Difficulty = "medium"
    due_at: datetime
    question_configs: list[QuestionGenerationConfig] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_question_configs(self):
        if sum(item.count for item in self.question_configs) < 1:
            raise ValueError("at least one question is required")
        if sum(item.count for item in self.question_configs) > 50:
            raise ValueError("at most 50 questions are allowed")
        if len({item.question_type for item in self.question_configs}) != len(self.question_configs):
            raise ValueError("question types must not be duplicated")
        return self


class AssignmentQuestionWrite(BaseModel):
    id: UUID | None = None
    question_type: QuestionType
    question_stem: str = Field(min_length=1, max_length=20000)
    options: list[str] | None = None
    correct_answer: dict[str, Any]
    rubric: str | None = Field(None, max_length=10000)
    max_score: float = Field(gt=0, le=100)
    order_index: int = Field(ge=0)
    grader_type: Literal["rule", "ai", "oj"] = "rule"
    public_config: OjPublicConfig | None = None
    grader_config: dict[str, Any] | None = None


class AssignmentUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(None, min_length=1, max_length=200)
    instructions: str | None = Field(None, max_length=5000)
    difficulty: Difficulty | None = None
    due_at: datetime | None = None
    questions: list[AssignmentQuestionWrite] | None = None


class AssignmentQuestionTeacherResponse(AssignmentQuestionWrite):
    id: UUID


class AssignmentTeacherResponse(BaseModel):
    id: UUID
    space_id: UUID
    teacher_user_id: UUID
    title: str
    instructions: str
    difficulty: str
    status: str
    due_at: datetime
    version: int
    total_questions: int
    total_score: float
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    questions: list[AssignmentQuestionTeacherResponse] = Field(default_factory=list)
    generation_progress: dict[str, Any] | None = None


class AssignmentJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID | None
    submission_id: UUID | None
    job_type: str
    status: str
    attempt_count: int
    output_data: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class UserAnswerItem(BaseModel):
    question_id: UUID
    answer: Any = None


class AssignmentDraftRequest(BaseModel):
    answers: list[UserAnswerItem]
    current_question_index: int = Field(0, ge=0)


class AssignmentSubmitRequest(BaseModel):
    answers: list[UserAnswerItem]


class AssignmentListItemResponse(BaseModel):
    id: UUID
    item_kind: Literal["assignment"] = "assignment"
    space_id: UUID
    title: str
    instructions: str
    difficulty: str
    assignment_status: str
    submission_status: str | None
    due_at: datetime
    effective_due_at: datetime
    total_questions: int
    total_score: float
    draft_answer_count: int | None
    provisional_score: float | None
    final_score: float | None
    answers_revealed: bool
    created_at: datetime
    published_at: datetime | None


class AssignmentQuestionStudentResponse(BaseModel):
    id: UUID
    question_type: str
    question_stem: str
    options: list[str] | None
    max_score: float
    order_index: int
    grader_type: str
    public_config: OjPublicConfig | None = None
    correct_answer: dict[str, Any] | None = None
    rubric: str | None = None


class AssignmentDraftAnswerResponse(BaseModel):
    question_id: UUID
    answer: Any = None


class AssignmentDetailResponse(BaseModel):
    id: UUID
    item_kind: Literal["assignment"] = "assignment"
    space_id: UUID
    title: str
    instructions: str
    difficulty: str
    assignment_status: str
    submission_status: str | None
    due_at: datetime
    effective_due_at: datetime
    total_questions: int
    total_score: float
    provisional_score: float | None
    final_score: float | None
    answers_revealed: bool
    questions: list[AssignmentQuestionStudentResponse]
    draft_answers: list[AssignmentDraftAnswerResponse] = Field(default_factory=list)
    current_question_index: int = 0
    draft_updated_at: datetime | None = None


class AssignmentDraftResponse(BaseModel):
    assignment_id: UUID
    submission_id: UUID
    submission_status: Literal["in_progress"] = "in_progress"
    draft_updated_at: datetime


class AssignmentSubmitResponse(BaseModel):
    assignment_id: UUID
    submission_id: UUID
    job_id: UUID
    submission_status: Literal["pending"] = "pending"
    message: str = "作业已提交，AI 正在批改"


class AssignmentQuestionResultResponse(BaseModel):
    id: UUID
    question_id: UUID
    order_index: int
    question_type: str
    question_stem: str
    options: list[str] | None
    max_score: float
    user_answer: Any = None
    status: str
    auto_score: float | None
    final_score: float | None
    feedback: str | None
    reasoning: str | None
    review_required: bool
    grader_result: dict[str, Any] | None = None
    oj_run_id: UUID | None = None
    correct_answer: dict[str, Any] | None = None
    rubric: str | None = None


class AssignmentSubmissionResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    user_id: UUID
    submission_status: str
    provisional_score: float | None
    final_score: float | None
    total_score: float
    teacher_feedback: str | None
    grading_error: str | None
    submitted_at: datetime | None
    grading_completed_at: datetime | None
    due_at: datetime
    effective_due_at: datetime
    answers_revealed: bool
    question_results: list[AssignmentQuestionResultResponse]


class RecipientDeadlineUpdateRequest(BaseModel):
    due_at: datetime


class AnswerReviewItem(BaseModel):
    answer_id: UUID
    score: float = Field(ge=0)
    comment: str | None = Field(None, max_length=5000)


class SubmissionReviewRequest(BaseModel):
    answers: list[AnswerReviewItem] = Field(default_factory=list)
    teacher_feedback: str | None = Field(None, max_length=10000)
    confirm_remaining: bool = False


class TeacherSubmissionListItem(BaseModel):
    submission_id: UUID | None
    recipient_id: UUID
    user_id: UUID
    student_name: str
    submission_status: str
    provisional_score: float | None
    final_score: float | None
    total_score: float
    review_required: bool
    submitted_at: datetime | None
    effective_due_at: datetime


class TeacherSubmissionListResponse(BaseModel):
    assignment_id: UUID
    recipient_count: int
    submitted_count: int
    items: list[TeacherSubmissionListItem]
