import os
import argparse
import logging
from config import DEFAULT_PREFS, RAILWAY_USERNAME, RAILWAY_PASSWORD
from login_handler import LoginHandler
from ticket_scanner import TicketScanner
from ticket_booker import TicketBooker

# 初始化基础日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    # 基础参数
    parser.add_argument("--from", dest="from_station", required=True)
    parser.add_argument("--to", dest="to_station", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--passengers", nargs="+", required=True)
    # 可选参数
    parser.add_argument("--trains", nargs="+")
    parser.add_argument("--seats")
    parser.add_argument("--interval", type=float, default=2.0)
    # 关键：添加 --debug 参数支持
    parser.add_argument("--debug", action="store_true", help="开启调试日志")
    
    args = parser.parse_args()

    # 如果输入了 --debug，则将全局日志级别设为 DEBUG
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("已开启 DEBUG 调试模式")

    # 1. 登录
    login_handler = LoginHandler()
    if not login_handler.ensure_login(RAILWAY_USERNAME, RAILWAY_PASSWORD):
        logger.error("登录失败，请检查账号密码或重新扫码")
        return

    # 2. 扫描与下单循环
    scanner = TicketScanner(login_handler)
    seat_priority = [s.strip() for s in args.seats.split(",")] if args.seats else DEFAULT_PREFS["seat_priority"]
    
    logger.info(f"监控启动：{args.from_station} -> {args.to_station} ({args.date})")
    
    while True:
        target_ticket = scanner.scan_loop(
            args.from_station, 
            args.to_station, 
            args.date, 
            args.trains, 
            seat_priority, 
            args.interval
        )
        
        if target_ticket:
            booker = TicketBooker(login_handler, scanner, args.date)
            # 执行下单
            is_success = booker.book_ticket(
                target_ticket, 
                args.passengers, 
                target_ticket["selected_seat"]
            )
            
            if is_success:
                logger.info("🎉 抢票流程全部完成！")
                break
            else:
                logger.warning("⚠️ 本次下单未成功，3秒后自动重新开始监控...")
                import time
                time.sleep(3)
                continue

if __name__ == "__main__":
    main()