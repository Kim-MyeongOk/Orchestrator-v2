# Run a Local Server

원문 : https://docs.langchain.com/oss/python/langgraph/local-server

LangGraph 애플리케이션을 로컬에서 실행하는 가이드. LangSmith API 키(무료) 필요.

## 1. CLI 설치 (Python 3.11+ 필요)

```bash
pip install -U "langgraph-cli[inmem]"
# 또는 uv add "langgraph-cli[inmem]"
```

## 2. 앱 생성 (템플릿)

```bash
langgraph new path/to/your/app --template new-langgraph-project-python
```

템플릿 미지정 시 인터랙티브 메뉴가 뜬다.

## 3. 의존성 설치 (edit 모드)

로컬 변경이 서버에 반영되도록 edit 모드로 설치한다.

```bash
cd path/to/your/app
pip install -e .   # 또는 uv sync
```

## 4. `.env` 작성

`.env.example`을 복사해 `.env`를 만들고 키를 채운다.

```bash
LANGSMITH_API_KEY=lsv2...
```

## 5. 서버 실행

```bash
langgraph dev
```

출력 예 :
- API : `http://127.0.0.1:2024`
- Studio UI : `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`
- API Docs : `http://127.0.0.1:2024/docs`

`langgraph dev`는 **in-memory 모드**로 개발/테스트용이다. 프로덕션은 영속 스토리지 백엔드가 있는
LangSmith Deployment를 사용한다.

> Safari는 localhost 연결 제한이 있어 `langgraph dev --tunnel`로 보안 터널을 만든다.

## 6. Studio에서 테스트

`langgraph dev` 출력의 Studio URL로 접속해 그래프를 시각화·디버그한다. 커스텀 host/port면
`baseUrl` 쿼리 파라미터를 수정한다.

## 7. API 테스트 (SDK)

```bash
pip install langgraph-sdk
```

```python
# 비동기
from langgraph_sdk import get_client
import asyncio

client = get_client(url="http://localhost:2024")

async def main():
    async for chunk in client.runs.stream(
        None,          # threadless run
        "agent",       # langgraph.json에 정의된 assistant 이름
        input={"messages": [{"role": "human", "content": "What is LangGraph?"}]},
    ):
        print(chunk.event, chunk.data)

asyncio.run(main())
```

```python
# 동기
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://localhost:2024")
for chunk in client.runs.stream(
    None, "agent",
    input={"messages": [{"role": "human", "content": "What is LangGraph?"}]},
    stream_mode="messages-tuple",
):
    print(chunk.event, chunk.data)
```

REST :
```bash
curl -s --request POST --url "http://localhost:2024/runs/stream" \
  --header 'Content-Type: application/json' \
  --data '{"assistant_id":"agent","input":{"messages":[{"role":"human","content":"What is LangGraph?"}]},"stream_mode":"messages-tuple"}'
```

## 다음 단계

- 배포 → `deploy.md`
- Studio → `studio.md`
