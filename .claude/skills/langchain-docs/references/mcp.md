# Model Context Protocol (MCP)

원문 : https://docs.langchain.com/oss/python/langchain/mcp

MCP는 애플리케이션이 LLM에 도구/컨텍스트를 제공하는 방식을 표준화하는 오픈 프로토콜이다.
LangChain 에이전트는 `langchain-mcp-adapters` 라이브러리로 MCP 서버의 도구를 사용한다.

## Quickstart

```bash
pip install langchain-mcp-adapters
```

`MultiServerMCPClient`는 **기본적으로 stateless**다. 각 도구 호출마다 새 MCP `ClientSession`을
생성하고, 도구를 실행한 뒤 정리한다.

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",            # 로컬 서브프로세스
        "command": "python",
        "args": ["/path/to/math_server.py"],
    },
    "weather": {
        "transport": "http",             # HTTP 원격 서버
        "url": "http://localhost:8000/mcp",
    },
})

tools = await client.get_tools()
agent = create_agent("claude-sonnet-4-6", tools)
response = await agent.ainvoke({"messages": [{"role": "user", "content": "..."}]})
```

## 커스텀 서버 (FastMCP)

```python
from fastmcp import FastMCP

mcp = FastMCP("Math")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## Transports

### HTTP (`http` = streamable-http)

```python
client = MultiServerMCPClient({"weather": {"transport": "http", "url": "http://localhost:8000/mcp"}})
```

**헤더 전달** (인증/트레이싱) — `sse`(MCP 스펙상 deprecated), `streamable_http`에서 지원 :

```python
"weather": {
    "transport": "http",
    "url": "http://localhost:8000/mcp",
    "headers": {"Authorization": "Bearer YOUR_TOKEN", "X-Custom-Header": "custom-value"},
}
```

**인증** — `httpx.Auth` 인터페이스 구현(공식 MCP SDK 사용) :

```python
"weather": {"transport": "http", "url": "...", "auth": auth}
```

### stdio

클라이언트가 서버를 서브프로세스로 실행하고 표준 입출력으로 통신. 로컬 도구/단순 설정에 적합.
서브프로세스는 클라이언트 연결 동안 유지(본질적으로 stateful)되지만, 명시적 세션 관리 없이는 각
도구 호출이 여전히 새 세션을 생성한다.

## Stateful sessions

상태를 유지하는 서버에선 `client.session()`으로 영속 `ClientSession`을 생성한다.

```python
from langchain_mcp_adapters.tools import load_mcp_tools

async with client.session("server_name") as session:
    tools = await load_mcp_tools(session)
    agent = create_agent("google_genai:gemini-3.1-pro-preview", tools)
```

## 핵심 기능

### Tools

`client.get_tools()`로 MCP 도구를 LangChain 도구로 변환해 로드.

**구조화 콘텐츠(structured content)** : MCP 도구가 `structuredContent`를 반환하면 어댑터가
`MCPToolArtifact`로 감싸 `ToolMessage.artifact`로 반환.

```python
for message in result["messages"]:
    if isinstance(message, ToolMessage) and message.artifact:
        structured_content = message.artifact["structured_content"]
```

interceptor로 대화 히스토리에 추가 가능(모델에게 보이게).

**멀티모달 콘텐츠** : 이미지/텍스트 등 여러 파트는 표준 content blocks로 변환되어
`ToolMessage.content_blocks`로 접근.

### Resources

MCP 리소스(파일/DB 레코드/API 응답)를 `Blob` 객체로 변환.

```python
blobs = await client.get_resources("server_name")
blobs = await client.get_resources("server_name", uris=["file:///path/to/file.txt"])
# 또는 세션으로: load_mcp_resources(session, uris=[...])
```

### Prompts

MCP 프롬프트 템플릿을 메시지로 변환.

```python
messages = await client.get_prompt("server_name", "summarize")
messages = await client.get_prompt("server_name", "code_review",
                                   arguments={"language": "python", "focus": "security"})
```

## 고급 기능

### Tool interceptors

MCP 서버는 별도 프로세스라 LangGraph 런타임 정보(store/context/state)에 접근 못 한다. **인터셉터가
이 간극을 메운다** — MCP 도구 실행 중 런타임 컨텍스트 접근 + 미들웨어 같은 제어(요청 수정, 재시도,
헤더 동적 추가, 단락).

`create_agent`와 함께 쓰면 인터셉터가 `request.runtime`(tool_call_id, state, config, store)에 접근.

```python
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

async def inject_user_context(request: MCPToolCallRequest, handler):
    """Inject user credentials into MCP tool calls."""
    user_id = request.runtime.context.user_id
    modified = request.override(args={**request.args, "user_id": user_id})
    return await handler(modified)

client = MultiServerMCPClient({...}, tool_interceptors=[inject_user_context])
```

- **Store 접근** : `request.runtime.store.get(...)`로 사용자 선호 조회.
- **State 접근** : `request.runtime.state`로 인증 상태 확인 후 민감 도구 차단(`ToolMessage` 반환).
- **Tool call ID** : `request.runtime.tool_call_id`로 응답 포맷팅/추적.

**상태 업데이트와 Command** : 인터셉터가 `Command`를 반환해 상태 갱신/그래프 흐름 제어.

```python
from langgraph.types import Command

async def handle_task_completion(request, handler):
    result = await handler(request)
    if request.name == "submit_order":
        return Command(update={"task_status": "completed"}, goto="summary_agent")
    return result
# goto="__end__"로 조기 종료
```

**커스텀 인터셉터 패턴** : async 함수가 request와 handler를 받음. "양파(onion)" 패턴 — 리스트
첫 번째가 최외곽.

```python
async def logging_interceptor(request: MCPToolCallRequest, handler):
    print(f"Calling tool: {request.name} with args: {request.args}")
    result = await handler(request)
    return result

# 요청 수정: request.override(args=..., headers=...)
# 조합: tool_interceptors=[outer, inner] → outer before → inner before → tool → inner after → outer after
# 에러 처리/재시도: try/except + asyncio.sleep(지수 백오프)
```

### Progress notifications / Logging

장시간 도구 실행의 진행 업데이트와 서버 로그 구독.

```python
from langchain_mcp_adapters.callbacks import Callbacks, CallbackContext

async def on_progress(progress, total, message, context: CallbackContext):
    percent = (progress / total * 100) if total else progress
    print(f"[{context.server_name}] {percent:.1f}% - {message}")

client = MultiServerMCPClient({...}, callbacks=Callbacks(on_progress=on_progress))
# on_logging_message=... 로 로그 구독
```

`CallbackContext` : `server_name`, `tool_name`.

### Elicitation

MCP 서버가 도구 실행 중 사용자에게 추가 입력을 대화형으로 요청. 서버는 `ctx.elicit(message=...,
schema=...)`, 클라이언트는 `on_elicitation` 콜백 제공.

```python
from mcp.types import ElicitResult

async def on_elicitation(mcp_context, params, context) -> ElicitResult:
    return ElicitResult(action="accept", content={"email": "user@example.com", "age": 25})

client = MultiServerMCPClient({...}, callbacks=Callbacks(on_elicitation=on_elicitation))
```

응답 액션 : `accept`(유효 입력, `content` 포함), `decline`(제공 거부), `cancel`(작업 취소).

## 참고

- MCP 문서 : https://modelcontextprotocol.io/introduction
- `langchain-mcp-adapters` : https://github.com/langchain-ai/langchain-mcp-adapters
