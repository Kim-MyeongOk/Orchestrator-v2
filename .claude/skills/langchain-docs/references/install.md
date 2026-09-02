# Install

원문 : https://docs.langchain.com/oss/python/langchain/install

## 기본 설치

```bash
pip install -U langchain
# Python 3.10+ 필요
```

`uv` 사용 시 :

```bash
uv add langchain
```

## 프로바이더 통합 패키지

LangChain은 수백 개의 LLM과 수천 개의 통합을 제공하며, 이들은 독립적인 프로바이더 패키지로 존재한다.

```bash
# OpenAI 통합
pip install -U langchain-openai

# Anthropic 통합
pip install -U langchain-anthropic
```

전체 통합 목록 : https://docs.langchain.com/oss/python/integrations/providers/overview

## 다음 단계

설치 후 Quickstart 가이드(references/quickstart.md)로 진행한다.
