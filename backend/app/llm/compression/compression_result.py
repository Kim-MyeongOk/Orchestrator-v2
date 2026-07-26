from typing import Any
from typing import Dict
from typing import Optional


##################################################
# 압축 결과
# API 응답의 compressed_info 로 그대로 직렬화된다.
##################################################
class CompressionResult:
    def __init__(self, is_compressed : bool, saved_token_count : int = 0, summary : Optional[str] = None) -> None:
        self.is_compressed     = is_compressed
        self.saved_token_count = saved_token_count
        self.summary           = summary

    @staticmethod
    def create_uncompressed() -> "CompressionResult":
        return CompressionResult(is_compressed = False)

    def to_response_dictionary(self) -> Dict[str, Any]:
        return {
            "is_compressed" : self.is_compressed,
            "saved_tokens"  : self.saved_token_count,
            "summary"       : self.summary
        }

    def __repr__(self) -> str:
        return f"CompressionResult(is_compressed={self.is_compressed}, saved_token_count={self.saved_token_count})"
