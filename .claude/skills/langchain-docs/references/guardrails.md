# Guardrails

원문 : https://docs.langchain.com/oss/python/langchain/guardrails

가드레일은 에이전트 실행의 핵심 지점에서 콘텐츠를 검증/필터링해 안전하고 규정 준수하는 AI 앱을
만든다. 용도 : PII 유출 방지, 프롬프트 인젝션 탐지/차단, 부적절/유해 콘텐츠 차단, 비즈니스 규칙/규정
준수, 출력 품질/정확성 검증. 미들웨어로 구현한다(에이전트 시작 전/완료 후, 모델/도구 호출 주위).

## 두 가지 접근법

- **결정적(Deterministic)** : 규칙 기반(정규식, 키워드 매칭, 명시적 체크). 빠르고 예측 가능하고
  저렴하지만 미묘한 위반은 놓칠 수 있다.
- **모델 기반(Model-based)** : LLM/분류기로 의미적 이해. 미묘한 문제를 잡지만 느리고 비싸다.

## 내장 가드레일

### PII 탐지

`PIIMiddleware`. 전략 : `redact`(`[REDACTED_TYPE]`), `mask`(부분 마스킹), `hash`(결정적 해시),
`block`(예외). 내장 타입 : `email`, `credit_card`(Luhn 검증), `ip`, `mac_address`, `url`.

```python
from langchain.agents.middleware import PIIMiddleware

agent = create_agent(model="gpt-5.4", tools=[...], middleware=[
    PIIMiddleware("email", strategy="redact", apply_to_input=True),
    PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
    PIIMiddleware("api_key", detector=r"sk-[a-zA-Z0-9]{32}", strategy="block", apply_to_input=True),
])
```

### Human-in-the-loop

고위험 작업 전 사람 승인. checkpointer 필요. (금융 거래, 운영 데이터 변경/삭제, 외부 통신 등)

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_agent(model="gpt-5.4", tools=[...],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={
        "send_email": True, "delete_database": True, "search": False,
    })],
    checkpointer=InMemorySaver())
```

## 커스텀 가드레일

### Before agent 가드레일

각 호출 시작 시 1회 요청 검증(인증, rate limit, 부적절 요청 차단). 결정적 예 :

```python
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config

class ContentFilterMiddleware(AgentMiddleware):
    def __init__(self, banned_keywords):
        super().__init__()
        self.banned_keywords = [kw.lower() for kw in banned_keywords]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime) -> dict | None:
        if not state["messages"]:
            return None
        first_message = state["messages"][0]
        if first_message.type != "human":
            return None
        content = first_message.content.lower()
        for keyword in self.banned_keywords:
            if keyword in content:
                return {
                    "messages": [{"role": "assistant",
                                 "content": "I cannot process requests containing inappropriate content."}],
                    "jump_to": "end",
                }
        return None
```

### After agent 가드레일

최종 출력을 사용자에게 반환하기 전 1회 검증(모델 기반 안전 체크, 품질 검증, 규정 준수 스캔).

```python
class SafetyGuardrailMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.safety_model = init_chat_model("gpt-5.4-mini")

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime) -> dict | None:
        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return None
        result = self.safety_model.invoke([{"role": "user",
            "content": f"Evaluate if safe. Respond 'SAFE' or 'UNSAFE'.\nResponse: {last_message.content}"}])
        if "UNSAFE" in result.content:
            last_message.content = "I cannot provide that response. Please rephrase your request."
        return None
```

### 다중 가드레일 조합 (계층 방어)

미들웨어 배열에 쌓아 순서대로 실행.

```python
agent = create_agent(model="gpt-5.4", tools=[...], middleware=[
    ContentFilterMiddleware(banned_keywords=["hack", "exploit"]),         # 입력 필터
    PIIMiddleware("email", strategy="redact", apply_to_input=True),       # PII 입력
    PIIMiddleware("email", strategy="redact", apply_to_output=True),      # PII 출력
    HumanInTheLoopMiddleware(interrupt_on={"send_email": True}),          # 사람 승인
    SafetyGuardrailMiddleware(),                                          # 모델 안전 체크
])
```
