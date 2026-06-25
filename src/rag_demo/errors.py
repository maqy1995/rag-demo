"""Errors: 业务异常 + 状态码/决策码字典 (design §5 / §6.3).

单一信源: 所有 code 的 http_status / stage / message / is_decision 在这里维护.
调用方 (web / __main__) 在 L3→L2 边界统一捕获 AppError 并转 JSON.

决策码 (is_decision=True) 不是异常, 调用方自己处理:
  - RETRIEVE_EMPTY: hits 为空
  - NOT_DEFINED: hits 非空但 is_defined_in_hits == False

它们仍出现在 ERROR_CODES 里, 便于前端按 code 路由提示文案;
但 raise_error() 不会为决策码 raise (只是占位).
"""

from __future__ import annotations

from typing import NoReturn


class AppError(Exception):
    """v1 design §6.3 — 业务异常统一形态."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        stage: str | None = None,
        http_status: int | None = None,
    ) -> None:
        spec = ERROR_CODES.get(code, {})
        self.code = code
        self.message = message if message is not None else spec.get("message", code)
        self.stage = stage if stage is not None else spec.get("stage", "infra")
        self.http_status = http_status if http_status is not None else spec.get("http_status", 500)
        self.is_decision = spec.get("is_decision", False)
        super().__init__(self.message)


# design §5 状态码/决策码字典 (单一信源)
ERROR_CODES: dict[str, dict] = {
    "INGEST_INVALID_CONFIG":     {"http_status": 400, "stage": "ingest", "message": "ingest 配置非法"},
    "INGEST_BUILD_FAIL":         {"http_status": 503, "stage": "ingest", "message": "ingest 构建失败"},
    "RETRIEVE_EMPTY":            {"http_status": 200, "stage": "retrieve", "message": "未在笔记中找到相关内容", "is_decision": True},
    "RETRIEVE_INDEX_MISSING":    {"http_status": 503, "stage": "retrieve", "message": "索引不存在或为空"},
    "NOT_DEFINED":               {"http_status": 200, "stage": "generate", "message": "你的笔记里没找到 {query} 的明确定义", "is_decision": True},
    "GENERATE_LLM_FAIL":         {"http_status": 503, "stage": "generate", "message": "LLM 调用失败"},
    "GENERATE_INVALID_QUESTION": {"http_status": 400, "stage": "generate", "message": "问题参数非法"},
    # ADR-0001 §"修改模块": embedding 错误独立成码 (LLM 复用 GENERATE_LLM_FAIL).
    # stage=ingest 因为 embedding 是 ingest 阶段调用; 真实 HTTP status 由 openai_compat
    # 按 e.status_code 透传, 这里只是兜底默认值 (503).
    "EMBEDDING_FAIL":            {"http_status": 503, "stage": "ingest", "message": "embedding 调用失败"},
    "CONFIG_LOAD_FAIL":          {"http_status": 500, "stage": "infra", "message": "config 加载失败"},
    "USAGE_LOG_FAIL":            {"http_status": 500, "stage": "infra", "message": "埋点写入失败"},
}


def raise_error(code: str, **kwargs: str) -> NoReturn:
    """按 code 构造 AppError 并 raise. message 里的 {key} 占位符用 kwargs 替换.

    Example:
        raise_error("NOT_DEFINED", query="微服务治理")
        raise_error("INGEST_INVALID_CONFIG")
    """
    spec = ERROR_CODES.get(code)
    if spec is None:
        raise AppError(code=code, message=code, stage="infra", http_status=500)
    raw_message = spec["message"]
    try:
        msg = raw_message.format(**kwargs) if kwargs else raw_message
    except KeyError:
        msg = raw_message
    raise AppError(code=code, message=msg)
