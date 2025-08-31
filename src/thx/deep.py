import json
import logging
import time
import os
from openai import OpenAI
import dotenv
import datetime
from thx.thx_tool import ThxApi
from tool.util import send_mail

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

DEEP_TOKEN = os.getenv('DEEP_TOKEN')
RECORD_FILE = "stock_signal_records.json"

client = OpenAI(
    api_key=DEEP_TOKEN,
    base_url="https://api.deepseek.com",
)


def generate_user_prompt(stock_code,df_1d,df_5m):
    ''' 
    生成股票交易提示词
    '''

    user_prompt = f'''你是一个精通缠论的交易员, 根据用户提供的股票数据，基于缠论的买卖点原则, 并给出明确交易指示.包括：
    操作方向：买入/卖出/观望
    止盈价格：xx.xx
    止损价格：xx.xx
    

    你现在的任务是分析股票 {stock_code} 的交易情况, 并给出当前明确交易指示，输入数据包括：

    股票日K数据:
    {df_1d}

    股票5分钟K线数据:
    {df_5m}
    '''
    return user_prompt

def get_signal_from_deepseek(user_prompt):
    '''
    从大模型获得股票交易信号
    '''
    system_prompt = """
    The user will provide some exam text. Please parse the "question" and "answer" and output them in JSON format. 

    EXAMPLE INPUT: 
    基于缠论方法，请给出股票000001的交易指示.

    EXAMPLE JSON OUTPUT:
    {
        "股票代码": "000001",
        "操作方向": "买入/卖出/观望",
        "止盈价格": 15.00,# 适用于买入
        "止损价格": 14.50,# 适用于卖出
        "交易原因": '基于缠论分析，当前股票处于下跌趋势中，RSI指标显示超卖，建议持有观望，等待更明确的买入信号。'
    }
    """
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}]

    response = client.chat.completions.create(
        # model="deepseek-reasoner",
        model="deepseek-chat",
        messages=messages,
        response_format={
            'type': 'json_object'
        },
        temperature=0,
    )

    return json.loads(response.choices[0].message.content)

def check_stock_signal(stock_code):
    logger.info(f'检查股票 {stock_code} 信号')

    
    user_prompt = generate_user_prompt(stock_code,df_1d,df_5m)
    if api.isTrading:
        signal = get_signal_from_deepseek(user_prompt)
    else:
        signal = None
    return signal



def check_stock_signal(stock_code,force_check=False):
    # 记录函数开始时间（时间戳，单位：秒）
    start_total = time.time()
    logger.info(f'===== 开始检查股票 {stock_code} 信号，开始时间：{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_total))} =====')

    try:
        start_total = time.time()
        api = ThxApi(stock_code)
        df_1d = api.history('d',90)
        df_5m = api.last('5m')
        user_prompt = generate_user_prompt(stock_code,df_1d,df_5m)
        if api.isTrading == 0 or force_check:
            current_signal = get_signal_from_deepseek(user_prompt)
            end_total = time.time()
            total_cost = round(end_total - start_total, 4)
            current_signal['检查时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_signal['耗费时长'] = total_cost
            logger.info(f'===== 股票 {stock_code} 信号检查完成，总耗时：{total_cost} 秒 =====')

            history_latest_direction = get_stock_latest_direction(stock_code)
            # 判断：若历史方向不存在（首次记录）或与当前方向不一致 → 写入文件
            if history_latest_direction is None or history_latest_direction["操作方向"] != current_signal["操作方向"]:
                write_signal_to_file(current_signal)
                text_last = json.dumps(history_latest_direction, ensure_ascii=False,indent=4) if history_latest_direction else ''
                text_current = json.dumps(current_signal, ensure_ascii=False,indent=4) if current_signal else ''
                send_mail(os.getenv('MAIL_SENTTO'), f'股票 {stock_code} --> {current_signal["操作方向"]}', f'上次操作指令：{text_last}\n\n当前操作指令：{text_current}')
                logger.info(f'股票 {stock_code} 操作方向变化（历史：{history_latest_direction} → 当前：{current_signal["操作方向"]}），已写入文件')
            else:
                logger.info(f'股票 {stock_code} 操作方向未变化（当前：{current_signal["操作方向"]}），无需写入文件')
        else:
            logger.info(f'===== 股票 {stock_code} 非交易时间，无需检查 =====')
            current_signal = None
        return current_signal

    except Exception as e:
        end_error = time.time()
        error_cost = round(end_error - start_total, 4)
        logger.error(f'检查股票 {stock_code} 信号时发生错误，错误耗时：{error_cost} 秒，错误信息：{str(e)}', exc_info=True)

def write_signal_to_file(signal):
    """辅助函数：将信号记录写入文件（追加模式，每行一条JSON，便于读取）"""
    # 确保文件所在目录存在（如./data不存在则创建）
    file_dir = os.path.dirname(RECORD_FILE)
    if file_dir and not os.path.exists(file_dir):
        os.makedirs(file_dir)

    # 追加写入（每行一条JSON，避免多条记录在同一行导致解析错误）
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        json.dump(signal, f, ensure_ascii=False)  # ensure_ascii=False：支持中文
        f.write("\n")  # 换行分隔，便于后续按行读取

def get_stock_latest_direction(stock_code):
    """辅助函数：读取历史记录，获取指定股票的最新操作方向"""
    # 若记录文件不存在 → 首次检查，无历史方向
    if not os.path.exists(RECORD_FILE):
        return None

    # 读取文件中的所有历史记录（JSON格式，每行一条记录）
    try:
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            # 按行读取（避免单条记录过大导致JSON解析失败）
            history_records = [json.loads(line.strip()) for line in f if line.strip()]
    except Exception as e:
        logger.warning(f'读取历史记录文件失败：{str(e)}，将重新创建文件')
        return None

    # 筛选该股票的所有历史记录
    stock_records = [rec for rec in history_records if rec.get("股票代码") == stock_code]
    if not stock_records:  # 该股票无历史记录
        return None

    # 按“检查时间”排序，取最新一条的操作方向（时间格式：%Y-%m-%d %H:%M:%S，可直接字符串比较）
    stock_records_sorted = sorted(stock_records, key=lambda x: x["检查时间"], reverse=True)
    return stock_records_sorted[0]

if __name__ == '__main__':
    from tool.util import setup_logging
    setup_logging(log_file='deep.log',level=logging.INFO)
    charset_logger = logging.getLogger('httpcore.http11')
    charset_logger.propagate = False
    charset_logger.setLevel(logging.WARNING)
    stock_code = 'HK3690'
    signal = check_stock_signal(stock_code,force_check=True)
    logger.info(signal)