import datetime
import time
import logging
from tool.util import setup_logging
from thx.deep import check_stock_signal

logger = logging.getLogger(__name__)

# 交易时间配置（A股/港股，可根据实际规则调整）
TRADE_HOURS = {
    "A股": {
        "morning_start": datetime.time(9, 30),   # 早盘开始
        "morning_end": datetime.time(11, 30),     # 早盘结束
        "afternoon_start": datetime.time(13, 0),  # 午盘开始
        "afternoon_end": datetime.time(15, 0)     # 午盘结束
    },
    "港股": {
        "morning_start": datetime.time(9, 30),
        "morning_end": datetime.time(12, 0),
        "afternoon_start": datetime.time(13, 0),
        "afternoon_end": datetime.time(16, 0)
    }
}

# 循环间隔（单位：秒，例如60秒=1分钟执行一次，根据需求调整）
LOOP_INTERVAL = 60 * 15


# ---------------------- 2. 核心判断函数 ----------------------
def is_workday() -> bool:
    """
    判断当前日期是否为工作日（周一到周五，暂不包含法定节假日）
    返回：True=工作日，False=周末
    """
    today = datetime.datetime.now().weekday()  # weekday()：0=周一，4=周五，5=周六，6=周日
    return today < 5  # 周一到周五返回True，周末返回False


def is_trading_time(market: str) -> bool:
    """
    判断当前时间是否在指定市场的交易时间内
    参数：market - "A股" 或 "港股"
    返回：True=交易时间内，False=非交易时间
    """
    if market not in TRADE_HOURS:
        logger.error(f"不支持的市场类型：{market}，仅支持'A股'或'港股'")
        return False

    now = datetime.datetime.now()
    current_time = now.time()  # 当前时间（时分秒）
    trade_rule = TRADE_HOURS[market]

    # 1. 判断是否在早盘交易时间（开盘<=当前时间<=早盘结束）
    in_morning = trade_rule["morning_start"] <= current_time <= trade_rule["morning_end"]
    # 2. 判断是否在午盘交易时间（午盘开始<=当前时间<=收盘）
    in_afternoon = trade_rule["afternoon_start"] <= current_time <= trade_rule["afternoon_end"]

    return in_morning or in_afternoon


# ---------------------- 3. 待执行的业务函数 ----------------------
def do(force_check=False):
    """
    你需要循环执行的核心业务函数（替换为实际逻辑，例如检查股票信号、发送通知等）
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now}] 执行do()函数，业务逻辑执行中...")

    sotcks = ('HK0388','HK2018','HK0981')
    for stock in sotcks:
        signal = check_stock_signal(stock,force_check)
        logger.info(f"{stock} {signal}")


# ---------------------- 4. 循环任务调度器 ----------------------
def start_scheduled_task(target_markets: list,force_check=False):
    """
    启动循环任务，仅在工作日的目标市场交易时间内执行do()
    参数：target_markets - 目标市场列表，例如 ["A股", "港股"] 或 ["A股"]
    """
    logger.info("=" * 50)
    logger.info("循环任务调度器已启动，开始监控时间...")
    logger.info(f"目标市场：{target_markets}，循环间隔：{LOOP_INTERVAL}秒")
    logger.info("=" * 50)

    try:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


            in_any_trading_time = False
            for market in target_markets:
                if is_trading_time(market):
                    in_any_trading_time = True
                    break  # 只要有一个市场在交易时间内，就触发执

            if force_check or (in_any_trading_time and is_workday()) :
                do(force_check)
            else:
                logger.debug(f"[{now}] 当前为非工作日或非交易时间，不执行任务")

            # 3. 休眠指定间隔后，再次循环检查
            time.sleep(LOOP_INTERVAL)

    except KeyboardInterrupt:
        logger.info("用户手动停止循环任务")
    except Exception as e:
        logger.error(f"循环任务意外终止：{str(e)}", exc_info=True)


# ---------------------- 5. 启动入口 ----------------------
if __name__ == "__main__":
    # 配置目标市场（根据需求选择 ["A股", "港股"] 或单个市场）
    setup_logging('deep_check.log')
    TARGET_MARKETS = ["A股", "港股"]
    # 启动循环任务
    start_scheduled_task(TARGET_MARKETS,False)
