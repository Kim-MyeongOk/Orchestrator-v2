# LangSmith Observability

원문 : https://docs.langchain.com/oss/python/langgraph/observability

**트레이스**는 입력→출력 단계 시퀀스이고 각 단계는 **run**이다. LangSmith로 실행 단계를 시각화한다.
디버그(로컬 실행), 성능 평가, 모니터링 가능. LangSmith 계정 + API 키 필요.

## 추적 활성화

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<your-api-key>
```

기본 프로젝트명은 `default`.

## 선택적 추적

```python
import langsmith as ls

with ls.tracing_context(enabled=True):
    agent.invoke({"messages": [...]})   # 추적됨

agent.invoke({"messages": [...]})       # LANGSMITH_TRACING 미설정 시 추적 안 됨
```

## 프로젝트 지정

```bash
export LANGSMITH_PROJECT=my-agent-project   # 정적
```

```python
with ls.tracing_context(project_name="email-agent-test", enabled=True):   # 동적
    agent.invoke({"messages": [...]})
```

## 트레이스에 메타데이터/태그

```python
agent.invoke(
    {"messages": [...]},
    config={
        "tags": ["production", "email-assistant", "v1.0"],
        "metadata": {"user_id": "user_123", "session_id": "session_456", "environment": "production"},
    },
)
# tracing_context도 tags/metadata 인자를 받음
```

## 익명화 (민감 데이터 마스킹)

트레이스에 기록되기 전 민감 데이터를 마스킹. 예: SSN 형식(XXX-XX-XXXX) 레닥션.

```python
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client
from langsmith.anonymizer import create_anonymizer

anonymizer = create_anonymizer([
    {"pattern": r"\b\d{3}-?\d{2}-?\d{4}\b", "replace": "<ssn>"},
])
tracer_client = Client(anonymizer=anonymizer)
tracer = LangChainTracer(client=tracer_client)

graph = StateGraph(MessagesState)...compile().with_config({"callbacks": [tracer]})
```
