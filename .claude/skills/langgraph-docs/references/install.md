# Install LangGraph

원문 : https://docs.langchain.com/oss/python/langgraph/install

## 기본 설치

```bash
pip install -U langgraph
# 또는 uv add langgraph
```

## LangChain 함께 설치 (모델/도구용)

LangGraph로 LLM에 접근하고 도구를 정의하려면 보통 LangChain을 함께 쓴다 (필수는 아님).

```bash
pip install -U langchain
# Python 3.10+ 필요
# 또는 uv add langchain
```

프로바이더별 패키지(`langchain-openai`, `langchain-anthropic` 등)는 별도로 설치한다.
프로바이더별 설치는 integrations 문서 참조 :
https://docs.langchain.com/oss/python/integrations/providers/overview

## Python 요구사항

- Python **3.10+**

## 영속성 백엔드 (선택)

체크포인터/스토어 백엔드는 별도 패키지로 제공된다.

```bash
pip install -U langgraph-checkpoint-postgres   # PostgresSaver / PostgresStore
pip install -U langgraph-checkpoint-sqlite      # SqliteSaver
```
