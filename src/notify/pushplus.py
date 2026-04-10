"""PushPlus 微信公众号推送通知"""

import logging

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


def send_pushplus(content: str, title: str = "AI Trading 信号") -> bool:
    """通过 PushPlus 发送微信公众号推送

    Returns:
        True if sent successfully, False if failed or not configured
    """
    token = settings.pushplus_token
    if not token:
        logger.debug("未配置 PUSHPLUS_TOKEN，跳过 PushPlus 通知")
        return False

    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": "txt",
    }

    topic = settings.pushplus_topic
    if topic:
        payload["topic"] = topic

    try:
        resp = requests.post(
            "https://www.pushplus.plus/send",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 200:
            logger.info("PushPlus 通知发送成功")
            return True
        else:
            logger.error(f"PushPlus 通知发送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"PushPlus 通知异常: {e}")
        return False
