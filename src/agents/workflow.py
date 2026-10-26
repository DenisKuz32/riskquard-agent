from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import AgentState
from src.domain.models import RiskAssessmentReport
from src.infrastructure.llm_client import get_llm
from src.infrastructure.guardrails import PromptGuardrailService
from src.infrastructure.temporal_kg import TemporalKnowledgeGraph


class CriticEvaluation(BaseModel):
    """Оценка отчета агентом-критиком на галлюцинации."""

    is_valid: bool = Field(
        description="True, если отчет строго опирается на правила и даты."
    )
    feedback: str = Field(description="Что нужно исправить аудитору, если есть ошибка.")


class RiskAssessmentWorkflow:
    def __init__(self, kg: TemporalKnowledgeGraph):
        self.kg = kg
        self.guardrail = PromptGuardrailService()
        self.auditor_llm = get_llm(temperature=0.1).with_structured_output(
            RiskAssessmentReport
        )
        self.critic_llm = get_llm(temperature=0.0).with_structured_output(
            CriticEvaluation
        )

    # --- УЗЕЛ 1: Защита от промпт-атак ---
    def guardrail_node(self, state: AgentState) -> dict:
        verdict = self.guardrail.check(state["query"], state["document_text"])
        return {
            "is_safe": verdict.is_safe,
            "security_reason": verdict.reason if not verdict.is_safe else None,
        }

    # --- УЗЕЛ 2: Темпоральный GraphRAG ретривер ---
    def temporal_retriever_node(self, state: AgentState) -> dict:
        rules = self.kg.retrieve_subgraph(
            entities=state["extracted_entities"], as_of_date=state["document_date"]
        )
        return {"retrieved_rules": rules}

    # --- УЗЕЛ 3: Агент-Аудитор операционных рисков ---
    def risk_auditor_node(self, state: AgentState) -> dict:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "Ты — ведущий AI-аудитор операционных рисков Сбера.\n"
                        "Проанализируй бизнес-процесс на соответствие внутренним регламентам банка, "
                        "актуальным на дату документа ({doc_date}).\n"
                        "Актуальные правила из Темпорального Графа Знаний:\n{rules}\n\n"
                        "Замечания критика с прошлой итерации (если есть): {feedback}"
                    ),
                ),
                ("human", "Запрос: {query}\nОписание процесса: {doc}"),
            ]
        )
        chain = prompt | self.auditor_llm
        report = chain.invoke(
            {
                "doc_date": state["document_date"],
                "rules": "\n".join(state["retrieved_rules"]) or "Правила не найдены",
                "feedback": state.get("critic_feedback") or "Нет",
                "query": state["query"],
                "doc": state["document_text"],
            }
        )
        return {"report": report, "revision_count": state.get("revision_count", 0) + 1}

    # --- УЗЕЛ 4: Агент-Критик (Hallucination & Temporal Grader) ---
    def critic_node(self, state: AgentState) -> dict:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "Ты — строгий верификатор (Critic Agent). Проверь отчет аудитора:\n"
                        "1. Все ли найденные риски опираются ТОЛЬКО на переданные правила из графа?\n"
                        "2. Учтена ли дата документа ({doc_date})?\n"
                        "Если аудитор выдумал правило или пропустил нарушение лимита — верни is_valid=False."
                    ),
                ),
                (
                    "human",
                    "Правила:\n{rules}\n\nДокумент:\n{doc}\n\nОтчет аудитора:\n{report}",
                ),
            ]
        )
        chain = prompt | self.critic_llm
        eval_res = chain.invoke(
            {
                "doc_date": state["document_date"],
                "rules": "\n".join(state["retrieved_rules"]),
                "doc": state["document_text"],
                "report": state["report"].model_dump_json(indent=2),
            }
        )
        return {"critic_feedback": None if eval_res.is_valid else eval_res.feedback}

    # --- Маршрутизаторы (Conditional Edges) ---
    @staticmethod
    def route_after_guardrail(state: AgentState) -> str:
        return "retriever" if state["is_safe"] else END

    @staticmethod
    def route_after_critic(state: AgentState) -> str:
        # Если критик доволен ИЛИ мы достигли лимита в 2 итерации (защита от бесконечного цикла)
        if not state.get("critic_feedback") or state.get("revision_count", 0) >= 2:
            return END
        return "auditor"

    def build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("guardrail", self.guardrail_node)
        builder.add_node("retriever", self.temporal_retriever_node)
        builder.add_node("auditor", self.risk_auditor_node)
        builder.add_node("critic", self.critic_node)

        builder.add_edge(START, "guardrail")
        builder.add_conditional_edges("guardrail", self.route_after_guardrail)
        builder.add_edge("retriever", "auditor")
        builder.add_edge("auditor", "critic")
        builder.add_conditional_edges("critic", self.route_after_critic)

        return builder.compile()
