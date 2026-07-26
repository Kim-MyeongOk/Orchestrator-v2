##################################################
# 이미지 재주입 미들웨어 (모델 전방 Re-injection)
# LangGraph 가 LLM 을 호출하기 직전, State 의 image_reference 블록을 실제 Base64 로
# 복원해 모델 요청에만 일시적으로 주입한다.
#
# [중요] before_model 훅이 아니라 awrap_model_call 을 쓰는 이유 :
# before_model 이 반환하는 상태 업데이트는 체크포인트에 다시 기록되므로, 복원한 MB급
# 이미지가 그대로 영속화되어 격리(Detachment)가 무의미해진다. awrap_model_call 은
# 모델 요청(ModelRequest)만 override 하고 State 는 건드리지 않아 체크포인트에는
# 참조 블록만 남는다.
#
# 이미지가 없는 대화에서는 참조 블록 검색이 즉시 통과되어 오버헤드가 없다 (Pass-through).
##################################################

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest

from app.llm.agent.image_attachment_interceptor import ImageAttachmentInterceptor


class ImageReinjectionMiddleware(AgentMiddleware):
    def __init__(self, image_attachment_interceptor : ImageAttachmentInterceptor) -> None:
        super().__init__()
        self.image_attachment_interceptor = image_attachment_interceptor

    async def awrap_model_call(self, request : ModelRequest, handler):
        reinjected_message_list = await self.image_attachment_interceptor.reinject_image_into_message_list_async(request.messages)
        return await handler(request.override(messages = reinjected_message_list))
