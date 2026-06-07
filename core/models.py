from pydantic import BaseModel, Field
from typing import List, Optional


class SkillList(BaseModel):
    """List of missing skills extracted from JD analysis."""

    skills: List[str] = Field(
        description="List of technical or soft skills missing from the resume"
    )


class FactList(BaseModel):
    """List of extracted user facts."""

    facts: List[str] = Field(description="List of persistent truths about the user")


class EmailDraft(BaseModel):
    """Schema for a drafted email."""

    subject: str = Field(description="The email subject line")
    body: str = Field(description="The email body content")


class Transaction(BaseModel):
    """A single financial transaction."""

    amount: float = Field(description="The numeric cost/income amount")
    category_id: int = Field(
        description="The matching category ID from the provided context"
    )
    description: str = Field(description="Specific item name or short context")


class TransactionList(BaseModel):
    """List of extracted financial transactions."""

    transactions: List[Transaction]


class FoodItem(BaseModel):
    """A single food log item with nutritional data."""

    name: str = Field(description="Canonical English name of the food")
    quantity: Optional[str] = Field(None, description="Quantity (e.g., '180g', '2')")
    calories: int
    protein: float
    carbs: float
    fat: float
    fiber: float
    sugar: float
    diet_type: str = Field(description="veg | non-veg | vegan")


class FoodLog(BaseModel):
    """List of extracted food items."""

    items: List[FoodItem]


class NutritionTargets(BaseModel):
    """Daily calorie and macro targets."""

    calories: int
    protein: float
    carbs: float
    fat: float

    fat: float


# --- WORKOUT MODELS ---


class WorkoutExercise(BaseModel):
    """A single exercise within a workout session."""

    exercise: str = Field(
        description="Canonical name of the exercise (e.g., 'Bench Press', 'Squat'). Use Title Case."
    )
    sets: int = Field(description="Number of sets performed")
    reps: int = Field(description="Number of repetitions per set")
    weight: float = Field(description="Weight used in kg")


class WorkoutSession(BaseModel):
    """A complete workout session containing multiple exercises."""

    date: Optional[str] = Field(
        None,
        description="Date of the workout in DD-MM-YYYY format. Use null if not specified.",
    )
    exercises: List[WorkoutExercise] = Field(
        description="List of exercises performed in this session"
    )


# --- BRAIN DUMP MODELS ---


class BrainDumpEntry(BaseModel):
    """A structured brain dump entry."""

    title: str = Field(description="A short, descriptive title (max 40 chars)")
    category: str = Field(
        description="Category: Recipe | Idea | Note | Link | Quote | Code"
    )
    tags: List[str] = Field(description="List of 1-3 short lowercase keywords")
    content: str = Field(
        description="The full content, cleaned up for readability (keep Markdown if provided)"
    )


class BrainDumpList(BaseModel):
    """List of extracted brain dump entries."""

    items: List[BrainDumpEntry]


# --- MAIN LEARNING MODELS (REFACTORED) ---


class RoadmapMeta(BaseModel):
    total_milestones: int
    estimated_effort: str


class Component(BaseModel):
    step: int
    component: str
    objective: str


class LearningRoadmap(BaseModel):
    """Core components roadmap."""

    roadmap: List[Component]


class MentalModel(BaseModel):
    definition: str
    analogy: str


class SystemFlow(BaseModel):
    io: str
    steps: List[str]


class ProReality(BaseModel):
    trade_off: str
    breaking_point: str
    trap: str


class LogicStressTest(BaseModel):
    problem: str
    diagnosis: str


class Implementation(BaseModel):
    high_level_approach: str
    example: str


class KnowledgeCheck(BaseModel):
    question: str
    options: List[str]
    correct_answer: str


class DayDetail(BaseModel):
    """Deep component flow for first-time learners."""

    the_mental_model: MentalModel
    the_system_flow: SystemFlow
    the_pro_reality: ProReality
    logic_stress_test: List[LogicStressTest]
    the_implementation: Implementation
    the_knowledge_check: List[KnowledgeCheck]


# --- MICRO LEARNING MODELS (RESTORED) ---


class PracticeAnswer(BaseModel):
    """Structured answer with red flag, pro response, and reasoning."""

    red_flag: str = Field(description="The lame 'Junior Trap' answer")
    pro_answer: str = Field(description="The 'Senior Signal' pro answer")
    why: str = Field(description="The technical reasoning why the pro answer wins")


class PracticeQuestion(BaseModel):
    """An interview question with a structured expert answer."""

    q: str = Field(description="The hard interview question")
    a: PracticeAnswer = Field(description="The structured multi-layered answer")


class MicroBasics(BaseModel):
    """Simple definition and technical reality."""

    simple_def: str = Field(description="Explanation for a 15-year-old")
    technical_reality: str = Field(description="Technical reality under the hood")


class MicroTruth(BaseModel):
    """Real-world pain, catch, and when to say no."""

    the_pain: str = Field(description="The real-world pain it stops")
    the_catch: str = Field(description="The downside or trade-off")
    the_no_go: str = Field(description="When this is a bad idea")


class MicroInterviewEdge(BaseModel):
    """Junior trap, senior signal, and the pivot."""

    junior_trap: str = Field(description="Common mistake to avoid")
    senior_signal: str = Field(description="Insight that proves production experience")
    the_pivot: str = Field(description="How to move to a more impressive topic")


