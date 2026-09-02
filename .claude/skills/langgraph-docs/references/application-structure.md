# Application Structure

원문 : https://docs.langchain.com/oss/python/langgraph/application-structure

LangGraph 앱은 하나 이상의 그래프, 설정 파일(`langgraph.json`), 의존성 파일, 선택적 `.env`로 구성된다.
LangSmith Deployment 배포에 필요한 설정을 다룬다.

## 배포에 필요한 4가지

1. **`langgraph.json`** : 의존성·그래프·환경변수 지정.
2. **그래프** : 앱 로직 구현.
3. **의존성 파일** : `requirements.txt` / `pyproject.toml` / `package.json`.
4. **환경변수** : 실행에 필요한 값.

## 파일 구조 예

```
my-app/
├── my_agent/
│   ├── utils/
│   │   ├── tools.py     # 도구
│   │   ├── nodes.py     # 노드 함수
│   │   └── state.py     # 상태 정의
│   └── agent.py         # 그래프 구성 코드
├── .env                 # 환경변수
├── requirements.txt     # 의존성 (또는 pyproject.toml)
└── langgraph.json       # 설정 파일
```

> 주의 : 위 구조는 LangSmith Deployment 템플릿 관례이며 `__init__.py`를 포함한다.
> icodebroker 프로젝트는 네임스페이스 패키지(`__init__.py` 없음, src 레이아웃)를 쓰므로,
> 실제 통합 시 사용자 컨벤션을 따른다.

## `langgraph.json` 예

```json
{
  "dependencies": ["langchain_openai", "./your_package"],
  "graphs": {
    "my_agent": "./your_package/your_file.py:agent"
  },
  "env": "./.env"
}
```

- **dependencies** : 의존성. 시스템 라이브러리/바이너리는 `dockerfile_lines` 키로 추가.
- **graphs** : 이름→경로 매핑. 경로는 (1) 컴파일된 그래프 또는 (2) 그래프를 만드는 함수.
  여러 그래프 지정 가능(이름은 고유).
- **env** : `.env` 파일 경로 (로컬). 프로덕션은 배포 환경에서 환경변수 구성.

CLI는 현재 디렉터리의 `langgraph.json`을 기본 사용. 전체 키는 LangGraph 설정 파일 레퍼런스 참조 :
https://docs.langchain.com/langsmith/cli#configuration-file
