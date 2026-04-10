"""统一通知分发：根据配置同时推送到已启用的渠道"""

import logging

from config.settings import settings
from src.notify.wechat import send_wechat
from src.notify.pushplus import send_pushplus

logger = logging.getLogger(__name__)


def send_notify(content: str) -> bool:
    """向所有已配置的渠道发送通知

    Returns:
        True if at least one channel sent successfully
    """
    results = []

    if settings.wechat_webhook_url:
        results.append(send_wechat(content))

    if settings.pushplus_token:
        results.append(send_pushplus(content))

    if not results:
        logger.warning("未配置任何通知渠道，打印到终端")
        print("── 通知（未配置推送渠道）──")
        print(content)
        print("── 结束 ──")
        return False

    return any(results)
