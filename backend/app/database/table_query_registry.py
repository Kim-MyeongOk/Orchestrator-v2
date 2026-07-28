##################################################
# 테이블 쿼리 레지스트리
#
# app/database/table_query/ 폴더의 *_query.py 를 자동으로 훑어 테이블 정의를 모은다.
# **새 테이블을 추가할 때 이 파일을 고칠 필요가 없다** — 폴더에 파일 하나만 만들면 된다.
#
# [새 테이블 추가 방법]
#   1. app/database/table_query/{테이블명}_query.py 를 만든다
#   2. 클래스 하나에 아래를 둔다
#        TABLE_NAME     : str   테이블 이름
#        CREATE_TABLE   : str   DDL (CREATE TABLE / CREATE INDEX / ALTER TABLE 을 함께 넣어도 된다)
#        CREATION_ORDER : int   작은 값이 먼저 생성된다 (외래키 참조 순서)
#        IS_ASYNCPG     : bool  asyncpg 풀을 쓰면 True (기본 False = psycopg)
#      쿼리 상수도 같은 클래스에 모은다 (SELECT_… / INSERT_… / UPDATE_… / DELETE_…)
#   3. 끝. 레지스트리가 자동으로 찾아 스키마 초기화에 포함시킨다.
#
# 자동 탐색을 쓰는 이유 : 목록을 손으로 관리하면 파일을 만들고 등록을 잊는 실수가 반드시 생긴다.
# (이 프로젝트는 __init__.py 를 두지 않는 네임스페이스 패키지라 pkgutil 로 경로를 직접 훑는다)
##################################################

import importlib
import inspect
import os
import pkgutil

from typing import Any
from typing import List


class TableQueryRegistry:
    PACKAGE_NAME       = "app.database.table_query"
    MODULE_NAME_SUFFIX = "_query"
    DEFAULT_ORDER      = 100   # CREATION_ORDER 를 적지 않은 테이블은 뒤로 보낸다

    @staticmethod
    def _get_package_directory_path() -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "table_query")

    @staticmethod
    def _find_table_query_class(module : Any) -> Any:
        # 모듈 안에서 TABLE_NAME 과 CREATE_TABLE 을 모두 가진 클래스를 찾는다.
        # 임포트된 다른 클래스가 딸려 들어오지 않도록 정의 모듈이 자기 자신인 것만 인정한다.
        for _class_name, class_object in inspect.getmembers(module, inspect.isclass):
            if class_object.__module__ != module.__name__:
                continue
            if hasattr(class_object, "TABLE_NAME") and hasattr(class_object, "CREATE_TABLE"):
                return class_object
        return None

    @staticmethod
    def load_table_query_class_list() -> List[Any]:
        # 생성 순서(CREATION_ORDER)대로 정렬해 돌려준다 — 외래키가 걸린 테이블이 먼저 만들어지면 실패한다
        table_query_class_list = []
        for module_information in pkgutil.iter_modules([TableQueryRegistry._get_package_directory_path()]):
            if not module_information.name.endswith(TableQueryRegistry.MODULE_NAME_SUFFIX):
                continue
            module           = importlib.import_module(f"{TableQueryRegistry.PACKAGE_NAME}.{module_information.name}")
            table_query_class = TableQueryRegistry._find_table_query_class(module)
            if table_query_class is None:
                print(f"TABLE QUERY SKIPPED : {module_information.name} - NO CLASS WITH TABLE_NAME/CREATE_TABLE", flush = True)
                continue
            table_query_class_list.append(table_query_class)

        table_query_class_list.sort(
            key = lambda table_query_class : getattr(table_query_class, "CREATION_ORDER", TableQueryRegistry.DEFAULT_ORDER))
        return table_query_class_list

    @staticmethod
    def load_psycopg_table_query_class_list() -> List[Any]:
        # psycopg 풀(체크포인트 DB)에서 만들 테이블
        return [table_query_class for table_query_class in TableQueryRegistry.load_table_query_class_list()
                if not getattr(table_query_class, "IS_ASYNCPG", False)]

    @staticmethod
    def load_asyncpg_table_query_class_list() -> List[Any]:
        # asyncpg 풀(job 스키마 DB)에서 만들 테이블
        return [table_query_class for table_query_class in TableQueryRegistry.load_table_query_class_list()
                if getattr(table_query_class, "IS_ASYNCPG", False)]
