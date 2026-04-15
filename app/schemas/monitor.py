from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' si el servicio está operativo")
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StrategyStats(BaseModel):
    DOM: int = 0
    CV: int = 0
    HISTORY: int = 0


class MetricsResponse(BaseModel):
    project: str
    total_healings: int
    by_strategy: StrategyStats
    avg_confidence: float = Field(ge=0.0, le=1.0)


class HealingEventResponse(BaseModel):
    id: int
    project: str
    test_id: str
    original_selector: str
    healed_selector: str
    selector_type: str
    strategy: str
    confidence: float
    healed_at: datetime
    feedback_correct: bool | None = None
    confirmed_selector: str | None = None
    feedback_at: datetime | None = None

    @classmethod
    def from_orm(cls, event) -> HealingEventResponse:
        return cls(
            id=event.id,
            project=event.project,
            test_id=event.test_id,
            original_selector=event.original_selector,
            healed_selector=event.healed_selector,
            selector_type=event.selector_type,
            strategy=event.strategy,
            confidence=event.confidence,
            healed_at=event.healed_at,
            feedback_correct=event.feedback_correct,
            confirmed_selector=event.confirmed_selector,
            feedback_at=event.feedback_at,
        )


class HistoryResponse(BaseModel):
    project: str
    total: int
    items: list[HealingEventResponse]
