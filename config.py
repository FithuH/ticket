import os

BASE_URLS = {
    "kyfw": "https://kyfw.12306.cn",
    "passport": "https://passport.12306.cn",
    "otn": "https://kyfw.12306.cn/otn",
}

class Endpoints:
    CAPTCHA_IMAGE = "/passport/captcha/captcha-image64"
    CAPTCHA_CHECK = "/passport/captcha/captcha-check"
    GET_RSA_KEY = "/passport/web/auth/uamtk-static"
    LOGIN = "/passport/web/login"
    UAMTK = "/passport/web/auth/uamtk"
    UAUTH_CLIENT = "/otn/uamauthclient"
    QRCODE_CREATE = "/passport/web/create-qr64"
    QRCODE_CHECK = "/passport/web/checkqr"
    STATION_JS = "/otn/resources/js/framework/station_name.js"
    QUERY_TICKET = "/otn/leftTicket/queryZ"
    SUBMIT_ORDER = "/leftTicket/submitOrderRequest"
    INIT_DC = "/confirmPassenger/initDc"
    GET_PASSENGERS = "/confirmPassenger/getPassengerDTOs"
    CHECK_ORDER_INFO = "/confirmPassenger/checkOrderInfo"
    GET_QUEUE_COUNT = "/confirmPassenger/getQueueCount"
    CONFIRM_SINGLE_FOR_QUEUE = "/confirmPassenger/confirmSingleForQueue"
    QUERY_ORDER_WAIT_TIME = "/confirmPassenger/queryOrderWaitTime"
    RESULT_ORDER_FOR_QUEUE = "/confirmPassenger/resultOrderForDcQueue"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

CAPTCHA_CONFIG = {"platform": "manual"}
RAILWAY_USERNAME = "fh050509"
RAILWAY_PASSWORD = "" 
LOGIN_METHOD = "qrcode"

DEFAULT_PREFS = {
    "seat_priority": ["二等座", "硬卧", "一等座"],
}