# LangSmith Deployment

원문 : https://docs.langchain.com/oss/python/langgraph/deploy

**LangSmith Cloud**는 에이전트 워크로드를 위한 완전 관리형 호스팅. GitHub 저장소에서 직접 배포하면
인프라·스케일링·운영을 LangSmith가 처리한다. 전통 호스팅은 stateless·단명 웹앱용이지만 LangSmith
Cloud는 **상태 유지·장시간 에이전트(영속 상태·백그라운드 실행 필요)** 전용이다.

다른 배포 옵션 : control plane(하이브리드/셀프호스트), standalone 서버. (Deployment overview 참조)

## 사전 준비
- GitHub 계정 + LangSmith 계정(무료).

## 배포 단계

1. **GitHub 저장소 생성** : 앱을 LangGraph 호환으로 만들고(로컬 서버 셋업 가이드) 코드 push. 공개/비공개 모두 지원.
2. **LangSmith에 배포** : LangSmith 로그인 → 좌측 **Deployments** → **+ New Deployment** → GitHub 계정
   연결 → 저장소 선택 → **Submit**. 약 15분 소요.
3. **Studio에서 테스트** : 배포 선택 → 우상단 **Studio** 버튼.
4. **API URL 획득** : Deployment details에서 API URL 복사.

## API 테스트

```bash
pip install langgraph-sdk
```

```python
from langgraph_sdk import get_sync_client   # async는 get_client

client = get_sync_client(url="your-deployment-url", api_key="your-langsmith-api-key")
for chunk in client.runs.stream(
    None,       # threadless run
    "agent",    # langgraph.json에 정의된 에이전트 이름
    input={"messages": [{"role": "human", "content": "What is LangGraph?"}]},
    stream_mode="updates",
):
    print(chunk.event, chunk.data)
```

REST :
```bash
curl -s --request POST --url <DEPLOYMENT_URL>/runs/stream \
  --header 'Content-Type: application/json' \
  --header "X-Api-Key: <LANGSMITH API KEY>" \
  --data '{"assistant_id":"agent","input":{"messages":[{"role":"human","content":"What is LangGraph?"}]},"stream_mode":"updates"}'
```
