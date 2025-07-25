import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import time
import logging
import os
import traceback
from functools import wraps

# 日志配置
def setup_logging():
    """配置日志系统"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(
                f'logs/stock_app_{datetime.now().strftime("%Y%m%d")}.log',
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('StockApp')
    logger.setLevel(logging.INFO)
    
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('plotly').setLevel(logging.WARNING)
    
    return logger

logger = setup_logging()

# 装饰器：用于记录函数调用
def log_function_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.info(f"开始执行函数: {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"函数 {func.__name__} 执行成功，用时: {execution_time:.2f}秒")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败，用时: {execution_time:.2f}秒，错误: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    return wrapper

# 配置常量
TOKEN = "F7A19AE8-38E9-4F94-B189-6A9A161658D8"
BASE_URL = "https://api.zhituapi.com/hs"
REAL_TIME_URL = f"{BASE_URL}/real/ssjy"
HISTORY_URL = f"{BASE_URL}/history"
BASE_INFO_URL = f"{BASE_URL}/instrument"

MARKET_MAP = {
    "sh": "SH",
    "sz": "SZ",
    "bj": "BJ",
}

logger.info("应用程序启动，常量配置完成")
logger.info(f"TOKEN配置: {TOKEN[:8]}...{TOKEN[-8:]}")
logger.info(f"实时行情URL: {REAL_TIME_URL}")
logger.info(f"历史数据URL: {HISTORY_URL}")
logger.info(f"基础信息URL: {BASE_INFO_URL}")

class ZhituApi:
    """智图API封装类"""
    
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        })
        logger.info(f"ZhituApi 初始化完成，token: {token[:8]}...{token[-8:]}")
    
    @log_function_call
    def get_base_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票基础信息"""
        try:
            url = f"{BASE_INFO_URL}/{stock_code}"
            params = {'token': self.token}
            
            logger.info(f"开始获取股票基础信息 - 股票代码: {stock_code}")
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            
            response = self.session.get(url, params=params, timeout=15)
            logger.info(f"基础信息API响应状态码: {response.status_code}")
            response.raise_for_status()
            
            raw_content = response.text
            logger.info(f"基础信息API原始响应内容: {raw_content}")
            
            try:
                data = response.json()
                logger.info(f"解析后的基础信息JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                if isinstance(data, dict):
                    logger.info(f"股票 {stock_code} 基础信息获取成功")
                    logger.info(f"股票名称: {data.get('name', 'N/A')}")
                    logger.info(f"上市日期: {data.get('od', 'N/A')}")
                    logger.info(f"总股本: {data.get('tv', 'N/A')}")
                    logger.info(f"流通股本: {data.get('fv', 'N/A')}")
                else:
                    logger.warning(f"股票 {stock_code} 基础信息格式异常: {type(data)}")
                
                return data
                
            except json.JSONDecodeError as e:
                logger.error(f"基础信息JSON解析失败 - 股票: {stock_code}, 错误: {str(e)}")
                logger.error(f"响应内容: {raw_content}")
                return None
            
        except requests.RequestException as e:
            logger.error(f"基础信息网络请求失败 - 股票: {stock_code}, 错误: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"HTTP状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"获取基础信息未知错误 - 股票: {stock_code}, 错误: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    @log_function_call
    def get_real_time_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        try:
            stock_code = stock_code[:6]if len(stock_code) > 6 else stock_code
            url = f"{REAL_TIME_URL}/{stock_code}"
            params = {'token': self.token}
            
            logger.info(f"开始获取股票实时数据 - 股票代码: {stock_code}")
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            
            response = self.session.get(url, params=params, timeout=15)
            logger.info(f"API响应状态码: {response.status_code}")
            logger.info(f"API响应头: {dict(response.headers)}")
            response.raise_for_status()
            
            raw_content = response.text
            logger.info(f"API原始响应内容: {raw_content}")
            
            try:
                data = response.json()
                logger.info(f"解析后的JSON数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                if isinstance(data, dict):
                    logger.info(f"股票 {stock_code} 实时数据获取成功")
                    logger.info(f"当前价格: {data.get('p', 'N/A')}")
                    logger.info(f"涨跌额: {data.get('ud', 'N/A')}")
                    logger.info(f"涨跌幅: {data.get('pc', 'N/A')}%")
                    logger.info(f"成交量: {data.get('v', 'N/A')}")
                    logger.info(f"成交额: {data.get('cje', 'N/A')}")
                    logger.info(f"更新时间: {data.get('t', 'N/A')}")
                else:
                    logger.warning(f"股票 {stock_code} 返回数据格式异常: {type(data)}")
                
                return data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 - 股票: {stock_code}, 错误: {str(e)}")
                logger.error(f"响应内容: {raw_content}")
                return None
            
        except requests.RequestException as e:
            logger.error(f"网络请求失败 - 股票: {stock_code}, 错误: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"HTTP状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"获取实时数据发生未知错误 - 股票: {stock_code}, 错误: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    @log_function_call
    def get_historical_data(self, stock_code: str, period: str = 'd', 
                          start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
        try:
            url = f"{HISTORY_URL}/{stock_code}/{period}/f"
            
            params = {'token': self.token}
            if start_date:
                params['st'] = start_date
            if end_date:
                params['et'] = end_date
            
            logger.info(f"开始获取股票历史数据")
            logger.info(f"股票代码: {stock_code}")
            logger.info(f"时间周期: {period}")
            logger.info(f"开始日期: {start_date}")
            logger.info(f"结束日期: {end_date}")
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            
            response = self.session.get(url, params=params, timeout=20)
            logger.info(f"历史数据API响应状态码: {response.status_code}")
            response.raise_for_status()
            
            raw_content = response.text
            logger.info(f"历史数据API响应长度: {len(raw_content)} 字符")
            
            try:
                data = response.json()
                
                if isinstance(data, list):
                    logger.info(f"历史数据获取成功 - 股票: {stock_code}, 返回 {len(data)} 条记录")
                    
                    if len(data) > 0:
                        logger.info(f"历史数据样本（前3条）:")
                        for i, record in enumerate(data[:3]):
                            logger.info(f"  记录{i+1}: {json.dumps(record, ensure_ascii=False)}")
                        
                        if len(data) > 6:
                            logger.info(f"历史数据样本（后3条）:")
                            for i, record in enumerate(data[-3:]):
                                logger.info(f"  记录{len(data)-2+i}: {json.dumps(record, ensure_ascii=False)}")
                        
                        first_date = data[0].get('t', 'N/A')
                        last_date = data[-1].get('t', 'N/A')
                        logger.info(f"数据日期范围: {first_date} 到 {last_date}")
                    
                    return data
                else:
                    logger.error(f"历史数据格式错误 - 股票: {stock_code}, 数据类型: {type(data)}")
                    logger.error(f"返回数据: {json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"历史数据JSON解析失败 - 股票: {stock_code}, 错误: {str(e)}")
                logger.error(f"响应内容前500字符: {raw_content[:500]}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"获取历史数据网络请求失败 - 股票: {stock_code}, 错误: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"HTTP状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"获取历史数据发生未知错误 - 股票: {stock_code}, 错误: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None

@st.cache_data(ttl=86400)
@log_function_call
def get_cached_base_info(token: str, stock_code: str):
    """获取缓存的股票基础信息"""
    logger.info(f"从缓存获取基础信息: {stock_code}")
    api = ZhituApi(token)
    result = api.get_base_info(stock_code)
    logger.info(f"缓存基础信息结果: {'成功' if result else '失败'}")
    return result

@st.cache_data(ttl=60)
@log_function_call
def get_cached_real_time_data(token: str, stock_code: str):
    logger.info(f"从缓存获取实时数据: {stock_code}")
    api = ZhituApi(token)
    result = api.get_real_time_data(stock_code)
    logger.info(f"缓存实时数据结果: {'成功' if result else '失败'}")
    return result

@st.cache_data(ttl=300)
@log_function_call
def get_cached_historical_data(token: str, stock_code: str, start_date: str, end_date: str):
    logger.info(f"从缓存获取历史数据: {stock_code}, {start_date} - {end_date}")
    api = ZhituApi(token)
    result = api.get_historical_data(stock_code, 'd', start_date, end_date)
    logger.info(f"缓存历史数据结果: {'成功' if result else '失败'}, 记录数: {len(result) if result else 0}")
    return result

@log_function_call
def determine_market_code(code: str) -> str:
    logger.info(f"开始确定股票代码市场归属: {code}")
    
    if '.' in code:
        logger.info(f"股票代码已包含市场信息: {code}")
        return code.upper()
    
    if not code.isdigit() or len(code) != 6:
        logger.warning(f"股票代码格式异常: {code}")
        return code
    
    market_suffix = ""
    market_name = ""
    
    if code.startswith(('000', '002', '003', '300')):
        market_suffix = ".SZ"
        market_name = "深圳交易所"
    elif code.startswith(('600', '601', '603', '605', '688')):
        market_suffix = ".SH"
        market_name = "上海交易所"
    elif code.startswith(('430', '831', '832', '833', '834', '835', '836', '837', '838', '839')):
        market_suffix = ".BJ"
        market_name = "北京交易所"
    else:
        market_suffix = ".SZ"
        market_name = "深圳交易所（默认）"
    
    full_code = f"{code}{market_suffix}"
    logger.info(f"股票代码市场归属确定: {code} -> {full_code} ({market_name})")
    return full_code

@log_function_call
def create_candlestick_chart(df: pd.DataFrame, title: str, stock_code: str) -> go.Figure:
    logger.info(f"开始创建K线图 - 股票: {stock_code}, 数据量: {len(df)} 条")
    logger.info(f"图表标题: {title}")
    
    try:
        # 处理日期，确保只包含年月日
        df['date_only'] = pd.to_datetime(df['t']).dt.date
        df['date_str'] = df['date_only'].astype(str)
        
        # 过滤掉无交易的日期（通过检查成交量是否为0）
        # 注意：实际交易中成交量为0的情况极少见，这里主要是确保数据连续性
        original_count = len(df)
        df = df[df['v'] > 0].copy()  # 保留成交量大于0的记录（有交易）
        filtered_count = len(df)
        
        if original_count != filtered_count:
            logger.info(f"过滤掉无交易的日期 - 原始: {original_count} 条, 过滤后: {filtered_count} 条")
        
        if not df.empty:
            logger.info(f"数据日期范围: {df['date_str'].min()} 到 {df['date_str'].max()}")
            logger.info(f"价格范围: {df['c'].min():.2f} - {df['c'].max():.2f}")
            logger.info(f"成交量范围: {df['v'].min():.0f} - {df['v'].max():.0f}")
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(title, f'成交量 - {stock_code}'),
            row_heights=[0.7, 0.3]
        )
        
        fig.add_trace(
            go.Candlestick(
                x=df['date_str'],  # 只使用有交易的日期
                open=df['o'],
                high=df['h'],
                low=df['l'],
                close=df['c'],
                name="价格",
                increasing_line_color='red',
                decreasing_line_color='green',
                increasing_fillcolor='red',
                decreasing_fillcolor='green'
            ),
            row=1, col=1
        )
        
        colors = ['red' if close >= open else 'green' 
                  for close, open in zip(df['c'], df['o'])]
        
        fig.add_trace(
            go.Bar(
                x=df['date_str'],  # 只使用有交易的日期
                y=df['v'],
                name="成交量",
                marker_color=colors,
                opacity=0.6
            ),
            row=2, col=1
        )
        
        # 设置x轴按月显示，且只显示有交易的日期
        fig.update_layout(
            title=title,
            xaxis_rangeslider_visible=False,
            height=600,
            showlegend=False,
            xaxis2_title="日期",
            yaxis_title="价格(元)",
            yaxis2_title="成交量",
            xaxis=dict(
                tickformat='%Y-%m-%d',  # 显示具体日期
                tickangle=45,
                tickmode='array',  # 使用数组模式
                tickvals=df['date_str'].iloc[::len(df)//6]  # 均匀选取约6个点显示（半年数据）
            ),
            xaxis2=dict(
                tickformat='%Y-%m-%d',  # 显示具体日期
                tickangle=45,
                tickmode='array',  # 使用数组模式
                tickvals=df['date_str'].iloc[::len(df)//6]  # 均匀选取约6个点显示
            )
        )
        
        logger.info(f"K线图创建完成 - 股票: {stock_code}")
        return fig
        
    except Exception as e:
        logger.error(f"创建K线图失败 - 股票: {stock_code}, 错误: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        raise

def format_large_number(num) -> str:
    try:
        num = float(num)
        if num >= 100000000:
            return f"{num/100000000:.2f}亿"
        elif num >= 10000:
            return f"{num/10000:.2f}万"
        else:
            return f"{num:.2f}"
    except (ValueError, TypeError):
        logger.warning(f"格式化数字失败: {num}")
        return "N/A"

def format_percentage(num) -> str:
    try:
        return f"{float(num):.2f}%"
    except (ValueError, TypeError):
        logger.warning(f"格式化百分比失败: {num}")
        return "N/A"

def format_price(num) -> str:
    try:
        return f"{float(num):.2f}"
    except (ValueError, TypeError):
        logger.warning(f"格式化价格失败: {num}")
        return "N/A"

def get_half_year_ago_date() -> str:
    half_year_ago = datetime.now() - timedelta(days=180)
    date_str = half_year_ago.strftime('%Y%m%d')
    logger.info(f"半年前日期: {date_str}")
    return date_str

def get_today_date() -> str:
    date_str = datetime.now().strftime('%Y%m%d')
    logger.info(f"今天日期: {date_str}")
    return date_str

@log_function_call
def log_user_input(stock_input: str):
    logger.info("=== 用户输入记录 ===")
    logger.info(f"原始输入: '{stock_input}'")
    logger.info(f"输入长度: {len(stock_input)}")
    logger.info(f"输入类型检查: 纯数字={stock_input.isdigit()}, 包含点={('.' in stock_input)}")
    logger.info(f"输入时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    cleaned_input = stock_input.strip().upper()
    logger.info(f"清理后输入: '{cleaned_input}'")
    
    if not cleaned_input:
        logger.warning("用户输入为空")
        return False, "股票代码不能为空"
    
    if '.' in cleaned_input:
        code_part = cleaned_input.split('.')[0]
        market_part = cleaned_input.split('.')[1] if len(cleaned_input.split('.')) > 1 else ""
        logger.info(f"输入包含市场后缀 - 代码: {code_part}, 市场: {market_part}")
        
        if not code_part.isdigit() or len(code_part) != 6:
            logger.warning(f"股票代码格式错误: {code_part}")
            return False, "股票代码必须为6位数字"
            
        if market_part not in ['SH', 'SZ', 'BJ']:
            logger.warning(f"市场代码格式错误: {market_part}")
            return False, "市场代码必须为SH、SZ或BJ"
    else:
        if not cleaned_input.isdigit() or len(cleaned_input) != 6:
            logger.warning(f"股票代码格式错误: {cleaned_input}")
            return False, "股票代码必须为6位数字"
    
    logger.info("用户输入验证通过")
    return True, cleaned_input

@log_function_call
def display_log_viewer():
    st.subheader("📋 系统日志")
    
    try:
        log_file = f'logs/stock_app_{datetime.now().strftime("%Y%m%d")}.log'
        
        if os.path.exists(log_file):
            logger.info(f"读取日志文件: {log_file}")
            
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.readlines()
            
            recent_logs = logs[-100:] if len(logs) > 100 else logs
            
            log_level = st.selectbox(
                "选择日志级别:",
                ["ALL", "ERROR", "WARNING", "INFO", "DEBUG"],
                index=0
            )
            
            if log_level != "ALL":
                filtered_logs = [log for log in recent_logs if f" {log_level} " in log]
            else:
                filtered_logs = recent_logs
            
            st.info(f"显示最近 {len(filtered_logs)} 条日志记录（总计 {len(logs)} 条）")
            
            if filtered_logs:
                log_text = "".join(filtered_logs)
                st.text_area(
                    "日志内容:",
                    value=log_text,
                    height=400,
                    help="显示应用程序运行日志"
                )
            else:
                st.warning("没有符合条件的日志记录")
                
        else:
            st.warning(f"日志文件不存在: {log_file}")
            logger.warning(f"日志文件不存在: {log_file}")
            
    except Exception as e:
        logger.error(f"显示日志失败: {str(e)}")
        st.error(f"读取日志文件失败: {e}")

@log_function_call
def main():
    logger.info("=== 主函数开始执行 ===")
    
    try:
        st.set_page_config(
            page_title="股票实时行情查询系统",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        logger.info("Streamlit页面配置完成")
        
        st.title("📊 股票实时行情查询系统")
        st.markdown("---")
        
        with st.sidebar:
            st.header("🔍 股票查询")
            
            stock_input = st.text_input(
                "请输入股票代码:",
                value="000001",
                help="支持格式: 000001 或 000001.SZ",
                key="stock_input"
            )
            
            if stock_input:
                logger.info(f"用户当前输入: {stock_input}")
            
            query_button = st.button("📈 查询股票", type="primary", use_container_width=True)
            
            show_logs = st.checkbox("📋 显示系统日志", value=False)
            
            st.markdown("---")
            st.markdown("### 📋 支持市场")
            st.markdown("""
            - **上海交易所**: 600×××, 601×××, 603×××, 688×××
            - **深圳交易所**: 000×××, 002×××, 300×××
            - **北京交易所**: 43×××, 83××××
            """)
            
            st.markdown("### 🕐 数据说明")
            st.markdown("""
            - 实时数据每分钟更新
            - K线图显示近半年数据（仅包含交易日）
            - 数据来源: 智图API
            - 所有操作都有详细日志记录
            """)
        
        if show_logs:
            logger.info("用户查看系统日志")
            display_log_viewer()
            return
        
        if query_button and stock_input:
            logger.info("=== 开始处理用户查询 ===")
            
            is_valid, cleaned_input = log_user_input(stock_input)
            
            if not is_valid:
                logger.error(f"用户输入验证失败: {cleaned_input}")
                st.error(f"❌ 输入错误: {cleaned_input}")
                return
            
            full_stock_code = determine_market_code(cleaned_input)
            
            logger.info(f"处理查询 - 原始输入: {stock_input}, 清理后: {cleaned_input}, 完整代码: {full_stock_code}")
            
            with st.spinner("正在获取股票数据..."):
                logger.info("=== 开始获取股票基础信息 ===")
                base_info = get_cached_base_info(TOKEN, full_stock_code)
                
                if not base_info:
                    logger.warning(f"获取基础信息失败，但继续执行（非关键数据）: {full_stock_code}")
                    st.warning("⚠️ 无法获取股票基础信息，可能影响部分展示内容")
                
                logger.info("=== 开始获取实时数据 ===")
                realtime_data = get_cached_real_time_data(TOKEN, full_stock_code)
                
                if not realtime_data:
                    logger.error(f"获取实时数据失败: {full_stock_code}")
                    st.error("❌ 无法获取实时行情数据，请检查股票代码是否正确或稍后再试")
                    return
                
                logger.info("=== 实时数据获取成功 ===")
                
                start_date = get_half_year_ago_date()
                end_date = get_today_date()
                
                logger.info("=== 开始获取历史数据 ===")
                historical_data = get_cached_historical_data(TOKEN, full_stock_code, start_date, end_date)
                
                stock_name = base_info.get('name', realtime_data.get('name', full_stock_code))
                st.subheader(f"📈 {stock_name} ({full_stock_code})")
                
                st.markdown("### 📋 股票基础信息")
                if base_info:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.info(f"**市场代码**\n{base_info.get('ei', 'N/A')}")
                        st.info(f"**股票代码**\n{base_info.get('ii', 'N/A')}")
                    
                    with col2:
                        st.info(f"**上市日期**\n{base_info.get('od', 'N/A')}")
                        # 前收盘价保留2位小数
                        st.info(f"**前收盘价**\n{format_price(base_info.get('pc', 'N/A'))}元")
                    
                    with col3:
                        st.info(f"**涨停价**\n{format_price(base_info.get('up', 'N/A'))}元")
                        st.info(f"**跌停价**\n{format_price(base_info.get('dp', 'N/A'))}元")
                    
                    with col4:
                        st.info(f"**总股本**\n{format_large_number(base_info.get('tv', 'N/A'))}股")
                        st.info(f"**流通股本**\n{format_large_number(base_info.get('fv', 'N/A'))}股")
                    
                    suspend_status = base_info.get('is', 0)
                    if suspend_status <= 0:
                        st.success(f"✅ 交易状态: 正常交易（{suspend_status == -1 and '今日复牌' or '可正常买卖'}）")
                    else:
                        st.error(f"⚠️ 交易状态: 停牌中（已停牌 {suspend_status} 天）")
                else:
                    st.info("未能获取到完整的股票基础信息")
                
                st.markdown("---")
                
                st.markdown("### 📊 核心交易指标")
                col1, col2, col3, col4 = st.columns(4)
                
                current_price = realtime_data.get('p', 0)
                price_change = realtime_data.get('ud', 0)
                price_change_pct = realtime_data.get('pc', 0)
                volume = realtime_data.get('v', 0)
                
                logger.info("=== 关键指标数据 ===")
                logger.info(f"当前价格: {current_price}")
                logger.info(f"涨跌额: {price_change}")
                logger.info(f"涨跌幅: {price_change_pct}%")
                logger.info(f"成交量: {volume}")
                
                with col1:
                    st.metric(
                        label="💰 当前价格",
                        value=f"¥{format_price(current_price)}" if current_price else "N/A",
                        delta=f"{price_change:+.2f}" if price_change else "N/A"
                    )
                
                with col2:
                    st.metric(
                        label="📊 涨跌幅",
                        value=format_percentage(price_change_pct),
                        delta=format_percentage(price_change_pct)
                    )
                
                with col3:
                    st.metric(
                        label="🔄 成交量",
                        value=format_large_number(volume * 100) if volume else "N/A",
                        help="成交量 (股)"
                    )
                
                with col4:
                    turnover = realtime_data.get('cje', 0)
                    st.metric(
                        label="💵 成交额",
                        value=format_large_number(turnover),
                        help="成交额 (元)"
                    )
                
                st.markdown("---")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("📈 近半年日K线图（仅交易日）")
                    
                    if historical_data and len(historical_data) > 0:
                        logger.info(f"=== 开始处理历史数据，数据量: {len(historical_data)} ===")
                        df = pd.DataFrame(historical_data)
                        df['t'] = pd.to_datetime(df['t'], errors='coerce')
                        df = df.sort_values('t').dropna(subset=['t'])

                        # 过滤无交易的日期（通常API返回的都是交易日数据，这里做双重保障）
                        df = df[df['v'] > 0]
                        
                        logger.info(f"历史数据处理完成，最终交易日数量: {len(df)}")
                        
                        fig = create_candlestick_chart(
                            df, 
                            f"{stock_name} K线图 (近半年，仅交易日)",
                            full_stock_code
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.info(f"📊 共显示 {len(df)} 个交易日的数据")
                    else:
                        logger.warning(f"没有历史K线数据: {full_stock_code}")
                        st.warning("⚠️ 暂无历史K线数据")
                
                with col2:
                    st.subheader("📋 详细交易指标")
                    
                    detailed_metrics = {
                        "开盘价": f"¥{format_price(realtime_data.get('o', 0))}",
                        "最高价": f"¥{format_price(realtime_data.get('h', 0))}",
                        "最低价": f"¥{format_price(realtime_data.get('l', 0))}",
                        "昨收价": f"¥{format_price(realtime_data.get('yc', 0))}",
                        "换手率": format_percentage(realtime_data.get('hs', 0)),
                        "振幅": format_percentage(realtime_data.get('zf', 0)),
                        "量比": f"{realtime_data.get('lb', 0):.2f}",
                        "市盈率": f"{realtime_data.get('pe', 0):.2f}",
                        "市净率": f"{realtime_data.get('sjl', 0):.2f}",
                        "总市值": format_large_number(realtime_data.get('sz', 0)),
                        "流通市值": format_large_number(realtime_data.get('lt', 0)),
                        "60日涨跌幅": format_percentage(realtime_data.get('zdf60', 0)),
                        "年初至今": format_percentage(realtime_data.get('zdfnc', 0)),
                        "五分钟涨跌幅": format_percentage(realtime_data.get('fm', 0)),
                        "涨速": format_percentage(realtime_data.get('zs', 0)),
                    }
                    
                    for label, value in detailed_metrics.items():
                        col_a, col_b = st.columns([1, 1])
                        with col_a:
                            st.write(f"**{label}**")
                        with col_b:
                            st.write(value)
                    
                    update_time = realtime_data.get('t', '')
                    if update_time:
                        st.caption(f"🕐 更新时间: {update_time}")
                
                if historical_data and len(historical_data) > 0:
                    st.markdown("---")
                    st.subheader("📋 最近交易记录")
                    
                    recent_df = pd.DataFrame(historical_data[-10:])
                    if not recent_df.empty:
                        logger.info(f"显示最近交易记录，记录数: {len(recent_df)}")
                        
                        recent_df['日期'] = pd.to_datetime(recent_df['t'], errors='coerce').dt.strftime('%Y-%m-%d')
                        recent_df = recent_df.sort_values('t')
                        
                        recent_df['涨跌幅'] = ((recent_df['c'] - recent_df['c'].shift(1)) / recent_df['c'].shift(1) * 100).round(2)
                        recent_df['涨跌幅'] = recent_df['涨跌幅'].fillna(0)
                        
                        recent_df['开盘'] = recent_df['o'].round(2)
                        recent_df['最高'] = recent_df['h'].round(2)
                        recent_df['最低'] = recent_df['l'].round(2)
                        recent_df['收盘'] = recent_df['c'].round(2)
                        recent_df['成交量'] = recent_df['v'].apply(lambda x: format_large_number(x * 100))
                        recent_df['成交额'] = recent_df.get('a', 0).apply(format_large_number)
                        
                        display_columns = ['日期', '开盘', '最高', '最低', '收盘', '涨跌幅', '成交量', '成交额']
                        
                        st.dataframe(
                            recent_df[display_columns].iloc[::-1],
                            use_container_width=True,
                            hide_index=True
                        )
                
                logger.info(f"=== 股票查询完成: {stock_name} ===")
        
        else:
            st.info("👆 请在左侧输入股票代码进行查询")
            
            st.markdown("""
            ### 🌟 功能特色
            
            - **实时行情**: 获取最新的股票价格和交易数据
            - **基础信息**: 包含上市日期、股本结构、涨跌停价等核心信息
            - **K线图**: 显示近半年的日K线走势图（仅包含交易日）
            - **详细指标**: 包含市盈率、换手率、振幅等关键指标
            - **历史记录**: 查看最近的交易记录
            """)
    
    except Exception as e:
        logger.error(f"主函数执行失败: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        st.error(f"应用程序发生错误: {e}")
    
    finally:
        logger.info("=== 主函数执行结束 ===")

def test_zhitu_api():
    api = ZhituApi(TOKEN)
    stock_code = '000001.SZ'
    base_info = api.get_base_info(stock_code)
    logger.info(f'股票基础信息：\n{base_info}')
    realtime_data = api.get_real_time_data(stock_code)
    logger.info(f'实时交易数据：\n{realtime_data}')
    history_data = api.get_historical_data(stock_code)
    logger.info(f'历史交易数据量：\n{len(history_data)}')


if __name__ == "__main__":
    logger.info("=== 股票查询应用程序启动 ===")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main()
    logger.info("=== 股票查询应用程序结束 ===")