"""
LLM API 客户端模块
使用 OpenAI SDK 调用兼容 OpenAI 格式的 API（如 Kimi、Moonshot 等）
支持环境变量：KIMI_API_KEY 或 OPENAI_API_KEY
"""
import logging
import time
from openai import OpenAI
from src.utils.config import (
    OPENAI_API_KEY,
    KIMI_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MAX_RETRIES,
    RETRY_DELAY,
    LLM_REQUEST_TIMEOUT,
    VOCABULARY_PROMPT_TEMPLATE,
    PROJECT_ROOT,
)
from src.utils.logger import setup_logger

logger = setup_logger("llm", log_file=None)


class LLMClient:
    """
    LLM API 客户端
    使用 OpenAI SDK 调用兼容 OpenAI 格式的 API（如 Kimi、Moonshot 等）
    """

    def __init__(self):
        """
        初始化 LLM 客户端

        Raises:
            ValueError: 如果 API Key 未配置
        """
        api_key = KIMI_API_KEY or OPENAI_API_KEY
        if not api_key:
            env_file = PROJECT_ROOT / ".env"
            raise ValueError(
                f"API Key 未配置！\n"
                f"请在项目根目录的 .env 文件中设置：{env_file}\n"
                f"格式：KIMI_API_KEY=sk-kimi-xxxxx 或 OPENAI_API_KEY=sk-kimi-xxxxx"
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=LLM_BASE_URL if LLM_BASE_URL else None,
        )
        self.model = LLM_MODEL or "kimi-k2.5"

        if not LLM_MODEL:
            logger.warning("⚠ LLM_MODEL 未配置，使用默认: kimi-k2.5")

        logger.info("LLM 客户端就绪 | 模型: %s", self.model)

    def _load_prompt_template(self) -> str:
        """
        加载 prompt 模板文件

        Returns:
            prompt 模板内容

        Raises:
            FileNotFoundError: 模板文件不存在时抛出异常
        """
        if not VOCABULARY_PROMPT_TEMPLATE.exists():
            raise FileNotFoundError(
                f"Prompt 模板文件不存在: {VOCABULARY_PROMPT_TEMPLATE}\n"
                f"请确保模板文件存在于 template/ 目录下"
            )

        with open(VOCABULARY_PROMPT_TEMPLATE, "r", encoding="utf-8") as f:
            return f.read()

    def extract_vocabulary(self, text: str, file_name: str = "") -> str:
        """
        提取文本中的核心词汇和词组
        使用 OpenAI 兼容 API 进行文本处理

        Args:
            text: 输入文本
            file_name: 文件名（用作文档标题）

        Returns:
            Markdown 格式的词汇提取结果

        Raises:
            Exception: API 调用失败时抛出异常
        """
        prompt_template = self._load_prompt_template()
        prompt = prompt_template.replace("{text}", text).replace("{file_name}", file_name)

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(
                    "调用 LLM | 尝试 %d/%d | 超时 %ds | 流式接收（首 token 可能需 1–2 分钟）",
                    attempt + 1,
                    MAX_RETRIES,
                    LLM_REQUEST_TIMEOUT,
                )

                t0 = time.perf_counter()
                stream = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一位英语教学专家。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=1,
                    stream=True,
                    timeout=LLM_REQUEST_TIMEOUT,
                    stream_options={"include_usage": True},
                )

                response_text = ""
                next_threshold = 2  # 按 2 的指数递增：2、4、8、16...
                first_chunk = True
                usage = None
                for chunk in stream:
                    if chunk.usage:
                        usage = chunk.usage
                    if chunk.choices and chunk.choices[0].delta.content:
                        if first_chunk:
                            logger.info("  开始接收响应...")
                            first_chunk = False
                        response_text += chunk.choices[0].delta.content
                        while len(response_text) >= next_threshold:
                            logger.info("  已接收 %d 字符...", len(response_text))
                            next_threshold *= 2

                elapsed = time.perf_counter() - t0
                if response_text and len(response_text) > next_threshold // 2:
                    logger.info("  已接收 %d 字符", len(response_text))
                if usage:
                    logger.info(
                        "✓ LLM 调用成功 | Token: 输入 %d / 输出 %d / 合计 %d | 耗时 %.1fs",
                        usage.prompt_tokens,
                        usage.completion_tokens,
                        usage.total_tokens,
                        elapsed,
                    )
                else:
                    logger.info("✓ LLM 调用成功 | 耗时 %.1fs（未返回 usage）", elapsed)
                return response_text

            except Exception as e:
                status_code = getattr(e, "status_code", None)
                if status_code == 401:
                    logger.error("✗ API Key 认证失败，请检查 .env")
                    raise
                error_msg = str(e)
                logger.warning("⚠ 调用失败 [%d/%d]: %s", attempt + 1, MAX_RETRIES, error_msg)
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    logger.info("等待 %d 秒后重试...", wait_time)
                    time.sleep(wait_time)
                else:
                    logger.error("✗ 已达最大重试次数 (%d)", MAX_RETRIES)
                    raise


if __name__ == "__main__":
    # 测试入口：验证 LLM 客户端是否可以正常初始化
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        client = LLMClient()
        logger.info("✓ 初始化成功 | 模型: %s | 端点: %s", client.model, LLM_BASE_URL)
    except Exception as e:
        logger.error("✗ 初始化失败: %s", e)
        sys.exit(1)
