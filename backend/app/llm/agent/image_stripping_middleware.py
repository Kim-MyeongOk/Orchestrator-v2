##################################################
# 이미지 제거 미들웨어
#
# 비전 미지원 모델에 이미지 블록이 섞인 메시지를 보내면 400 으로 턴이 통째로 실패한다.
#   [ResponseError 400] this model does not support image input
#
# 한 번이라도 이미지를 붙인 스레드는 그 블록이 체크포인트에 남아 매 턴 다시 실려 나가므로,
# 모델을 비전 미지원으로 바꾸는 순간부터 그 방은 영영 대화가 안 된다.
#
# 원칙은 ThinkTrimmingMiddleware 와 같다 — 체크포인트(원본)는 건드리지 않고
# "모델에게 보내는 프롬프트"에서만 이미지를 걷어낸다. 그래야 비전 모델로 되돌렸을 때
# 이미지가 그대로 살아 있고, 화면의 지난 대화도 깨지지 않는다.
##################################################

from langchain.agents.middleware.types import AgentMiddleware

from app.llm.image.image_content_helper import ImageContentHelper


class ImageStrippingMiddleware(AgentMiddleware):
    # image_maximum_count = None : 전부 제거 (비전 미지원 모델)
    #                       N    : 최신 N장만 남긴다 (llama3.2-vision 처럼 장수 제한이 있는 모델)
    def __init__(self, image_maximum_count : int = None) -> None:
        super().__init__()
        self.image_maximum_count = image_maximum_count

    async def awrap_model_call(self, request, handler):
        if self.image_maximum_count is None:
            stripped_message_list = ImageContentHelper.strip_image_block_list(request.messages)
        else:
            stripped_message_list = ImageContentHelper.limit_image_block_list(request.messages, self.image_maximum_count)
        return await handler(request.override(messages = stripped_message_list))
