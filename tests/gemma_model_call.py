from google import genai

MODEL_NAME = "gemini-3.5-flash"
API_KEY    = "AQ.Ab8RN6J8ySGXi7XiPStAkt1EGBF43jIrvA3mhnYWtht8Ve5oVQ"

client = genai.Client(api_key = API_KEY)

interaction = client.interactions.create(
    model             = "gemini-3.5-flash",
    input             = "서울 날씨.",
    generation_config = {"thinking_level" : "low"}
)
print(interaction.output_text)
# client          = genai.Client(api_key = API_KEY)
# response_stream = client.interactions.create(
#     model  = MODEL_NAME,
#     input  = "서울 날씨",
#     stream = True
# )
#
#
# # chunk 단위로 받아와 이벤트 타입을 확인 후 출력합니다.
# for chunk in response_stream:
#     # 텍스트 데이터 조각이 포함된 이벤트인지 확인
#     if chunk.event_type == "interaction.chunk":
#         # 안전하게 데이터 구조를 따라가서 출력합니다.
#         if hasattr(chunk, 'interaction') and chunk.interaction and hasattr(chunk.interaction, 'output_text'):
#             print(chunk.interaction.output_text, end = "")
#
# del client