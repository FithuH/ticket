import base64
import rsa
import pickle
import logging
import requests
import urllib.parse
from typing import List, Dict

logger = logging.getLogger(__name__)

def rsa_encrypt_password(password: str, public_key_str: str) -> str:
    exponent = int('10001', 16)
    modulus = int(public_key_str, 16)
    pubkey = rsa.PublicKey(modulus, exponent)
    encrypted = rsa.encrypt(password.encode('utf-8'), pubkey)
    return base64.b64encode(encrypted).decode('utf-8')

def parse_ticket_info(raw_data) -> List[Dict]:
    tickets = []
    if not raw_data:
        return tickets
    lines = raw_data if isinstance(raw_data, list) else [raw_data]

    for item in lines:
        if not item: continue
        parts = item.split('|')
        if len(parts) < 35: continue

        ticket = {
            "secretStr": parts[0],
            "train_no": parts[2],
            "train_code": parts[3],
            "from_station_telecode": parts[6],
            "to_station_telecode": parts[7],
            "leftTicketStr": parts[12],
            "train_location": parts[15],
            "seat_info": {
                "商务座": _clean_seat_value(parts[32]),
                "一等座": _clean_seat_value(parts[31]),
                "二等座": _clean_seat_value(parts[30]),
                "硬卧": _clean_seat_value(parts[28]),
                "硬座": _clean_seat_value(parts[29]),
                "无座": _clean_seat_value(parts[26]),
            },
            "can_buy": parts[11] == "Y",
        }
        tickets.append(ticket)
    return tickets

def _clean_seat_value(val: str) -> str:
    if not val or val in ("", "--", "无", "0", "*"):
        return "无"
    return val

def save_cookies(session: requests.Session, filename: str):
    with open(filename, 'wb') as f:
        pickle.dump(session.cookies, f)

def load_cookies(session: requests.Session, filename: str) -> bool:
    try:
        with open(filename, 'rb') as f:
            cookies = pickle.load(f)
            session.cookies.update(cookies)
        return True
    except:
        return False

def generate_passenger_ticket_str(passenger_list: List[dict], seat_type_code: str) -> str:
    # 格式: 席别,0,票种(1为成人),姓名,证件类型,证件号,手机号,N,加密串
    strs = []
    for p in passenger_list:
        # 12306 后端要求：如果 DTO 里有 allEncStr，必须带上
        enc = p.get('allEncStr', '')
        # 强制票种为 '1' (成人)
        part = f"{seat_type_code},0,1,{p['passenger_name']},{p['passenger_id_type_code']},{p['passenger_id_no']},{p['mobile_no']},N,{enc}"
        strs.append(part)
    return "_".join(strs)

def generate_old_passenger_str(passenger_list: List[dict]) -> str:
    # 格式: 姓名,证件类型,证件号,票种_
    strs = []
    for p in passenger_list:
        part = f"{p['passenger_name']},{p['passenger_id_type_code']},{p['passenger_id_no']},1_"
        strs.append(part)
    return "".join(strs)