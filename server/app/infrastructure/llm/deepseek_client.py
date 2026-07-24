"""DeepSeek API 统一客户端。

职责：HTTP 调用、超时、重试、错误映射。
不负责 Prompt 构造和结构化输出校验（由 provider 负责）。

使用 httpx 同步客户端调用 DeepSeek chat/completions 接口
（OpenAI 兼容格式）。

错误处理：
- 所有错误统一为 DeepSeekError（code, message）
- provider 捕获 DeepSeekError 后决定是否降级到 LocalRule
"""

import json
import time
import logging

import httpx

from app.infrastructure.llm.llm_cache import LLMCache


logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """DeepSeek 调用结构化错误。

    code 用于 provider 判断降级策略和日志记录。
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class DeepSeekClient:
    """DeepSeek API 统一客户端。

    使用 httpx 同步调用，支持超时和重试。
    不依赖 openai SDK，直接 HTTP 调用减少依赖。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        cache: LLMCache | None = None,
    ):
        if not api_key:
            raise DeepSeekError(
                code="DEEPSEEK_API_KEY_MISSING",
                message="DEEPSEEK_API_KEY 未配置",
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._cache = cache

    def chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        temperature: float = 0.3,
    ) -> str:
        """调用 DeepSeek chat/completions 接口，返回 content 字符串。

        参数：
        - messages: OpenAI 兼容的 messages 格式
          [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        - response_format: 可选，{"type": "json_object"} 要求 JSON 输出
        - temperature: 采样温度，默认 0.3（偏稳定）

        返回：assistant 消息的 content 字符串

        异常：
        - DeepSeekError（code, message）—— 所有错误统一为结构化错误
        """
        # 缓存查询（SPEC 0014）：cache=None 时跳过，行为与现有完全一致
        cache_key = None
        if self._cache is not None:
            cache_key = LLMCache.compute_key(
                self._model, messages, response_format, temperature
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.info(f"LLM 缓存命中, key={cache_key[:12]}...")
                return cached

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        last_error: DeepSeekError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    resp = client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as e:
                last_error = DeepSeekError(
                    code="DEEPSEEK_TIMEOUT",
                    message=f"请求超时（{self._timeout_seconds}s）：{e}",
                )
                logger.warning(f"DeepSeek 超时，attempt={attempt + 1}")
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error
            except httpx.ConnectError as e:
                last_error = DeepSeekError(
                    code="DEEPSEEK_CONNECTION_ERROR",
                    message=f"连接失败：{e}",
                )
                logger.warning(f"DeepSeek 连接失败，attempt={attempt + 1}")
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error
            except httpx.HTTPError as e:
                last_error = DeepSeekError(
                    code="DEEPSEEK_HTTP_ERROR",
                    message=f"HTTP 错误：{e}",
                )
                logger.warning(f"DeepSeek HTTP 错误，attempt={attempt + 1}")
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error

            # HTTP 状态码处理
            if resp.status_code == 200:
                content = self._extract_content(resp)
                # 缓存写入（SPEC 0014）：失败不阻断主流程
                if cache_key is not None and self._cache is not None:
                    try:
                        self._cache.set(cache_key, content, model=self._model)
                    except Exception as e:
                        logger.warning(f"LLM 缓存写入失败，降级到无缓存: {e}")
                return content

            # 不可恢复的错误（不重试）
            if resp.status_code == 401:
                raise DeepSeekError(
                    code="DEEPSEEK_AUTH_ERROR",
                    message="API Key 鉴权失败",
                )
            if resp.status_code == 429:
                raise DeepSeekError(
                    code="DEEPSEEK_RATE_LIMITED",
                    message="请求被限流",
                )
            if 400 <= resp.status_code < 500:
                raise DeepSeekError(
                    code="DEEPSEEK_CLIENT_ERROR",
                    message=f"客户端错误（{resp.status_code}）：{resp.text[:200]}",
                )

            # 5xx 服务端错误（可重试）
            last_error = DeepSeekError(
                code="DEEPSEEK_SERVER_ERROR",
                message=f"服务端错误（{resp.status_code}）：{resp.text[:200]}",
            )
            logger.warning(
                f"DeepSeek 5xx，attempt={attempt + 1}, status={resp.status_code}"
            )
            if attempt < self._max_retries:
                time.sleep(2 ** attempt)
                continue
            raise last_error

        # 理论上不会到达（循环内要么 return 要么 raise）
        raise last_error or DeepSeekError(
            code="DEEPSEEK_UNKNOWN_ERROR",
            message="未知错误",
        )

    def _extract_content(self, resp: httpx.Response) -> str:
        """从 200 响应中提取 content 字符串。"""
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"响应 JSON 解析失败：{e}",
            ) from e

        try:
            choices = data["choices"]
            if not choices:
                raise DeepSeekError(
                    code="DEEPSEEK_EMPTY_CHOICES",
                    message="响应 choices 为空",
                )
            content = choices[0]["message"]["content"]
            if not content:
                raise DeepSeekError(
                    code="DEEPSEEK_EMPTY_CONTENT",
                    message="响应 content 为空",
                )
            return content
        except (KeyError, IndexError, TypeError) as e:
            raise DeepSeekError(
                code="DEEPSEEK_RESPONSE_FORMAT_ERROR",
                message=f"响应格式异常：{e}",
            ) from e


def create_client_from_settings() -> DeepSeekClient:
    """从 settings 创建 DeepSeekClient 实例。

    供 Gateway 工厂函数使用。如果 API Key 未配置，抛出 DeepSeekError。
    根据 LLM_CACHE_ENABLED 决定是否注入缓存（SPEC 0014）。
    """
    from app.core.config import settings

    cache = None
    # TTL<=0 视为禁用（SPEC 0014 §5.2）
    if settings.llm_cache_enabled and settings.llm_cache_ttl_seconds > 0:
        cache = LLMCache(
            db_path=settings.llm_cache_db_path,
            ttl_seconds=settings.llm_cache_ttl_seconds,
        )

    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_retries=settings.deepseek_max_retries,
        cache=cache,
    )
