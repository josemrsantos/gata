from dataclasses import dataclass, field


@dataclass
class Headline:
    title: str
    abstract: str
    source: str
    published_at: str
    social_score: float


@dataclass
class NewsSource:
    # Exactly one of country or sources must be set; they are mutually exclusive
    # in the NewsAPI.org API.
    country: str = ""  # ISO 3166-1 alpha-2 code, e.g. "us"
    sources: str = ""  # comma-separated NewsAPI.org source IDs, e.g. "bbc-news"
    category: str = "general"  # only used with country; ignored when sources is set
    count: int = 10


@dataclass
class StrategyBrief:
    target_audience: str
    output_language: str
    tone: str


@dataclass
class Community:
    name: str
    target_audience: str
    output_language: str
    tone: str
    topics: list[str] = field(default_factory=list)
    news_sources: list[NewsSource] = field(default_factory=list)
    panels: int = 1
    layout: str = "horizontal"

    def to_brief(self) -> StrategyBrief:
        return StrategyBrief(
            target_audience=self.target_audience,
            output_language=self.output_language,
            tone=self.tone,
        )


@dataclass
class PanelConcept:
    scene: str
    caption: str
    beat: str


@dataclass
class CartoonLayout:
    panels: int = 1
    direction: str = "horizontal"


@dataclass
class CartoonConcept:
    full_text: str
    image_prompt: str
    iteration: int
    panels: list[PanelConcept] | None = None


@dataclass
class Critique:
    feedback: str
    approved: bool
    language_check_passed: bool


@dataclass
class EnrichedBrief:
    target_audience: str
    output_language: str
    tone: str
    cultural_angle: str
    culturally_loaded_references: list[str]
    joke_type: str = ""


@dataclass
class FramerHumor:
    wordplay_scan: bool = True
    joke_types: list[str] = field(
        default_factory=lambda: ["situational", "wordplay", "absurdist", "deadpan"]
    )
    language_register: str = "vernacular"
    inconvenience: int = 0


@dataclass
class SatiristHumor:
    preferred_style: str = "deadpan"
    avoid: list[str] = field(default_factory=list)
    subversion: str = "high"
    joke_explanation: bool = True
    inconvenience: int = 0


@dataclass
class CriticHumor:
    evaluate_joke_mechanics: bool = True
    flag_if_no_subversion: bool = True
    inconvenience: int = 0
    dual_satirist: bool = False


@dataclass
class HumorConfig:
    framer: FramerHumor = field(default_factory=FramerHumor)
    satirist: SatiristHumor = field(default_factory=SatiristHumor)
    critic: CriticHumor = field(default_factory=CriticHumor)


@dataclass
class PersonaConfig:
    name: str
    models: list[str]
    system_prompt: str
    max_tokens: int = 2048


@dataclass
class DualLoopResult:
    iteration: int
    proposer_output: str
    reviewer_verdict: str
    reviewer_feedback: str
    final_say: bool


@dataclass
class ConversationTurn:
    iteration: int
    role: str
    text: str
    # "APPROVED", "NEEDS REVISION", "FINAL_SAY" on reviewer turns; "" on proposer turns
    verdict: str


@dataclass
class ConversationLog:
    loop_name: str
    turns: list[ConversationTurn] = field(default_factory=list)


@dataclass
class LoopOutput:
    verdict: str
    log: ConversationLog
