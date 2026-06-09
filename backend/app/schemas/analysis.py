from pydantic import BaseModel, Field


class PainPoint(BaseModel):
    id: str = ""
    title: str
    description: str
    frequency: int = Field(default=0, ge=0, description="How often this pain is mentioned")
    severity_score: float = Field(default=5.0, ge=0, le=10, description="Severity from 0-10")
    evidence: list[str] = Field(default_factory=list, description="Supporting quotes or sources")


class TrendSignal(BaseModel):
    id: str = ""
    title: str
    description: str
    trend_score: float = Field(ge=0, le=100, description="Growth signal strength 0-100")
    confidence: float = Field(ge=0, le=1, description="Confidence level 0-1")


class MarketGap(BaseModel):
    id: str = ""
    title: str
    description: str
    opportunity_score: float = Field(ge=0, le=100, description="How promising this gap is")
    pain_points: list[str] = Field(default_factory=list, description="Related pain point IDs")
    supporting_trends: list[str] = Field(default_factory=list, description="Related trend IDs")


class Opportunity(BaseModel):
    id: str = ""
    title: str
    description: str
    market_size_estimate: str = Field(default="unknown", description="Estimated market size")
    confidence_score: float = Field(default=50.0, ge=0, le=100, description="Confidence 0-100")
    implementation_difficulty: str = Field(default="medium", description="easy/medium/hard")


class ValidationCheck(BaseModel):
    check_name: str
    passed: bool
    score: float = Field(ge=0, le=1)
    details: str = ""


class ValidatedOpportunity(BaseModel):
    opportunity: Opportunity
    overall_score: float = Field(ge=0, le=100)
    checks: list[ValidationCheck] = Field(default_factory=list)
    validated: bool = False


class Report(BaseModel):
    query: str
    executive_summary: str = ""
    top_pain_points: list[PainPoint] = Field(default_factory=list)
    top_trends: list[TrendSignal] = Field(default_factory=list)
    top_market_gaps: list[MarketGap] = Field(default_factory=list)
    top_opportunities: list[ValidatedOpportunity] = Field(default_factory=list)
    recommendation: str = ""
    metadata: dict = Field(default_factory=dict)