class MicroDayDetail(BaseModel):
    """Deep briefing for a micro-learning topic."""

    the_basics: MicroBasics
    the_truth: MicroTruth
    the_interview_edge: MicroInterviewEdge
    real_scenarios: List[str]
    practice_questions: List[PracticeQuestion]


# --- UTILITY MODELS ---


class UserProfile(BaseModel):
    """Structured user profile extracted from resume or interaction."""

    current_role: str = Field(description="Professional job title or current role")
    experience_level: str = Field(description="e.g., 'junior', 'mid', 'senior'")
    experience_years: int = Field(default=0, description="Total years of experience")
    skills: List[str] = Field(
        default_factory=list,
        description="List of core technical or domain-specific skills",
    )
    industry: str = Field(
        description="The primary industry, e.g., 'Software Engineering', 'Marketing', 'Finance'"
    )
    domain: str = Field(
        default="",
        description="Specific domain expertise, e.g., 'Backend', 'B2B SaaS', 'DevOps'",
    )
    example_type: str = Field(
        description="What kind of examples will resonate most with this person?"
    )


class TopicClassification(BaseModel):
    """Classification of a learning topic."""

    topic_type: str = Field(
        description="The classification of the topic: 'main' (broad) or 'micro' (granular)"
    )


class MasterStudyGuide(BaseModel):
    title: str = Field(description="Sophisticated, professional headline")
    executive_summary: str = Field(description="Master synthesis (200-300 words)")
    table_of_contents: List[str] = Field(description="Clickable Markdown TOC")
    master_content: str = Field(description="Seamlessly unified body of the guide")
    staff_challenge: str = Field(
        description="Complex engineering problem for the reader to solve"
    )
    future_trajectory: str = Field(
        description="Predictive analysis of the next 3-5 years"
    )


# --- API REQUEST/RESPONSE MODELS ---


class WorkoutCreateRequest(BaseModel):
    exercise: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight: Optional[float] = None
    text: Optional[str] = None
    date: Optional[str] = None


class BrainDumpCreateRequest(BaseModel):
    content: str
    title: Optional[str] = None
    category: Optional[str] = "Note"
    tags: Optional[List[str]] = None


class ChatRequest(BaseModel):
    task: str


class TodoCreateRequest(BaseModel):
    task: str


class TodoStatusUpdate(BaseModel):
    status: str


class BookmarkCreateRequest(BaseModel):
    url: str


class ReminderCreateRequest(BaseModel):
    text: str
    target_time: Optional[str] = None  # Format: DD-MM-YYYY HH:MM


class AnalyzeSkillsRequest(BaseModel):
    job_description: str


class SkillCreateRequest(BaseModel):
    skill: str


class LearningGenerateRequest(BaseModel):
    topic_title: str
    topic_type: Optional[str] = None  # Optional, will be identified if missing


class SkillActionRequest(BaseModel):
    skill: str


class FinanceCategoryCreate(BaseModel):
    name: str
    type: str = "expense"


class FinanceTransactionCreate(BaseModel):
    text: str
    date_logged: Optional[str] = None


class FinanceTransactionUpdate(BaseModel):
    amount: Optional[float] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    date_logged: Optional[str] = None


class GenerateTargetsRequest(BaseModel):
    profile_text: str


class NutritionTargetsUpdate(BaseModel):
    calories: int = 1985
    protein: float = 150.0
    carbs: float = 200.0
    fat: float = 65.0


class FoodLogUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[str] = None
    calories: Optional[int] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None


class FoodLogCreate(BaseModel):
    text: str
    date: Optional[str] = None


class CalendarEventCreate(BaseModel):
    summary: str
    start_time: str
    end_time: str
    description: Optional[str] = None
    location: Optional[str] = None


class QuickAddEvent(BaseModel):
    text: str


class DescriptionRequest(BaseModel):
    description: str


class JobApplicationCreate(BaseModel):
    company: str
    position: str
    email: Optional[str] = None
    status: Optional[str] = "Pending"
    notes: Optional[str] = None
    url: Optional[str] = None


class JobApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    url: Optional[str] = None


class ScrapeTriggerRequest(BaseModel):
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None


class ScraperConfigUpdate(BaseModel):
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    naukri_max_pages: Optional[int] = None
    search_pages: Optional[int] = None
    delay_between_reqs: Optional[float] = None
    mandatory_skill: Optional[str] = None
    nice_to_have: Optional[List[str]] = None
    exp_min: Optional[int] = None
    exp_max: Optional[int] = None


class ParsedCalendarEvent(BaseModel):
    """Structured calendar event parsed from natural language input by LLM."""

    summary: str = Field(description="Short title or summary of the event")
    start_time: str = Field(
        description="ISO 8601 formatted start datetime string (including local/target timezone offset). If only a date is specified, default to 09:00:00 on that date with the target timezone."
    )
    end_time: str = Field(
        description="ISO 8601 formatted end datetime string (including local/target timezone offset). If duration is not specified, default to 1 hour after the start time."
    )
    description: Optional[str] = Field(
        None, description="Optional description of the event"
    )
    location: Optional[str] = Field(None, description="Optional location of the event")
