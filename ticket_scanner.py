import time
import logging
from typing import List, Dict, Optional
from config import BASE_URLS, Endpoints
from utils import parse_ticket_info
from stations import get_station_code

logger = logging.getLogger(__name__)

class TicketScanner:
    def __init__(self, login_handler):
        self.login_handler = login_handler
        self.session = login_handler.session
        self.from_station_name = ""
        self.to_station_name = ""

    def query_tickets(self, from_station: str, to_station: str, date: str) -> List[Dict]:
        from_code = get_station_code(from_station)
        to_code = get_station_code(to_station)
        url = BASE_URLS["kyfw"] + Endpoints.QUERY_TICKET
        params = {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": from_code,
            "leftTicketDTO.to_station": to_code,
            "purpose_codes": "ADULT",
        }
        try:
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            return parse_ticket_info(data.get("data", {}).get("result", []))
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []

    def scan_loop(self, from_station, to_station, date, train_filter=None, seat_filter=None, interval=2.0):
        self.from_station_name = from_station
        self.to_station_name = to_station
        while True:
            tickets = self.query_tickets(from_station, to_station, date)
            for t in tickets:
                if train_filter and t['train_code'] not in train_filter: continue
                for seat in (seat_filter or ["二等座"]):
                    if t['seat_info'].get(seat) not in ["无", ""]:
                        t['selected_seat'] = seat
                        logger.info(f"✅ 发现车票: {t['train_code']} {seat}")
                        return t
            time.sleep(interval)