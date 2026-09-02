# LangSmith Studio

원문 : https://docs.langchain.com/oss/python/langgraph/studio

**LangSmith Studio**는 로컬에서 에이전트를 개발·테스트하는 무료 시각 인터페이스. 로컬 실행 에이전트에
연결해 각 스텝(모델에 보낸 프롬프트, 도구 호출·결과, 최종 출력)을 보여준다. 추가 코드/배포 없이
다른 입력 테스트, 중간 상태 검사, 동작 반복 개선.

## 사전 준비

- LangSmith 계정(무료) + API 키.
- LangSmith로 추적 데이터를 보내기 싫으면 `.env`에 `LANGSMITH_TRACING=false` → 데이터가 로컬 서버를 벗어나지 않음.

## 셋업

```bash
# 1. CLI 설치 (Python 3.11+)
pip install --upgrade "langgraph-cli[inmem]"
```

```python
# 2. 에이전트 준비 (예: create_agent — 컴파일된 그래프 반환)
from langchain.agents import create_agent
agent = create_agent("gpt-5.4", tools=[send_email], system_prompt="...")
```

```bash
# 3. .env에 API 키 (git에 커밋 금지)
LANGSMITH_API_KEY=lsv2...
```

```json
// 4. langgraph.json
{
  "dependencies": ["."],
  "graphs": {"agent": "./src/agent.py:agent"},
  "env": ".env"
}
```

```bash
# 5. 의존성 설치
pip install langchain langchain-openai   # 또는 uv add ...

# 6. 개발 서버 시작
langgraph dev
```

접속 :
- API : `http://127.0.0.1:2024`
- Studio UI : `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

> Safari는 localhost 연결 차단 → `langgraph dev --tunnel` 후 Studio UI에서 "Connect to a local server"로
> 터널 URL을 허용 origin에 추가.

## 기능

- 테스트 입력 실행 → 전체 실행 트레이스(프롬프트, 도구 인자/반환값, 토큰/지연 메트릭) 검사.
- 예외 발생 시 주변 상태와 함께 캡처.
- **핫 리로드** : 프롬프트·도구 시그니처 변경이 즉시 반영. 임의 스텝부터 스레드 재실행으로 변경 테스트.
- 단일 도구 에이전트부터 복잡한 멀티 노드 그래프까지 확장.
