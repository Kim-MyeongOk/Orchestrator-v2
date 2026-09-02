파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\agent\deep_agent_factory.py`

클래스 기능: `DeepAgentFactory` - 에이전트 그래프 팩토리 (모델·도구·체크포인터·미들웨어 조립 후 컴파일)

하위 함수 기능:
- `create(model_configuration, system_prompt, tool_list, checkpointer, subagent_list, middleware_list)`:
  컴파일된 LangGraph 그래프를 반환한다. **모델의 도구 호출 지원 여부에 따라 두 경로로 갈린다.**

## 두 가지 조립 경로

| 조건 | 조립 | 비고 |
|---|---|---|
| `tool_calling_enabled = True` (기본) | `deepagents.create_deep_agent` | `write_todos`·파일 도구 자동 바인딩, 서브에이전트(`task` 위임) 지원 |
| `tool_calling_enabled = False` | `langchain.agents.create_agent(tools = [])` | 도구 없음, 서브에이전트 불가 |

> ⚠️ **도구 미지원 모델에 deepagents 를 태우면 안 된다.**
> `create_deep_agent` 는 도구를 **항상** 바인딩하므로, 미지원 모델에서는 ollama 가
> 400 `"does not support tools"` 로 **턴을 통째로 실패**시킨다.
> 예 : `llama3.2-vision` 은 capabilities 가 `completion` · `vision` 뿐이다.

**도구 없는 경로에서도 유지되는 것** — `checkpointer` 와 `middleware_list` 를 그대로 넘기므로
대화 영속화, 생각 토큰 트리밍(`ThinkTrimmingMiddleware`), 컨텍스트 압축은 동일하게 동작한다.

**성립하지 않는 것** — 서브에이전트 위임(`task`)은 도구 호출이 전제라 이 경로에서는 쓸 수 없다.

## 인자 메모

- `checkpointer` : 주입 시 `thread_id` 기반 대화 상태가 영속화된다 (`None` 이면 비활성)
- `subagent_list` : 주입 시 메인 → `task()` → 서브에이전트 트리가 되어
  `astream(subgraphs=True)` 청크에 다단계 네임스페이스(`ns_path`)가 쌓인다
- `middleware_list` : `AgentMiddleware` 목록 (예 : 이미지 재주입 미들웨어)

관련 : `.claude/index/config/models.yaml.md` · `.claude/index/backend/app/llm/agent/chat_model_factory.md`
