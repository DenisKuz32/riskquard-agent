from datetime import date
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TemporalEdge(BaseModel):
    """Ребро темпорального графа знаний с учетом версионности."""

    source: str
    relation: str
    target: str
    doc_id: str
    valid_from: date
    valid_to: Optional[date] = None  # None означает, что правило действует сейчас

    def is_active_at(self, query_date: date) -> bool:
        if self.valid_to is None:
            return self.valid_from <= query_date
        return self.valid_from <= query_date <= self.valid_to


class RiskFinding(BaseModel):
    """Конкретное найденное нарушение или операционный риск."""

    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rule_violated: str = Field(description="ID документа и суть нарушенного правила")
    explanation: str = Field(description="Почему это является риском с учетом даты")


class RiskAssessmentReport(BaseModel):
    """Структурированный ответ агента-аудитора (Structured Output)."""

    is_compliant: bool
    overall_risk_score: int = Field(ge=0, le=100)
    findings: List[RiskFinding]
    reasoning_summary: str
