파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\config\models.yaml`

파일 기능: 모델 카탈로그. `.env` 의 `MODEL_*` 설정을 대체하며, 각 항목이 `ModelConfiguration` 필드와 1:1 매핑된다.
`${oc.env:VAR,default}` 는 OmegaConf 가 로드 시 환경변수로 치환한다 (시크릿은 `.env` 에 남긴다).

## 로드 경로 — 실행 위치에 주의

`.env` 의 `MODEL_CATALOG_PATH = config/models.yaml` 은 **상대 경로**다.
따라서 백엔드는 **프로젝트 루트를 cwd 로** 실행해야 한다 (`PYTHONPATH=backend`).

`backend/` 에서 실행하면 `ModelCatalog.load_default()` 가 파일을 못 찾아 **조용히 `None`** 을 반환하고,
`.env` 폴백의 기본값 `MODEL_PROVIDER=openai` 가 적용되어 다음 오류로 **기동이 실패**한다.

```
openai.OpenAIError: Missing credentials ... set the OPENAI_API_KEY environment variable
```

> 이 오류가 뜨면 API 키를 찾지 말고 **cwd 부터 확인**한다.

## 항목 필드

| 필드 | 의미 |
|---|---|
| `provider` | `ollama` / `google` / `openai` / `anthropic` / `lm_studio` / `vllm` |
| `name` | 프로바이더에 넘길 실제 모델명 |
| `enable` | `false` 면 UI 드롭다운(`GET /models`)에서 제외. 명시적으로 `false` 일 때만 비활성 |
| `reasoning_enabled` | **thinking 지원 여부 선언** — 아래 참고 |
| `context_token_count` | ollama `num_ctx`. 기본 4096 은 deepagents 프롬프트에 부족해 절단 → thinking 폭주 |

## `reasoning_enabled` 의 의미 — 주의

**`false` 는 "끄고 싶다"가 아니라 "이 모델은 thinking 을 못 쓴다"는 선언이다.**
`ChatModelFactory` 의 ollama 분기는 이 값이 `False` 면 요청별 생각 강도(UI 의 **생각 정도**)를
무시하고 `reasoning=False` 를 보낸다. 단순히 기본값만 끄고 싶다면 필드를 **지정하지 않는다**(`None`).

> 예전에는 생각 강도가 무조건 우선이라 thinking 미지원 모델에 `think` 가 전송되어
> Ollama 가 400 (`"...does not support thinking"`) 을 던지고 턴이 통째로 실패했다.
> 자세한 규칙은 `.claude/index/backend/app/llm/agent/chat_model_factory.md` 참고.

## ⚠️ `llama3_2_vision` 은 Ollama 버전에 묶여 있다

**Ollama 는 0.24.x 에 고정**한다. 자동 업데이트도 꺼져 있다.

신엔진(**0.30.0 이상**)이 `mllama` 아키텍처를 버려서 로드 자체가 실패한다.

```
unknown model architecture: 'mllama'
```

0.30.0 릴리스 노트에 "llama3.2-vision is not yet supported" 로 명시돼 있고,
llama.cpp 본류는 mllama 를 지원한 적이 없다 (Ollama 사설 포크에만 있던 기능).

> **비전이 갑자기 깨지면 가장 먼저 `ollama --version` 을 확인한다.**
> 자동 업데이트로 0.30+ 가 올라온 것이 유력하다.

0.24.0 에서 `gpt-oss:120b-cloud`(기본 모델) · `qwen3-vl:4b` · `qwen3.5:27b` 모두 정상 동작을 확인했다.
