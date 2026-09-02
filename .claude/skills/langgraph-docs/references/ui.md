# Agent Chat UI

원문 : https://docs.langchain.com/oss/python/langgraph/ui

**Agent Chat UI**는 어떤 LangChain 에이전트와도 상호작용하는 대화 인터페이스를 제공하는 Next.js 앱.
실시간 채팅, 도구 시각화, time-travel 디버깅·상태 fork 지원. `create_agent`로 만든 에이전트와 매끄럽게
연동되며, 로컬/배포 컨텍스트 모두 지원. 오픈소스(github.com/langchain-ai/agent-chat-ui).

> generative UI도 사용 가능 (LangSmith generative-ui-react 참조).

## 빠른 시작 (호스티드)

1. https://agentchat.vercel.app 방문
2. 배포 URL 또는 로컬 서버 주소 입력해 에이전트 연결
3. 채팅 시작 — 도구 호출·interrupt를 자동 감지·렌더링

## 로컬 개발

```bash
# npx
npx create-agent-chat-app --project-name my-chat-ui
cd my-chat-ui
pnpm install
pnpm dev

# 또는 저장소 클론
git clone https://github.com/langchain-ai/agent-chat-ui.git
cd agent-chat-ui && pnpm install && pnpm dev
```

## 에이전트 연결 설정

로컬·배포 에이전트 모두 연결 가능. 설정 항목 :
1. **Graph ID** : `langgraph.json`의 `graphs` 아래 그래프 이름.
2. **Deployment URL** : Agent server 엔드포인트 (로컬 `http://localhost:2024`, 또는 배포 URL).
3. **LangSmith API key** (선택) : 로컬 Agent server면 불필요.

설정 후 에이전트의 interrupted 스레드를 자동으로 가져와 표시. 도구 호출·결과 메시지 렌더링을 기본
지원하며, 표시 메시지 커스터마이징은 저장소 README의 "Hiding Messages in the Chat" 참조.
