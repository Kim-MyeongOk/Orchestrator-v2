##################################################
# [병목 해결 가이드] 생각 토큰 트리밍 + 윈도잉 미들웨어
#
# 원칙 : 체크포인트(원본 상태)는 건드리지 않고, "모델에게 보내는 프롬프트"만
# 슬림하게 만든다. before_model 훅은 반환값이 체크포인트에 다시 기록되므로 쓰지 않는다 —
# awrap_model_call 은 모델 요청(ModelRequest)만 override 하고 State 는 그대로 둔다.
##################################################

from langchain.agents.middleware.types import AgentMiddleware

from app.llm.agent.think_token_helper import ThinkTokenHelper


class ThinkTrimmingMiddleware(AgentMiddleware):
    # 모델 호출 직전에만 트리밍+윈도잉을 적용한다 (체크포인트 원본 보존)
    def __init__(self, window_message_count : int = 20) -> None:
        super().__init__()
        self.window_message_count = window_message_count

    async def awrap_model_call(self, request, handler):
        slim_message_list = ThinkTokenHelper.prepare_model_input(request.messages, self.window_message_count)
        return await handler(request.override(messages = slim_message_list))
