##################################################
# 코드 인덱스 대조기
# 소스 파일과 .claude/index/ 의 인덱스 문서가 1:1로 맞는지 검사한다.
#   - 누락 : 소스는 있는데 인덱스 문서가 없다
#   - 고아 : 인덱스 문서는 있는데 소스가 사라졌다 (이름 변경·삭제 후 정리 누락)
#   - 낡음 : 소스가 인덱스보다 나중에 수정됐다 (내용이 밀렸을 가능성)
#
# 규칙을 기억에 맡기지 않고 기계로 잡기 위한 도구다.
# 컨텍스트에 올라가지 않고 실행만 되므로 토큰을 쓰지 않는다.
#
#   실행 : python .claude/skills/doc-sync/scripts/check_index.py
#   종료 코드 : 0 = 이상 없음, 1 = 누락 또는 고아 있음
##################################################

import os
import sys

from typing import List
from typing import Tuple

class IndexChecker:
    # 인덱스가 반드시 있어야 하는 대상 : (소스 루트, 확장자)
    SOURCE_ROOT_LIST      = [("backend", (".py",)), ("frontend/src", (".jsx", ".js"))]
    EXCLUDED_SEGMENT_SET  = {"__pycache__", "node_modules", ".venv", "dist", "build"}
    INDEX_RELATIVE_PATH   = os.path.join(".claude", "index")
    # 고아 판정용 : 인덱스 문서에 대응할 수 있는 소스 확장자.
    # 위 SOURCE_ROOT_LIST 밖에도 인덱스를 둔 파일이 있다 (config/models.yaml, tests/*.py, frontend/index.html 등).
    # 이들을 고아로 잘못 잡지 않으려면 확장자를 넓게 확인해야 한다.
    CANDIDATE_EXTENSION_LIST = ["", ".py", ".jsx", ".js", ".ts", ".tsx", ".html", ".yaml", ".yml", ".json", ".css"]

    def __init__(self, project_root_path : str) -> None:
        self.project_root_path = os.path.abspath(project_root_path)
        self.index_root_path   = os.path.join(self.project_root_path, IndexChecker.INDEX_RELATIVE_PATH)

    @staticmethod
    def _is_excluded(directory_path : str) -> bool:
        return any(segment in IndexChecker.EXCLUDED_SEGMENT_SET
                   for segment in directory_path.replace("\\", "/").split("/"))

    def _collect_source_relative_path_list(self) -> List[str]:
        # 소스 루트를 훑어 인덱스 대상 파일의 프로젝트 상대 경로를 모은다
        source_relative_path_list = []
        for source_root, extension_tuple in IndexChecker.SOURCE_ROOT_LIST:
            root_path = os.path.join(self.project_root_path, *source_root.split("/"))
            if not os.path.isdir(root_path):
                continue
            for directory_path, _, file_name_list in os.walk(root_path):
                if IndexChecker._is_excluded(directory_path):
                    continue
                for file_name in file_name_list:
                    if file_name.endswith(extension_tuple):
                        absolute_path = os.path.join(directory_path, file_name)
                        source_relative_path_list.append(os.path.relpath(absolute_path, self.project_root_path))
        return sorted(source_relative_path_list)

    def _collect_index_relative_path_list(self) -> List[str]:
        index_relative_path_list = []
        for directory_path, _, file_name_list in os.walk(self.index_root_path):
            for file_name in file_name_list:
                if file_name.endswith(".md"):
                    absolute_path = os.path.join(directory_path, file_name)
                    index_relative_path_list.append(os.path.relpath(absolute_path, self.index_root_path))
        return sorted(index_relative_path_list)

    def get_index_relative_path(self, source_relative_path : str) -> str:
        # 소스 경로 → 인덱스 경로. 확장자만 .md 로 바꾸고 트리 구조는 그대로 둔다
        return os.path.splitext(source_relative_path)[0] + ".md"

    def check(self) -> Tuple[List[str], List[str], List[str]]:
        source_relative_path_list = self._collect_source_relative_path_list()
        index_relative_path_set   = set(self._collect_index_relative_path_list())

        missing_list = []
        stale_list   = []
        expected_set = set()
        for source_relative_path in source_relative_path_list:
            index_relative_path = self.get_index_relative_path(source_relative_path)
            expected_set.add(index_relative_path)
            index_absolute_path = os.path.join(self.index_root_path, index_relative_path)
            if index_relative_path not in index_relative_path_set:
                missing_list.append(source_relative_path)
                continue
            source_absolute_path = os.path.join(self.project_root_path, source_relative_path)
            if os.path.getmtime(source_absolute_path) > os.path.getmtime(index_absolute_path):
                stale_list.append(source_relative_path)

        # 고아 판정 : 대응하는 소스가 어떤 확장자로도 존재하지 않을 때만 고아다.
        # 인덱스 루트 바로 아래의 안내 문서(README 등)는 소스 대응이 없어도 고아가 아니다.
        orphan_list = sorted(index_relative_path for index_relative_path in index_relative_path_set
                             if index_relative_path not in expected_set
                             and os.sep in index_relative_path
                             and not self._has_matching_source(index_relative_path))
        return missing_list, orphan_list, stale_list

    def _has_matching_source(self, index_relative_path : str) -> bool:
        # 인덱스 경로에서 .md 를 떼고 알려진 확장자를 붙여 실제 소스가 있는지 본다.
        # 확장자가 이미 이름에 들어간 경우(models.yaml.md)를 위해 빈 문자열도 후보에 둔다.
        base_relative_path = os.path.splitext(index_relative_path)[0]
        for extension_text in IndexChecker.CANDIDATE_EXTENSION_LIST:
            candidate_path = os.path.join(self.project_root_path, base_relative_path + extension_text)
            if os.path.isfile(candidate_path):
                return True
        return False

def _print_section(title_text : str, path_list : List[str], maximum_print_count : int = 40) -> None:
    print(f"\n{title_text} : {len(path_list)}개")
    for path_text in path_list[:maximum_print_count]:
        print("   -", path_text.replace("\\", "/"))
    if len(path_list) > maximum_print_count:
        print(f"   ... 외 {len(path_list) - maximum_print_count}개")

if __name__ == "__main__":
    # 스크립트 위치(.claude/skills/doc-sync/scripts/)에서 프로젝트 루트로 네 단계 올라간다
    default_project_root_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    project_root_path = sys.argv[1] if len(sys.argv) > 1 else default_project_root_path

    index_checker = IndexChecker(project_root_path)
    missing_list, orphan_list, stale_list = index_checker.check()

    print(f"프로젝트 : {index_checker.project_root_path}")
    print(f"인덱스   : {index_checker.index_root_path}")

    if missing_list:
        _print_section("누락 (소스는 있는데 인덱스 문서가 없다)", missing_list)
    if orphan_list:
        _print_section("고아 (인덱스 문서는 있는데 소스가 없다)", orphan_list)
    if stale_list:
        _print_section("낡음 (소스가 인덱스보다 나중에 수정됨 — 내용 확인 필요)", stale_list)

    if not missing_list and not orphan_list:
        print("\n누락·고아 없음" + (f" (낡음 {len(stale_list)}개는 내용만 확인)" if stale_list else ""))
        sys.exit(0)
    print(f"\n누락 {len(missing_list)}개, 고아 {len(orphan_list)}개 — doc-sync 스킬로 갱신이 필요하다")
    sys.exit(1)
