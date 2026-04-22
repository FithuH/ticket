"""
登录认证模块：支持扫码登录（推荐）及传统密码登录
"""

import time
import json
import base64
import logging
import random
import requests
from typing import Tuple, Optional
from config import BASE_URLS, Endpoints, HEADERS, CAPTCHA_CONFIG, LOGIN_METHOD
from captcha_solver import get_solver
from utils import rsa_encrypt_password, save_cookies, load_cookies

logger = logging.getLogger(__name__)


class LoginHandler:
    def __init__(self, cookie_file: str = "./cookies.pkl", login_method: str = LOGIN_METHOD):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.cookie_file = cookie_file
        self.login_method = login_method
        self.solver = get_solver(CAPTCHA_CONFIG)

        self._init_session()
        cookies_loaded = load_cookies(self.session, self.cookie_file)
        if cookies_loaded:
            logger.info("已加载持久化 Cookies")
        else:
            logger.info("未找到有效 Cookies，需要登录")

    def _init_session(self):
        try:
            # 设置浏览器设备ID Cookie（模拟真实浏览器）
            self._set_rail_deviceid()
            self.session.get(BASE_URLS["kyfw"] + "/otn/resources/login.html", timeout=10)
            logger.debug("已初始化会话 Cookie")
        except Exception as e:
            logger.warning(f"初始化会话失败: {e}")

    def _set_rail_deviceid(self):
        """设置 RAIL_DEVICEID 和 RAIL_EXPIRATION Cookie"""
        if "RAIL_DEVICEID" not in self.session.cookies:
            device_id = self._generate_device_id()
            self.session.cookies.set("RAIL_DEVICEID", device_id, domain="kyfw.12306.cn")
            self.session.cookies.set("RAIL_EXPIRATION", str(int(time.time() * 1000) + 3600000), domain="kyfw.12306.cn")
            logger.debug(f"已设置 RAIL_DEVICEID: {device_id}")

    def _generate_device_id(self) -> str:
        """生成随机的设备ID（模拟浏览器）"""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choices(chars, k=32))

    # ---------- 扫码登录 ----------
    def _create_qrcode(self) -> Tuple[Optional[str], Optional[str]]:
        url = BASE_URLS["passport"] + Endpoints.QRCODE_CREATE
        params = {"appid": "otn"}
        resp = self.session.post(url, data=params, timeout=10)
        data = resp.json()
        if data.get("result_code") != "0":
            raise Exception(f"创建二维码失败: {data.get('result_message')}")
        return data.get("uuid"), data.get("image")

    def _check_qrcode_status(self, uuid: str) -> dict:
        url = BASE_URLS["passport"] + Endpoints.QRCODE_CHECK
        data = {"uuid": uuid, "appid": "otn"}
        resp = self.session.post(url, data=data, timeout=10)
        return resp.json()

    def _poll_qrcode(self, uuid: str, timeout: int = 60) -> bool:
        start_time = time.time()
        last_status = None
        while time.time() - start_time < timeout:
            try:
                status = self._check_qrcode_status(uuid)
                code = status.get("result_code")
                if code != last_status:
                    if code == "0":
                        logger.info("等待扫码...")
                    elif code == "1":
                        logger.info("二维码已扫描，请在手机上确认登录...")
                    elif code == "2":
                        logger.info("登录确认成功！")
                        uamtk = status.get("uamtk")
                        if uamtk:
                            logger.info(f"获取到 uamtk: {uamtk[:20]}...")
                            self._set_cookie("uamtk", uamtk)
                            newapptk = self._get_newapptk()
                            if not newapptk:
                                return False
                            if not self._get_ukey(newapptk):
                                logger.warning("获取 tk 失败，但可尝试继续")
                            self._activate_session()
                            save_cookies(self.session, self.cookie_file)
                            return True
                        else:
                            logger.error("未找到 uamtk")
                            return False
                    elif code == "3":
                        logger.warning("二维码已过期，重新生成中...")
                        return False
                    last_status = code
            except Exception as e:
                logger.error(f"检查二维码状态出错: {e}")
            time.sleep(2)
        logger.warning("二维码轮询超时")
        return False

    def _display_qrcode(self, img_b64: str):
        try:
            from PIL import Image
            import io
            img_data = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_data))
            img.save("12306_login_qr.png")
            logger.info("二维码已保存为 12306_login_qr.png，请打开扫描")
        except Exception:
            logger.warning("无法显示二维码，请手动安装 Pillow 库")

    def login_by_qrcode(self) -> bool:
        max_retry = 3
        for attempt in range(1, max_retry + 1):
            try:
                uuid, img_b64 = self._create_qrcode()
                logger.info(f"二维码生成成功（第{attempt}次），请使用 12306 APP 扫描登录")
                self._display_qrcode(img_b64)
                if self._poll_qrcode(uuid):
                    return True
                if attempt < max_retry:
                    logger.info("即将重新生成二维码...")
                    time.sleep(1)
            except Exception as e:
                logger.error(f"扫码登录尝试 {attempt} 异常: {e}")
                time.sleep(2)
        logger.error("扫码登录失败")
        return False

    def _set_cookie(self, name: str, value: str, domain: str = "kyfw.12306.cn"):
        if domain in self.session.cookies._cookies:
            for path in list(self.session.cookies._cookies[domain].keys()):
                if name in self.session.cookies._cookies[domain][path]:
                    del self.session.cookies._cookies[domain][path][name]
        self.session.cookies.set(name, value, domain=domain)

    def _get_cookie(self, name: str) -> Optional[str]:
        cookies = list(self.session.cookies)
        values = [c.value for c in cookies if c.name == name]
        if not values:
            return None
        if len(values) > 1:
            logger.warning(f"发现多个 {name} Cookie，使用第一个")
        return values[0]

    def _get_newapptk(self) -> Optional[str]:
        url = BASE_URLS["passport"] + Endpoints.UAMTK
        data = {"appid": "otn"}
        resp = self.session.post(url, data=data, timeout=10)
        result = resp.json()
        logger.debug(f"_get_newapptk 响应: {result}")
        if result.get("result_code") == 0:
            newapptk = result.get("newapptk")
            if newapptk:
                self._set_cookie("newapptk", newapptk)
                logger.info("newapptk 获取成功")
                return newapptk
        logger.error("获取 newapptk 失败")
        return None

    def _get_ukey(self, newapptk: str) -> bool:
        url = BASE_URLS["kyfw"] + Endpoints.UAUTH_CLIENT
        data = {"tk": newapptk}
        resp = self.session.post(url, data=data, timeout=10)
        result = resp.json()
        logger.debug(f"_get_ukey 响应: {result}")
        if result.get("result_code") == 0:
            apptk = result.get("apptk")
            if apptk:
                self._set_cookie("tk", apptk)
            logger.info("uKey 获取成功，授权 Cookie 已设置")
            return True
        logger.error(f"获取 uKey 失败: {result}")
        return False

    def _activate_session(self):
        try:
            self.session.get(BASE_URLS["kyfw"] + "/otn/index/init", allow_redirects=True, timeout=10)
            logger.debug("已激活会话")
        except Exception as e:
            logger.warning(f"激活会话失败: {e}")

    # ---------- 密码登录 ----------
    def _get_captcha(self) -> bytes:
        url = BASE_URLS["passport"] + Endpoints.CAPTCHA_IMAGE
        params = {"login_site": "E", "module": "login", "rand": "sjrand", "_": str(int(time.time() * 1000))}
        resp = self.session.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("result_code") != "0":
            raise Exception(f"获取验证码失败: {data.get('result_message')}")
        return base64.b64decode(data.get("image"))

    def _check_captcha(self, answer: str) -> bool:
        url = BASE_URLS["passport"] + Endpoints.CAPTCHA_CHECK
        data = {"answer": answer, "login_site": "E", "rand": "sjrand"}
        resp = self.session.post(url, data=data, timeout=10)
        return resp.json().get("result_code") == "4"

    def _get_rsa_key(self) -> Tuple[str, str]:
        url = BASE_URLS["passport"] + Endpoints.GET_RSA_KEY
        resp = self.session.post(url, data={}, timeout=10)
        data = resp.json()
        if data.get("result_code") != "0":
            raise Exception(f"获取 RSA 公钥失败: {data}")
        return data.get("modulus"), data.get("exponent")

    def login_by_password(self, username: str, password: str) -> bool:
        for attempt in range(1, 4):
            try:
                img_bytes = self._get_captcha()
                answer = self.solver.solve(img_bytes)
                if not answer or not self._check_captcha(answer):
                    continue
                modulus, _ = self._get_rsa_key()
                encrypted_pwd = rsa_encrypt_password(password, modulus)
                login_url = BASE_URLS["passport"] + Endpoints.LOGIN
                login_data = {"username": username, "password": encrypted_pwd, "appid": "otn", "answer": answer}
                resp = self.session.post(login_url, data=login_data, timeout=10)
                result = resp.json()
                if result.get("result_code") == 0:
                    logger.info("密码登录成功！")
                    newapptk = self._get_newapptk()
                    if newapptk:
                        self._get_ukey(newapptk)
                    self._activate_session()
                    save_cookies(self.session, self.cookie_file)
                    return True
            except Exception as e:
                logger.error(f"登录尝试 {attempt} 异常: {e}")
            time.sleep(2)
        return False

    def login(self, username: str = None, password: str = None) -> bool:
        if self.login_method == "qrcode":
            return self.login_by_qrcode()
        else:
            if not username or not password:
                raise ValueError("密码登录需要提供用户名和密码")
            return self.login_by_password(username, password)

    def is_session_valid(self) -> bool:
        try:
            url = BASE_URLS["kyfw"] + "/otn/login/checkUser"
            resp = self.session.post(url, data={}, timeout=10)
            return resp.json().get("data", {}).get("flag") is True
        except Exception:
            return False

    def ensure_login(self, username: str = None, password: str = None) -> bool:
        if self.is_session_valid():
            logger.info("当前会话有效，无需重新登录")
            return True
        logger.info("会话无效或过期，开始登录...")
        return self.login(username, password)

    def refresh_auth(self) -> bool:
        uamtk = self._get_cookie("uamtk")
        if not uamtk:
            logger.warning("Cookie 中无 uamtk，无法刷新授权")
            return False

        logger.info("尝试使用现有 uamtk 刷新授权令牌...")
        newapptk = self._get_newapptk()
        if not newapptk:
            return False
        if not self._get_ukey(newapptk):
            return False
        self._activate_session()
        save_cookies(self.session, self.cookie_file)
        logger.info("授权令牌刷新成功")
        return True