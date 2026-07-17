import threading
import uuid
import time
import os

class UUIDV7Generator:
    def __init__(self) -> None:
        self.lock                             = threading.Lock()
        self.last_timestamp_millisecond_count = 0
        self.counter                          = 0

    def generate(self) -> uuid.UUID:
        with self.lock:
            timestamp_millisecond_count = int(time.time() * 1000)
            # 동일(또는 역행) 밀리초에서는 12비트 카운터로 단조 증가를 보장한다.
            if timestamp_millisecond_count <= self.last_timestamp_millisecond_count:
                timestamp_millisecond_count = self.last_timestamp_millisecond_count
                self.counter                = self.counter + 1
                # 카운터 오버플로우 시 다음 밀리초로 이월한다.
                if self.counter > 0x0FFF:
                    timestamp_millisecond_count = timestamp_millisecond_count + 1
                    self.counter                = 0
            else:
                # 새 밀리초에서는 하위 11비트를 랜덤 시드로 초기화한다 (최상위 비트 여유 확보)
                self.counter = int.from_bytes(os.urandom(2), "big") & 0x07FF
            self.last_timestamp_millisecond_count = timestamp_millisecond_count
            random_bit_value                      = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
            uuid_integer                          = (timestamp_millisecond_count & 0xFFFFFFFFFFFF) << 80
            uuid_integer                         |= 0x7 << 76                     # UUID 버전 7
            uuid_integer                         |= (self.counter & 0x0FFF) << 64 # 상위 랜덤 영역에 모노토닉 카운터 배치
            uuid_integer                         |= 0x2 << 62                     # RFC 4122 변형 비트
            uuid_integer                         |= random_bit_value              # 하위 랜덤 영역
            return uuid.UUID(int = uuid_integer)
