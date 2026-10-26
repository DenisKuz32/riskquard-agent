from datetime import date
from typing import TypedDict, List, Optional
from src.domain.models import RiskAssessmentReport


class AgentState(TypedDict):
    """Единый State мультиагентной системы в LangGraph."""

    query: str  # Запрос аналитика
    document_text: str  # Проверяемый бизнес-процесс / документ
    document_date: date  # Дата документа (для Temporal GraphRAG!)
    extracted_entities: List[str]  # Сущности для поиска в графе
    # Временной контекст из графа знаний
    retrieved_rules: List[str]
    # Результат работы Guardrail
    is_safe: bool
    security_reason: Optional[str]
    # Черновик и финальный отчет аудитора
    report: Optional[RiskAssessmentReport]
    # Поля для цикла самокоррекции (Reflection Loop)
    critic_feedback: Optional[str]
    revision_count: int  # Счетчик итераций (защита от бесконечного цикла!)
