from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RangeSpec(BaseModel):
    min: float
    max: float
    step: float


class Molecule(BaseModel):
    label: str
    smiles: str


class HeatmapBestPoint(BaseModel):
    temperature_c: float
    meoh_pct: float
    optimization_metric_s: float
    # Deprecated alias retained for backwards compatibility.
    quality_score: float


class Landscape(BaseModel):
    temp_axis: list[float]
    meoh_axis: list[float]
    values: list[list[float]]
    best_point: HeatmapBestPoint


class DemoPreset(BaseModel):
    preset_id: str
    name: str
    description: str
    temperature_range: RangeSpec
    meoh_range: RangeSpec
    molecules: list[Molecule]
    landscape: Landscape


class PresetsResponse(BaseModel):
    presets: list[DemoPreset]


class SimulationRequest(BaseModel):
    preset_id: str
    temperature_c: float = Field(ge=25.0, le=80.0)
    meoh_pct: float = Field(ge=0.0, le=100.0)


class Peak(BaseModel):
    label: str
    smiles: str
    retention_time_s: float


class ChartPoint(BaseModel):
    x: float
    y: float


class HeatmapPoint(BaseModel):
    temperature_c: float
    meoh_pct: float
    optimization_metric_s: float
    # Deprecated alias retained for backwards compatibility.
    quality_score: float
    best_point: HeatmapBestPoint


class SummaryMetrics(BaseModel):
    min_separation_s: float
    max_retention_s: float
    critical_resolution: float
    optimization_metric_s: float
    # Deprecated alias retained for backwards compatibility.
    quality_score: float


class SimulationResponse(BaseModel):
    preset_id: str
    peaks: list[Peak]
    chromatogram_series: list[ChartPoint]
    heatmap_point: HeatmapPoint
    summary_metrics: SummaryMetrics


class ContactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    company: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=10, max_length=2000)


class ContactResponse(BaseModel):
    status: str


class PublicConfigResponse(BaseModel):
    booking_url: str
    analytics_key: str | None = None


class AnalyticsEventRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    payload: dict = Field(default_factory=dict)


class AnalyticsEventResponse(BaseModel):
    status: str


class SmilesNameResolveRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    smiles: str = Field(min_length=1, max_length=400)


class SmilesNameResolveResponse(BaseModel):
    smiles: str
    resolved_name: str
    source: str
    candidates: list[str] = Field(default_factory=list)


class FollowUpChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class FollowUpMobilePhase(BaseModel):
    solvent: str | None = None
    additive: str | None = None
    ph_estimate: float | None = None


class FollowUpGradientPoint(BaseModel):
    time_min: float
    percent_b: float


class FollowUpRecommendationContext(BaseModel):
    paper_id: str
    title: str
    citation: str | None = None
    rationale: str | None = None
    core_method_summary: str | None = None
    flow_rate_ml_min: float | None = None
    run_time_min: float | None = None
    column_temperature_c: float | None = None
    is_scaled: bool = False
    mobile_phase_a: FollowUpMobilePhase | None = None
    mobile_phase_b: FollowUpMobilePhase | None = None
    gradient_profile: list[FollowUpGradientPoint] = Field(default_factory=list)
    isocratic_percent_b: float | None = None
    trust_state: str | None = None
    validation_status: str | None = None
    warning_summary: list[str] = Field(default_factory=list)
    scaling_notes: list[str] = Field(default_factory=list)
    dominant_differentiator: str | None = None


class FollowUpChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)
    request_text: str = Field(default="", max_length=4000)
    source_mode: str | None = None
    runtime_mode: str | None = None
    result_origin: str | None = None
    system_summary: str | None = None
    search_query_used: str | None = None
    recommendations_count: int = Field(default=0, ge=0, le=50)
    active_recommendation: FollowUpRecommendationContext | None = None
    history: list[FollowUpChatMessage] = Field(default_factory=list)


class FollowUpChatResponse(BaseModel):
    answer: str
    source: str
