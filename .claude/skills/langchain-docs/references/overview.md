# LangChain Overview

원문 : https://docs.langchain.com/oss/python/langchain/overview

## 핵심 개념

**Agent = Model + Harness.** LangChain은 `create_agent`라는 최소하면서도 고도로 구성 가능한
에이전트 하네스(harness)를 제공한다. 하네스란 모델 루프를 둘러싼 모든 것(프롬프트, 도구,
동작을 조정하는 미들웨어)을 의미한다. 프리미티브에서 시작해 유스케이스에 필요한 만큼만 조합한다.

OpenAI, Anthropic, Google 등 다양한 프로바이더를 지원한다.

## LangChain vs LangGraph vs Deep Agents vs LangSmith

- **Deep Agents** : 자동 컨텍스트 압축, 가상 파일시스템, 서브에이전트 스폰 등이 포함된
  "배터리 포함형(batteries-included)" 에이전트. LangChain agents 위에 구축됨.
- **LangChain** (`create_agent`) : 유스케이스/데이터에 맞춰 쉽게 커스터마이즈 가능한 고도로
  구성 가능한 하네스.
- **LangGraph** : 결정적(deterministic) 워크플로우와 에이전트형 워크플로우를 결합하는 고급
  요구사항을 위한 저수준 오케스트레이션 프레임워크.
- **LangSmith** : 위 프레임워크들로 만든 에이전트를 추적/디버그/평가. `LANGSMITH_TRACING=true`와
  API 키 설정으로 시작.

## 에이전트 생성 예제

```python
# pip install -qU langchain "langchain[anthropic]"
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in San Francisco?"}]}
)
print(result["messages"][-1].content_blocks)
```

### 프로바이더별 model 문자열 예시

| 프로바이더 | 패키지 | model 인자 |
|---|---|---|
| OpenAI | `langchain[openai]` | `"openai:gpt-5.5"` |
| Google Gemini | `langchain[google-genai]` | `"google_genai:gemini-2.5-flash-lite"` |
| Anthropic | `langchain[anthropic]` | `"claude-sonnet-4-6"` |
| OpenRouter | `langchain-openrouter` | `"openrouter:anthropic/claude-sonnet-4-6"` |
| Fireworks | `langchain-fireworks` | `"fireworks:accounts/..."` |
| Ollama | `langchain-ollama` | `"ollama:devstral-2"` |
| Azure | `langchain[openai]` | `"azure_openai:gpt-5.5"` + `azure_deployment=...` |
| AWS Bedrock | `langchain-aws` | `model="...", model_provider="bedrock_converse"` |
| HuggingFace | `langchain[huggingface]` | `model="...", model_provider="huggingface"` |

## 핵심 이점

1. **표준 모델 인터페이스** : 채팅 모델/임베딩 등을 프로바이더 전반에 걸쳐 하나의 인터페이스로
   사용. 최소한의 코드 변경으로 모델 교체 가능.
2. **고도로 구성 가능한 하네스** : `create_agent`를 최소 하네스로 시작하고 미들웨어를 통해 점진적으로
   기능 추가(가드레일, 재시도, 라우팅, 커스텀 도구 정책 등).
3. **LangGraph 기반** : durable execution, human-in-the-loop, 영속성 등을 활용.
4. **LangSmith로 디버그** : 트레이스, 도구 호출, 상태 전이, 지연시간을 한 곳에서 관찰.

## 참고

전체 문서 인덱스 : https://docs.langchain.com/llms.txt
