import os
from datetime import date
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from src.domain.models import TemporalEdge, RiskAssessmentReport
from src.infrastructure.temporal_kg import TemporalKnowledgeGraph
from src.agents.workflow import RiskAssessmentWorkflow

kg = TemporalKnowledgeGraph()
workflow_app = None


def seed_initial_rules(graph: TemporalKnowledgeGraph) -> None:
    """Предзагрузка регламентов банка с разными версиями во времени."""
    graph.add_rule(
        TemporalEdge(
            source="Лимит_безакцептного_списания",
            relation="максимальная_сумма",
            target="500_000_руб",
            doc_id="Регламент_ОР_v1.2",
            valid_from=date(2023, 1, 1),
            valid_to=date(2024, 12, 31),
        )
    )
    graph.add_rule(
        TemporalEdge(
            source="Лимит_безакцептного_списания",
            relation="максимальная_сумма",
            target="100_000_руб",
            doc_id="Регламент_ОР_v2.0",
            valid_from=date(2025, 1, 1),
            valid_to=None,
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow_app
    seed_initial_rules(kg)
    workflow_app = RiskAssessmentWorkflow(kg).build_graph()
    yield


app = FastAPI(
    title="RiskGuard Multi-Agent Service",
    description="Оценка операционных рисков банка: LangGraph + Temporal GraphRAG + Guardrails",
    version="1.0.0",
    lifespan=lifespan,
)


class AuditRequest(BaseModel):
    query: str = Field(
        default="Оцени операционные риски процесса автосписания у партнера."
    )
    document_text: str = Field(
        default="Партнер списывает без акцепта суммы до 350 000 руб."
    )
    document_date: date = Field(default=date(2026, 3, 15))
    extracted_entities: List[str] = Field(default=["Лимит_безакцептного_списания"])


class AuditResponse(BaseModel):
    is_safe: bool
    security_reason: Optional[str] = None
    retrieved_rules: List[str] = []
    iterations_used: int = 0
    report: Optional[RiskAssessmentReport] = None


def get_langfuse_callbacks() -> list:
    """Подключает Langfuse трейсинг при наличии ключей в .env."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse.callback import CallbackHandler

            return [CallbackHandler()]
        except Exception:
            pass
    return []


@app.get("/health", tags=["health"])
async def healthcheck():
    return {"status": "ok"}


@app.post("/api/v1/audit", response_model=AuditResponse, tags=["audit"])
async def audit_process(req: AuditRequest) -> AuditResponse:
    if workflow_app is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")

    result = await workflow_app.ainvoke(
        {
            "query": req.query,
            "document_text": req.document_text,
            "document_date": req.document_date,
            "extracted_entities": req.extracted_entities,
            "revision_count": 0,
        },
        config={"callbacks": get_langfuse_callbacks(), "recursion_limit": 10},
    )

    return AuditResponse(
        is_safe=result["is_safe"],
        security_reason=result.get("security_reason"),
        retrieved_rules=result.get("retrieved_rules", []),
        iterations_used=result.get("revision_count", 0),
        report=result.get("report"),
    )


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", reload=True)
