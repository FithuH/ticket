"""
验证码识别适配器：支持超级鹰打码平台及手动输入降级
"""

import base64
import requests
from abc import ABC, abstractmethod
from io import BytesIO
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class BaseCaptchaSolver(ABC):
    @abstractmethod
    def solve(self, image_bytes: bytes) -> str:
        """返回识别出的坐标字符串，如 '35,60|110,45'"""
        pass


class ChaojiyingSolver(BaseCaptchaSolver):
    """超级鹰打码平台实现"""
    def __init__(self, user: str, password: str, soft_id: str):
        self.user = user
        self.password = password
        self.soft_id = soft_id
        self.api_url = "https://upload.chaojiying.net/Upload/Processing.php"

    def solve(self, image_bytes: bytes) -> str:
        # 超级鹰需要上传图片文件
        files = {
            'userfile': ('captcha.jpg', image_bytes, 'image/jpeg')
        }
        data = {
            'user': self.user,
            'pass': self.password,
            'softid': self.soft_id,
            'codetype': '9004',      # 12306 验证码类型（坐标多选）
        }
        try:
            resp = requests.post(self.api_url, data=data, files=files, timeout=30)
            resp_json = resp.json()
            if resp_json.get('err_no') == 0:
                result = resp_json.get('pic_str', '')
                logger.info(f"超级鹰识别结果: {result}")
                return result
            else:
                logger.error(f"超级鹰识别失败: {resp_json.get('err_str')}")
                return ""
        except Exception as e:
            logger.error(f"超级鹰请求异常: {e}")
            return ""


class ManualSolver(BaseCaptchaSolver):
    """手动输入验证码（降级方案）"""
    def solve(self, image_bytes: bytes) -> str:
        try:
            img = Image.open(BytesIO(image_bytes))
            img.show()
        except Exception as e:
            logger.warning(f"无法显示图片: {e}")
        answer = input("请输入验证码答案（坐标格式，如 '35,60|110,45'）：").strip()
        return answer


def get_solver(config: dict) -> BaseCaptchaSolver:
    platform = config.get("platform", "manual")
    if platform == "chaojiying":
        cjy_conf = config.get("chaojiying", {})
        return ChaojiyingSolver(
            user=cjy_conf.get("user", ""),
            password=cjy_conf.get("password", ""),
            soft_id=cjy_conf.get("soft_id", "")
        )
    else:
        return ManualSolver()