##################################################
# 게이트웨이 프록시 라우터 테스트
# 실제 게이트웨이 없이 httpx.MockTransport 로 업스트림을 흉내 내어
# URL 조립 / 인증 헤더 주입 / 모델명 주입 / stream 분기를 검증한다.
# (프로젝트 관례에 따라 동기 test_ 함수 안에서 asyncio.run 으로 실행한다)
##################################################

import json
import asyncio

import httpx

from omegaconf                    import OmegaConf
from fastapi                      import FastAPI
from httpx                        import ASGITransport

from app.llm.agent.model_catalog  import ModelCatalog
from app.llm.model.gateway_router import GatewayRouter
from app.llm.model                import base_llm as base_llm_module

CATALOG_YAML_TEXT = """
default_model : gpt_oss_120b
model_info :
    gpt_oss_120b :
        provider                  : vllm
        name                      : gpt-oss-120b
        base_url                  : http://gateway.test/gpt-oss-120b
        api_key                   : secret-key
        timeout_second_count      : 30.0
        default_header_dictionary :
            Send-System-Name : test-system
            User-Id          : tester
    gemini_default :
        provider : google
        name     : gemini-3.5-flash
"""


def _load_test_catalog() -> ModelCatalog:
    catalog_dictionary    = OmegaConf.to_container(OmegaConf.create(CATALOG_YAML_TEXT), resolve = True)
    model_info_dictionary = catalog_dictionary["model_info"]
    return ModelCatalog(catalog_dictionary["default_model"], model_info_dictionary)


def _build_test_application(monkeypatch, gateway_handler) -> FastAPI:
    # base_llm 이 만드는 httpx.AsyncClient 에 MockTransport 를 주입해 업스트림 게이트웨이를 흉내 낸다
    native_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        # base_llm 은 transport 를 넘기지 않으므로 그 경우에만 MockTransport 를 주입한다.
        # (테스트용 ASGI 클라이언트는 transport 를 명시하므로 그대로 둔다 — 전역 httpx 를 오염시키지 않음)
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(gateway_handler)
        return native_async_client(*args, **kwargs)

    monkeypatch.setattr(base_llm_module.httpx, "AsyncClient", mock_async_client)
    application = FastAPI()
    application.include_router(GatewayRouter(_load_test_catalog()).get_router())
    return application


def _post_async(application : FastAPI, path : str, header_dictionary : dict, body_dictionary : dict):
    async def execute_async():
        async with httpx.AsyncClient(transport = ASGITransport(app = application), base_url = "http://testserver") as client:
            return await client.post(path, headers = header_dictionary, json = body_dictionary)
    return asyncio.run(execute_async())


def test_chat_completion_forwards_with_auth_and_model(monkeypatch):
    captured_request_dictionary = {}

    def gateway_handler(request : httpx.Request) -> httpx.Response:
        captured_request_dictionary["url"]     = str(request.url)
        captured_request_dictionary["headers"] = dict(request.headers)
        captured_request_dictionary["body"]    = json.loads(request.content)
        return httpx.Response(200, json = {"choices" : [{"message" : {"content" : "ok"}}]})

    application = _build_test_application(monkeypatch, gateway_handler)
    response    = _post_async(
        application,
        "/gateway/gpt_oss_120b/v1/chat/completions",
        {"User-Id" : "caller-99"},
        {"messages" : [{"role" : "user", "content" : "hi"}], "stream" : False}
    )

    assert response.status_code == 200
    # URL 조립 : base_url + /v1/chat/completions
    assert captured_request_dictionary["url"] == "http://gateway.test/gpt-oss-120b/v1/chat/completions"
    # 모델명 주입 (요청 바디에는 없었음)
    assert captured_request_dictionary["body"]["model"] == "gpt-oss-120b"
    # 인증/식별 헤더 : 카탈로그 api_key → Bearer, 카탈로그 헤더, 클라이언트 패스스루 헤더
    assert captured_request_dictionary["headers"]["authorization"]     == "Bearer secret-key"
    assert captured_request_dictionary["headers"]["send-system-name"]  == "test-system"
    assert captured_request_dictionary["headers"]["user-id"]           == "caller-99"   # 클라이언트 값이 패스스루된다


def test_stream_true_returns_sse_chunks(monkeypatch):
    def gateway_handler(request : httpx.Request) -> httpx.Response:
        sse_text = 'data: {"choices":[{"delta":{"content":"5"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content = sse_text.encode("utf-8"), headers = {"content-type" : "text/event-stream"})

    application = _build_test_application(monkeypatch, gateway_handler)
    response    = _post_async(
        application,
        "/gateway/gpt_oss_120b/v1/chat/completions",
        {},
        {"messages" : [{"role" : "user", "content" : "2+3"}], "stream" : True}
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"content":"5"' in response.text


def test_non_gateway_model_is_rejected(monkeypatch):
    def gateway_handler(request : httpx.Request) -> httpx.Response:
        return httpx.Response(200, json = {})

    application = _build_test_application(monkeypatch, gateway_handler)
    response    = _post_async(application, "/gateway/gemini_default/v1/chat/completions", {}, {"messages" : []})

    assert response.status_code == 400   # google 모델은 게이트웨이 프록시 대상이 아니다


def test_unknown_model_key_is_not_found(monkeypatch):
    def gateway_handler(request : httpx.Request) -> httpx.Response:
        return httpx.Response(200, json = {})

    application = _build_test_application(monkeypatch, gateway_handler)
    response    = _post_async(application, "/gateway/does_not_exist/v1/chat/completions", {}, {"messages" : []})

    assert response.status_code == 404
