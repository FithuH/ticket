import time
import json
import logging
import requests
import urllib.parse
import re
from typing import Dict, List, Optional
from config import BASE_URLS, Endpoints, HEADERS
from utils import generate_passenger_ticket_str, generate_old_passenger_str

logger = logging.getLogger(__name__)

class TicketBooker:
    def __init__(self, login_handler, scanner, travel_date: str):
        self.login_handler = login_handler
        self.session = login_handler.session
        self.scanner = scanner
        self.travel_date = travel_date

    def book_ticket(self, target_train_info: Dict, passenger_names: List[str], seat_type: str) -> bool:
        logger.info(f"开始订票流程：{target_train_info['train_code']} | {seat_type}")
        
        # 1. 准备基础参数
        secret_str = urllib.parse.unquote(target_train_info['secretStr'])
        current_left_ticket = target_train_info['leftTicketStr']
        train_location = target_train_info['train_location']
        seat_code = self._seat_type_to_code(seat_type)
        
        # 2. 刷新 Session 环境
        self.session.get(f"{BASE_URLS['otn']}/leftTicket/init", timeout=10)

        # 3. 提交订单申请
        if not self._submit_order_request(secret_str):
            return False

        # 4. 初始化 DC 页面并提取核心 Token 与 Key
        init_data = self._init_dc()
        if not init_data or not init_data.get('token'):
            logger.error("获取订单 Token 失败，可能需要重新登录")
            return False
        
        token = init_data['token']
        # 补充 train_location 供后续接口使用
        init_data['train_location'] = train_location 
        
        # 如果页面返回了最新的票源串，立即更新
        if init_data.get('leftTicket'):
            current_left_ticket = init_data['leftTicket']

        # 5. 获取乘客列表
        all_passengers = self._get_passengers(token)
        target_passengers = [p for p in all_passengers if p['passenger_name'] in passenger_names]
        if not target_passengers:
            logger.error(f"未在常用联系人中找到: {passenger_names}")
            return False

        # 6. 校验订单 (成人票模式)
        if not self._check_order_info(target_passengers, seat_code, token):
            return False

        # 7. 获取队列状态 (GMT 时间格式)
        self._get_queue_count(target_train_info, seat_code, token, current_left_ticket)

        # 8. 确认提交队列
        if not self._confirm_single_for_queue(target_passengers, seat_code, token, current_left_ticket, init_data):
            return False

        # 9. 循环查询排队结果
        order_id = self._wait_for_order_id(token)
        if order_id:
            logger.info(f"🎉 订票成功！订单号: {order_id}，请在30分钟内完成支付")
            return True
        
        return False

    def _submit_order_request(self, secret_str: str) -> bool:
        url = BASE_URLS["otn"] + Endpoints.SUBMIT_ORDER
        data = {
            "secretStr": secret_str,
            "train_date": self.travel_date,
            "back_train_date": self.travel_date,
            "tour_flag": "dc",
            "purpose_codes": "ADULT",
            "query_from_station_name": self.scanner.from_station_name,
            "query_to_station_name": self.scanner.to_station_name,
            "undefined": ""
        }
        headers = {**HEADERS, "Referer": "https://kyfw.12306.cn/otn/leftTicket/init"}
        try:
            resp = self.session.post(url, data=data, headers=headers, timeout=10)
            return resp.json().get("status") is True
        except: return False

    def _init_dc(self) -> Optional[dict]:
        url = BASE_URLS["otn"] + Endpoints.INIT_DC
        headers = {**HEADERS, "Referer": "https://kyfw.12306.cn/otn/leftTicket/init"}
        try:
            resp = self.session.post(url, data={"_json_att": ""}, headers=headers, timeout=10)
            token = re.search(r"var globalRepeatSubmitToken = '([^']+)';", resp.text)
            left_ticket = re.search(r"'leftTicketStr':'([^']+)'", resp.text)
            key_check = re.search(r"'key_check_isChange':'([^']+)'", resp.text)
            
            return {
                "token": token.group(1) if token else None,
                "leftTicket": left_ticket.group(1) if left_ticket else None,
                "key_check": key_check.group(1) if key_check else None
            }
        except: return None

    def _get_passengers(self, token: str) -> List[Dict]:
        url = BASE_URLS["otn"] + Endpoints.GET_PASSENGERS
        data = {"_json_att": "", "REPEAT_SUBMIT_TOKEN": token}
        try:
            resp = self.session.post(url, data=data, timeout=10)
            return resp.json().get("data", {}).get("normal_passengers", [])
        except: return []

    def _check_order_info(self, passengers, seat_code, token) -> bool:
        url = BASE_URLS["otn"] + Endpoints.CHECK_ORDER_INFO
        data = {
            "cancel_flag": "2",
            "bed_level_info": "000000000000000000000000000000",
            "passengerTicketStr": generate_passenger_ticket_str(passengers, seat_code),
            "oldPassengerStr": generate_old_passenger_str(passengers),
            "tour_flag": "dc",
            "randCode": "",
            "whatsSelect": "1",
            "_json_att": "",
            "REPEAT_SUBMIT_TOKEN": token
        }
        headers = {**HEADERS, "Referer": "https://kyfw.12306.cn/otn/confirmPassenger/initDc"}
        try:
            resp = self.session.post(url, data=data, headers=headers, timeout=10)
            res = resp.json()
            if res.get("data", {}).get("submitStatus") is True:
                return True
            logger.error(f"校验失败：{res.get('data', {}).get('errMsg')}")
            return False
        except: return False

    def _get_queue_count(self, info, seat_code, token, left_ticket):
        url = BASE_URLS["otn"] + Endpoints.GET_QUEUE_COUNT
        st = time.strptime(self.travel_date, "%Y-%m-%d")
        gmt_date = time.strftime("%a %b %d %Y 00:00:00 GMT+0800 (中国标准时间)", st)
        data = {
            "train_date": gmt_date,
            "train_no": info['train_no'],
            "stationTrainCode": info['train_code'],
            "seatType": seat_code,
            "fromStationTelecode": info['from_station_telecode'],
            "toStationTelecode": info['to_station_telecode'],
            "leftTicket": left_ticket,
            "purpose_codes": "00",
            "train_location": info['train_location'],
            "_json_att": "",
            "REPEAT_SUBMIT_TOKEN": token
        }
        self.session.post(url, data=data, timeout=10)

    def _confirm_single_for_queue(self, passengers, seat_code, token, left_ticket, init_data) -> bool:
        url = BASE_URLS["otn"] + Endpoints.CONFIRM_SINGLE_FOR_QUEUE
        # 优先级：从 initDc 抓取的 key_check > train_location
        key_check = init_data.get('key_check') or init_data.get('train_location')
        
        data = {
            "passengerTicketStr": generate_passenger_ticket_str(passengers, seat_code),
            "oldPassengerStr": generate_old_passenger_str(passengers),
            "randCode": "",
            "purpose_codes": "00",
            "key_check_isChange": key_check,
            "leftTicketStr": left_ticket,
            "train_location": init_data.get('train_location'),
            "choose_seats": "",
            "seatDetailType": "000",
            "whatsSelect": "1",
            "roomType": "00",
            "dwAll": "N",
            "_json_att": "",
            "REPEAT_SUBMIT_TOKEN": token
        }
        headers = {**HEADERS, "Referer": "https://kyfw.12306.cn/otn/confirmPassenger/initDc"}
        try:
            resp = self.session.post(url, data=data, headers=headers, timeout=10)
            res = resp.json()
            if res.get("data", {}).get("submitStatus") is True:
                logger.info("✅ 已成功提交至排队队列！")
                return True
            else:
                # 增强报错捕获
                err = res.get("data", {}).get("errMsg") or res.get("messages", "未知错误")
                logger.error(f"❌ 确认提交失败原因: {err}")
                return False
        except Exception as e:
            logger.error(f"确认提交请求异常: {e}")
            return False

    def _wait_for_order_id(self, token: str) -> Optional[str]:
        url = BASE_URLS["otn"] + Endpoints.QUERY_ORDER_WAIT_TIME
        # 适当增加重试次数，排队可能需要一点时间
        for i in range(20):
            params = {
                "random": str(int(time.time()*1000)), 
                "tourFlag": "dc", 
                "_json_att": "", 
                "REPEAT_SUBMIT_TOKEN": token
            }
            try:
                resp = self.session.get(url, params=params, timeout=10)
                res = resp.json()
                if res.get("status"):
                    d = res["data"]
                    # 1. 如果拿到了订单号，直接成功
                    if d.get("orderId"): 
                        return d["orderId"]
                    
                    # 2. 检查排队消息
                    msg = d.get("msg")
                    if msg:
                        logger.warning(f"排队系统提示: {msg}")
                        # 如果提示行程冲突或已有订单，其实也算“成功”了（因为你已经占到位置了）
                        if "行程冲突" in msg or "未支付订单" in msg:
                            return "ALREADY_BOOKED"
                    
                    # 3. 检查等待时间
                    wait_time = d.get("waitTime", 0)
                    if wait_time >= 0:
                        logger.info(f"正在排队中，预计等待 {wait_time} 秒...")
                    else:
                        # waitTime < 0 通常意味着失败
                        break
                time.sleep(2.5) # 稍微延长间隔，防止“频繁请求”
            except: 
                time.sleep(2)
        return None

    def _seat_type_to_code(self, seat_name: str) -> str:
        mapping = {"商务座": "9", "一等座": "M", "二等座": "O", "硬卧": "3", "硬座": "1"}
        return mapping.get(seat_name, "O")