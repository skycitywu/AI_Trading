"""企业微信 Webhook 通知"""

import logging

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


def send_wechat(content: str) -> bool:
    """通过企业微信 Webhook 发送文本消息

    Returns:
        True if sent successfully
    """
    url = settings.wechat_webhook_url
    if not url:
        logger.debug("未配置 WECHAT_WEBHOOK_URL，跳过企业微信通知")
        return False

    # 企业微信文本消息限制 2048 字符
    if len(content) > 2000:
        content = content[:2000] + "\n...(内容已截断)"

    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            logger.info("微信通知发送成功")
            return True
        else:
            logger.error(f"微信通知发送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"微信通知异常: {e}")
        return False
