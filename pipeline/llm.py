"""LLM 접근 계층. 에이전트는 이 얇은 인터페이스만 알고, 제공사는 LLM_MODEL 로 바꾼다."""
from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLM(Protocol):
    name: str

    def structured(self, system: str, user: str, schema: type[T]) -> T: ...


class LangChainLLM:
    """`provider:model` 문자열 하나로 Gemini / Claude / OpenAI 를 바꿔 끼운다."""

    def __init__(self, model_spec: str, temperature: float = 0.4):
        from langchain.chat_models import init_chat_model

        self.name = model_spec
        self._model = init_chat_model(model_spec, temperature=temperature)

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        runnable = self._model.with_structured_output(schema)
        result = runnable.invoke([("system", system), ("human", user)])
        return result if isinstance(result, schema) else schema.model_validate(result)


def get_llm(model_spec: str) -> LLM | None:
    """모델이 설정되지 않았거나 초기화에 실패하면 None → 에이전트가 템플릿으로 폴백."""
    if not model_spec:
        return None
    try:
        return LangChainLLM(model_spec)
    except Exception as exc:  # 키 누락, 패키지 미설치 등
        print(f"[llm] '{model_spec}' 초기화 실패, 템플릿 모드로 진행: {exc}")
        return None
