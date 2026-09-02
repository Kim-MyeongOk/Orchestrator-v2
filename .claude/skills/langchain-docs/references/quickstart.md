# Quickstart

원문 : https://docs.langchain.com/oss/python/langchain/quickstart

몇 분 안에 동작하는 AI 에이전트를 만든다.

## 의존성 설치

```bash
# uv
uv init
uv add langchain deepagents
uv sync

# pip
pip install -U langchain deepagents
```

## API 키 설정

지원 프로바이더에서 API 키를 발급받아 환경변수로 설정한다.

```bash
export OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."
export ANTHROPIC_API_KEY="..."
# Azure: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME
# Bedrock: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
```

## 기본 에이전트 만들기

```python
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

## 실전 에이전트 만들기 (단계별)

핵심 개념 6가지를 다룬다 : 상세 시스템 프롬프트, 외부 데이터 연동 도구, 모델 설정,
대화형 메모리, Deep Agents, 테스트.

### 1. 시스템 프롬프트 정의

역할과 동작을 구체적이고 실행 가능하게 정의한다.

```python
SYSTEM_PROMPT = """You are a literary data assistant.

## Capabilities

- `fetch_text_from_url`: loads document text from a URL into the conversation.
Do not guess line counts or positions—ground them in tool results from the saved file."""
```

### 2. 도구 생성

`@tool` 데코레이터로 함수를 도구로 만든다. 도구의 이름/설명/인자명이 모델 프롬프트의 일부가
되므로 잘 문서화해야 한다. 도구는 런타임 컨텍스트(`ToolRuntime`)에 의존하거나 에이전트
메모리와 상호작용할 수 있다.

```python
import urllib.error
import urllib.request

from langchain.tools import tool

@tool
def fetch_text_from_url(url: str) -> str:
    """Fetch the document from a URL."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; quickstart-research/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        return f"Fetch failed: {e}"
    return raw.decode("utf-8", errors="replace")
```

### 3. 모델 설정

`init_chat_model`로 모델을 초기화하고 파라미터를 지정한다.

```python
from langchain.chat_models import init_chat_model

model = init_chat_model(
    "claude-sonnet-4-6",
    temperature=0.5,
    timeout=600,
    max_tokens=25000,
    streaming=True,
)
```

### 4. 메모리 추가

상호작용 간 상태를 유지하기 위해 checkpointer를 추가한다. 운영 환경에서는 메시지 히스토리를
DB에 저장하는 영속적 checkpointer를 사용한다.

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
```

### 5. 에이전트 생성 및 실행

에이전트 생성 프레임워크는 두 가지(LangChain agents / deep agents)다. 둘 다 도구/메모리 등에
대한 세밀한 제어를 제공한다. 차이는 deep agents가 계획(planning), 파일시스템 도구, 서브에이전트
같은 유용한 기능을 기본 내장한다는 점이다. 최대 기능을 최소 설정으로 원하면 deep agents,
세밀한 제어가 필요하면 LangChain agents를 선택한다.

```python
from langchain.agents import create_agent
from deepagents import create_deep_agent

agent = create_agent(
    model=model,
    tools=[fetch_text_from_url],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

deep_agent = create_deep_agent(
    model=model,
    tools=[fetch_text_from_url],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"configurable": {"thread_id": "great-gatsby-lc"}},
)
```

`thread_id`를 `config.configurable`에 넘기면 해당 스레드의 대화 상태가 유지된다.

### 6. 결과 비교

deep agent는 `write_todos`로 작업을 계획하고, 파일을 로드하고, 파일시스템 도구(`grep`,
`read_file`)로 컨텍스트를 관리하며, 필요시 서브에이전트를 스폰한다. LangChain agent로 동일한
수준을 얻으려면 더 많은 기능을 직접 구현해야 한다.

## 트레이싱

LangSmith로 에이전트 내부 호출을 관찰한다.

```bash
export LANGSMITH_TRACING="true"
export LANGSMITH_API_KEY="..."
```
