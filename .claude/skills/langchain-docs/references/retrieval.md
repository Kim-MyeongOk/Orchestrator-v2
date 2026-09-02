# 검색 (Retrieval / RAG)

원문 : https://docs.langchain.com/oss/python/langchain/retrieval

LLM에는 두 가지 핵심 한계가 있다.

- **유한한 컨텍스트** : 전체 코퍼스를 한 번에 넣을 수 없다.
- **정적 지식** : 학습 데이터가 특정 시점에 고정되어 있다.

Retrieval은 쿼리 시점에 관련 외부 지식을 가져와 이 문제를 해결한다. 이것이 **Retrieval-Augmented Generation (RAG)**의 토대다.

## 지식 베이스 구축

**지식 베이스(knowledge base)**는 검색에 사용되는 문서/구조화 데이터의 저장소다. 커스텀 지식 베이스가 필요하면 LangChain의 document loaders와 vector stores로 자신의 데이터에서 구축한다.

이미 지식 베이스가 있다면(SQL DB, CRM, 내부 문서 시스템 등) 재구축할 필요가 없다.

- Agentic RAG에서 에이전트의 **도구**로 연결한다.
- 조회한 뒤 검색된 내용을 LLM 컨텍스트로 공급한다 (2-Step RAG).

## 검색 파이프라인

전형적 흐름 : Sources(Google Drive, Slack, Notion 등) → Document Loaders → Documents → 청크 분할 → 임베딩 변환 → Vector Store. 사용자 쿼리 → 쿼리 임베딩 → Vector Store → Retriever → LLM이 검색 정보 사용 → 답변.

각 컴포넌트는 모듈식이다. 앱 로직을 다시 쓰지 않고 loader, splitter, embedding, vector store를 교체할 수 있다.

### 빌딩 블록

- **Document loaders** : 외부 소스에서 데이터를 수집해 표준화된 `Document` 객체를 반환한다.
- **Text splitters** : 큰 문서를 개별 검색 가능하고 모델 컨텍스트에 맞는 작은 청크로 나눈다.
- **Embedding models** : 텍스트를 숫자 벡터로 바꿔, 의미가 비슷한 텍스트가 벡터 공간에서 가까이 위치하게 한다.
- **Vector stores** : 임베딩 저장·검색에 특화된 데이터베이스.
- **Retrievers** : 비정형 쿼리를 받아 문서를 반환하는 인터페이스.

## RAG 아키텍처

| 아키텍처 | 설명 | 제어 | 유연성 | 지연 | 예시 |
|---|---|---|---|---|---|
| **2-Step RAG** | 생성 전에 항상 검색. 단순·예측 가능 | 높음 | 낮음 | 빠름 | FAQ, 문서 봇 |
| **Agentic RAG** | LLM 에이전트가 추론 중 언제·어떻게 검색할지 결정 | 낮음 | 높음 | 가변 | 여러 도구를 가진 리서치 어시스턴트 |
| **Hybrid** | 두 접근의 특성 + 검증 단계 결합 | 중간 | 중간 | 가변 | 품질 검증이 있는 도메인 특화 Q&A |

지연은 보통 2-Step RAG에서 더 예측 가능하다 (최대 LLM 호출 수가 알려지고 상한이 있음). 다만 실제 지연은 검색 단계 성능(API 응답, 네트워크 지연, DB 쿼리)의 영향도 받는다.

### 2-Step RAG

검색 단계가 생성 단계 전에 항상 실행된다. 단순·예측 가능하여 관련 문서 검색이 답변 생성의 명확한 전제 조건인 많은 응용에 적합하다.

흐름 : User Question → Retrieve Relevant Documents → Generate Answer → Return Answer.

### Agentic RAG

RAG의 강점과 에이전트 기반 추론을 결합한다. 답변 전에 문서를 검색하는 대신, 에이전트(LLM)가 단계별로 추론하며 상호작용 중 **언제·어떻게** 정보를 검색할지 결정한다. RAG 동작을 위해 에이전트에 필요한 유일한 것은 외부 지식을 가져올 수 있는 하나 이상의 **도구**(문서 로더, 웹 API, DB 쿼리 등)다.

```python
import requests
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

@tool
def fetch_url(url: str) -> str:
    """Fetch text content from a URL"""
    response = requests.get(url, timeout=10.0)
    response.raise_for_status()
    return response.text

system_prompt = "Use fetch_url when you need to fetch information from a web-page; quote relevant snippets."

agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[fetch_url],  # 검색용 도구
    system_prompt=system_prompt,
)
```

확장 패턴 : llms.txt를 먼저 로드하여 가용 문서 URL 목록을 얻고, `fetch_documentation` 도구로 사용자 질문에 맞는 내용을 동적으로 검색한다. `ALLOWED_DOMAINS`로 허용 도메인을 제한하는 것이 안전하다.

### Hybrid RAG

2-Step과 Agentic의 특성을 결합한다. 쿼리 전처리, 검색 검증, 생성 후 검사 같은 중간 단계를 도입한다. 고정 파이프라인보다 유연하면서도 실행에 대한 어느 정도의 제어를 유지한다.

전형적 컴포넌트 :

- **쿼리 향상(Query enhancement)** : 검색 품질 개선을 위해 입력 질문을 수정한다. 불명확한 쿼리 재작성, 여러 변형 생성, 추가 컨텍스트로 확장.
- **검색 검증(Retrieval validation)** : 검색된 문서가 관련 있고 충분한지 평가한다. 아니면 쿼리를 다듬어 재검색한다.
- **답변 검증(Answer validation)** : 생성된 답변의 정확성·완전성·출처 정합성을 검사한다. 필요하면 재생성/수정한다.

이 단계들 사이에서 여러 번 반복하는 구조를 흔히 지원한다. 모호하거나 불충분하게 명세된 쿼리, 검증/품질 관리 단계가 필요한 시스템, 여러 소스나 반복 개선이 관여하는 워크플로우에 적합하다.

---

참고 : icodebroker의 다단계 하이브리드 검색 아키텍처(약 21K 기술 문서 PostgreSQL 지식 베이스, 한국어 고려)는 위 Hybrid RAG 범주에 해당한다. 쿼리 향상 → 검색 → 검증 → 재검색 루프를 LangGraph 커스텀 워크플로우로 구성하면 제어와 유연성을 균형 맞출 수 있다.
