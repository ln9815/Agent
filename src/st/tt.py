import streamlit as st
import requests
import json
import time
import queue
import threading
import logging
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import os
from thx.thx_tool import ThxApi
from typing import Optional, Dict, List, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 常量定义
TOKEN = 'app-rCFXuZN6Bwr4P3c5VDsknOt4'
LOG_DIR = 'logs'
DATA_LOG_PREFIX = 'data_'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_STOCK_CODE = 'HK2018'

# 创建必要的目录
os.makedirs(LOG_DIR, exist_ok=True)

# 设置数据记录器
data_logger = logging.getLogger('StockData')
data_logger.setLevel(logging.INFO)
file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=f'{LOG_DIR}/stock_app.log',
    when='midnight',
    interval=1,
    backupCount=30,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
data_logger.addHandler(file_handler)

# 配置Streamlit页面
st.set_page_config(page_title="投资小秘", layout="wide")

def log_stock_data(stock_code: str, data_type: str, data: dict):
    """记录股票数据"""
    try:
        def convert_timestamps(obj):
            if isinstance(obj, pd.Timestamp):
                return obj.strftime(DATE_FORMAT)
            elif isinstance(obj, dict):
                return {k: convert_timestamps(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_timestamps(item) for item in obj]
            return obj

        serializable_data = convert_timestamps(data)
        
        log_entry = {
            'timestamp': datetime.now().strftime(DATE_FORMAT),
            'stock_code': stock_code,
            'data_type': data_type,
            'data': serializable_data
        }
        
        data_log_path = f'{LOG_DIR}/{DATA_LOG_PREFIX}{datetime.now().strftime("%Y%m%d")}.json'
        with open(data_log_path, 'a', encoding='utf-8') as f:
            json.dump(log_entry, f, ensure_ascii=False)
            f.write('\n')
        
        data_logger.info(f"数据记录 - 股票代码: {stock_code}, 类型: {data_type}")
    except Exception as e:
        data_logger.error(f"数据记录失败: {str(e)}")

def filter_trading_hours(df, is_intraday=False, is_hk=False):
    """过滤非交易时间的数据点"""
    if is_intraday:
        df = df.copy()
        df['time_only'] = df['t'].dt.time
        
        if is_hk:
            trade_time = [('09:30:00', '12:00:00'), ('13:00:00', '16:10:00')]
        else:
            trade_time = [('09:30:00', '11:30:00'), ('13:00:00', '15:00:00')]
        
        conditions = []
        for start, end in trade_time:
            start_time = pd.to_datetime(start).time()
            end_time = pd.to_datetime(end).time()
            conditions.append((df['time_only'] >= start_time) & (df['time_only'] <= end_time))
        
        combined_condition = conditions[0]
        for cond in conditions[1:]:
            combined_condition |= cond
        
        df = df[combined_condition]
        df = df.drop(columns=['time_only'])
    else:
        df = df.dropna(subset=['o', 'h', 'l', 'c'])
    
    return df

def convert_datetime_column(df, column_name):
    """处理日期时间列的转换"""
    if column_name not in df.columns:
        return df, "缺少时间列"
    
    formats = [
        '%Y%m%d', '%Y-%m-%d', '%Y/%m/%d', 
        '%m/%d/%Y', '%d/%m/%Y'
    ]
    
    for fmt in formats:
        try:
            df[column_name] = pd.to_datetime(df[column_name], format=fmt, errors='coerce')
            if not df[column_name].isnull().any():
                return df, None
        except:
            continue
    
    try:
        df[column_name] = pd.to_datetime(df[column_name], errors='coerce')
    except Exception as e:
        return df, f"时间转换失败: {str(e)}"
    
    if df[column_name].isnull().any():
        failed_values = df.loc[df[column_name].isnull(), column_name].unique()
        failed_sample = failed_values[0] if len(failed_values) > 0 else "N/A"
        return df, f"无法转换的时间值: {failed_sample} (样本)"
    
    return df, None

def create_candlestick_chart(df: pd.DataFrame, title: str, stock_code: str, is_intraday=False):
    """创建股票图表"""
    is_hk = stock_code.startswith('HK') or stock_code.startswith('hk')
    currency_unit = 'HKD' if is_hk else 'CNY'
    df = filter_trading_hours(df, is_intraday=is_intraday, is_hk=is_hk)
    
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            xaxis_title='时间' if is_intraday else '日期',
            yaxis_title=f'价格 ({currency_unit})',
            annotations=[dict(
                text="无可用数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20)
            )]
        )
        return fig
    
    try:
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3]
        )
        
        if is_intraday:
            if 'v' in df.columns and 'c' in df.columns:
                df['cum_amount'] = (df['c'] * df['v']).cumsum()
                df['cum_volume'] = df['v'].cumsum()
                df['avg_price'] = df['cum_amount'] / df['cum_volume']
            else:
                df['avg_price'] = df['c'].rolling(window=5, min_periods=1).mean()
            
            price_trace = go.Scatter(
                x=df['t'],
                y=df['c'],
                mode='lines',
                name='价格',
                line=dict(color='blue', width=2)
            )
            fig.add_trace(price_trace, row=1, col=1)
            
            avg_trace = go.Scatter(
                x=df['t'],
                y=df['avg_price'],
                mode='lines',
                name='均价',
                line=dict(color='orange', width=2, dash='dash')
            )
            fig.add_trace(avg_trace, row=1, col=1)
            
            if 'prev_close' in df.columns and not df['prev_close'].isnull().all():
                prev_close = df['prev_close'].iloc[0]
                fig.add_hline(
                    y=prev_close, 
                    line=dict(color='gray', width=1, dash='dash'),
                    annotation_text=f"昨收: {prev_close:.2f}",
                    row=1, col=1
                )
        else:
            candle_trace = go.Candlestick(
                x=df['t'],
                open=df['o'],
                high=df['h'],
                low=df['l'],
                close=df['c'],
                increasing_line_color='red',
                decreasing_line_color='green',
                name='K线'
            )
            fig.add_trace(candle_trace, row=1, col=1)
        
        if 'v' in df.columns:
            colors = ['red'] * len(df)
            for i in range(len(df)):
                if i == 0:
                    if 'prev_close' in df.columns and not pd.isnull(df['prev_close'].iloc[0]):
                        if df['c'].iloc[i] < df['prev_close'].iloc[0]:
                            colors[i] = 'green'
                else:
                    if df['c'].iloc[i] < df['c'].iloc[i-1]:
                        colors[i] = 'green'
            
            volume_bars = go.Bar(
                x=df['t'],
                y=df['v'],
                name='成交量',
                marker_color=colors,
                showlegend=False
            )
            fig.add_trace(volume_bars, row=2, col=1)
            has_volume = True
        else:
            has_volume = False
        
        if not is_intraday and len(df) > 5 and 'c' in df.columns:
            try:
                df['MA5'] = df['c'].rolling(window=5, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=df['t'],
                    y=df['MA5'],
                    mode='lines',
                    name='MA5',
                    line=dict(color='orange', width=2)
                ), row=1, col=1)
                
                if len(df) > 20:
                    df['MA20'] = df['c'].rolling(window=20, min_periods=1).mean()
                    fig.add_trace(go.Scatter(
                        x=df['t'],
                        y=df['MA20'],
                        mode='lines',
                        name='MA20',
                        line=dict(color='purple', width=2)
                    ), row=1, col=1)
            except Exception as e:
                data_logger.warning(f"添加移动平均线失败: {str(e)}")
        
        layout_params = {
            'title': title,
            'height': 700,
            'legend': dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        }
        
        if is_intraday:
            if is_hk:
                rangebreaks = [
                    dict(bounds=[12, 13], pattern="hour"),
                    dict(bounds=[16, 9.5], pattern="hour"),
                    dict(bounds=["sat", "mon"])
                ]
            else:
                rangebreaks = [
                    dict(bounds=[11.5, 13], pattern="hour"),
                    dict(bounds=[15, 9.5], pattern="hour"),
                    dict(bounds=["sat", "mon"])
                ]
            
            layout_params.update({
                'xaxis': {
                    'type': 'date',
                    'tickformat': '%H:%M',
                    'rangebreaks': rangebreaks,
                    'rangeslider': dict(visible=False)
                },
                'xaxis2': {
                    'type': 'date',
                    'tickformat': '%H:%M',
                    'rangebreaks': rangebreaks
                }
            })
        else:
            layout_params.update({
                'xaxis': {
                    'type': 'date',
                    'tickformat': '%Y-%m-%d',
                    'rangeslider': dict(visible=False)
                },
                'xaxis2': {
                    'type': 'date',
                    'tickformat': '%Y-%m-%d'
                }
            })
        
        fig.update_layout(**layout_params)
        fig.update_yaxes(title_text=f"价格 ({currency_unit})", row=1, col=1)
        
        if has_volume:
            fig.update_yaxes(title_text="成交量", row=2, col=1)
        else:
            fig.update_layout(row_heights=[1.0, 0])
        
        return fig
            
    except Exception as e:
        data_logger.error(f"创建图表失败: {str(e)}", exc_info=True)
        fig = go.Figure(data=[go.Scatter(
            x=df['t'],
            y=df['c'],
            mode='lines+markers',
            name='收盘价',
            line=dict(color='blue', width=2))
        ])
        fig.update_layout(title=title)
        return fig

def display_stock_info(stock_code: str) -> Optional[Dict[str, Any]]:
    """显示股票基本信息"""
    is_hk = stock_code.startswith('HK') or stock_code.startswith('hk')
    currency_unit = 'HKD' if is_hk else 'CNY'
    try:
        api = ThxApi(stock_code)
        info = api.basic_info()
        
        log_stock_data(stock_code, "basic_info", info)
        
        if not info:
            data_logger.warning(f"获取到空的基本信息 - 股票代码: {stock_code}")
            st.warning("未获取到股票基本信息")
            return None
        
        st.subheader(f"{info.get('股票名称', 'N/A')} ({info.get('股票编码', 'N/A')})")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("当前价格", f"{info.get('收盘', 'N/A')} {currency_unit}")
            st.metric("涨跌幅", f"{info.get('涨幅(%)', 'N/A')}%", 
                      delta=f"{info.get('涨幅', 'N/A')}", delta_color="inverse")
            st.metric("成交量", f"{float(info.get('成交量', 'N/A'))/1000000:.2f}万手")
        
        with col2:
            st.metric("昨收", f"{info.get('昨收', 'N/A')} {currency_unit}")
            st.metric("最高价/最低价", 
                     f"{info.get('最高', 'N/A')}/{info.get('最低', 'N/A')} {currency_unit}")
            st.metric("成交额", f"{float(info.get('成交额', 'N/A'))/100000000:.2f}亿 {currency_unit}")
        
        with col3:
            st.metric("开盘", f"{info.get('开盘', 'N/A')} {currency_unit}")
            st.metric("市盈率", f"{info.get('市盈率', 'N/A')}")
            st.metric("市盈率(动)", f"{info.get('市盈率(动)', 'N/A')}")
        
        with col4:
            st.metric("振幅", f"{info.get('振幅', 'N/A')}%")
            st.metric("换手率", f"{info.get('换手率', 'N/A')}%")
            st.metric("市净率", f"{info.get('市净率', 'N/A')}")
        
        return info
    except Exception as e:
        data_logger.error(f"获取股票信息失败 - 股票代码: {stock_code}, 错误: {str(e)}")
        st.error(f"获取股票基本信息失败: {str(e)}")
        return None

def display_chart(stock_code: str, chart_type: str = 'realtime'):
    """显示K线图（实时或历史）"""
    try:
        data_logger.info(f"开始获取{chart_type}数据，股票代码: {stock_code}")
        api = ThxApi(stock_code)
        
        if chart_type == 'realtime':
            data = api.last(period='1m')
            data_type = "realtime_data"
            title = f'{stock_code} 实时K线图 (5分钟)'
        else:
            try:
                data = api.history(period='d', count=90)
                data_type = "history_data"
                title = f'{stock_code} 历史K线图 (90天)'
            except Exception as api_error:
                data_logger.warning(f"使用默认参数获取历史数据失败，尝试其他方法: {str(api_error)}")
                data = api.history(period='1d', count=90)
                data_type = "history_data"
                title = f'{stock_code} 历史K线图 (90天)'
        
        if not data:
            data_logger.error(f"获取{chart_type}数据为空 - 股票代码: {stock_code}")
            st.error(f"获取{chart_type}数据失败: 返回数据为空")
            return
            
        def convert_numeric_fields(obj):
            if isinstance(obj, dict):
                return {k: convert_numeric_fields(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numeric_fields(item) for item in obj]
            elif isinstance(obj, str):
                clean_str = obj.replace(',', '').replace(' ', '')
                if clean_str.replace('.', '', 1).replace('-', '', 1).isdigit():
                    return float(clean_str)
            return obj

        processed_data = convert_numeric_fields(data)
        log_stock_data(stock_code, data_type, processed_data)
        
        df = pd.DataFrame(processed_data)
        
        required_columns = ['t', 'o', 'h', 'l', 'c']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            data_logger.error(f"数据缺失必要列: {missing_columns}")
            st.error(f"数据格式错误: 缺少必要的列 {', '.join(missing_columns)}")
            return
            
        try:
            df['t'] = pd.to_datetime(df['t'])
        except Exception as e:
            data_logger.error(f"时间转换失败: {str(e)}")
            st.error("时间数据处理失败")
            return
            
        numeric_cols = ['o', 'h', 'l', 'c']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if df[numeric_cols].isnull().values.any():
            data_logger.warning(f"数据包含NaN值，将尝试填充")
            df[numeric_cols] = df[numeric_cols].fillna(method='ffill')
        
        df, error = convert_datetime_column(df, 't')
        if error:
            data_logger.error(error)
            st.error("时间数据处理失败")
            return
            
        if not pd.api.types.is_datetime64_any_dtype(df['t']):
            data_logger.error("时间列转换后仍不是datetime类型")
            st.error("时间数据处理失败")
            return
        
        try:
            fig = create_candlestick_chart(
                df, 
                title,
                stock_code,
                is_intraday=(chart_type == 'realtime')
            )
            st.plotly_chart(fig, use_container_width=True)
            data_logger.info(f"成功显示{chart_type}图表")
        except Exception as e:
            data_logger.error(f"绘制图表失败: {str(e)}")
            st.error(f"绘制{chart_type}图表失败")
            
    except Exception as e:
        data_logger.error(f"获取{chart_type}数据失败 - 股票代码: {stock_code}", exc_info=True)
        st.error(f"获取{chart_type}数据失败: {str(e)}")

def display_news(stock_code: str):
    """显示股票新闻"""
    try:
        if not stock_code or not isinstance(stock_code, str):
            data_logger.warning(f"无效的股票代码: {stock_code}")
            st.warning("请输入有效的股票代码")
            return

        data_logger.info(f"开始获取新闻数据，股票代码: {stock_code}")
        
        api = ThxApi(stock_code)
        news_data = api.news(count=10)
        
        if not news_data:
            data_logger.warning(f"获取到空的新闻数据 - 股票代码: {stock_code}")
            st.warning("暂无相关新闻")
            return
            
        if not isinstance(news_data, list):
            data_logger.error(f"新闻数据格式不正确，期望列表，得到: {type(news_data)}")
            st.error("新闻数据格式错误")
            return

        processed_news = []
        for news_item in news_data:
            try:
                if not isinstance(news_item, dict):
                    continue
                processed_item = {
                    'date': str(news_item.get('date', '无日期')),
                    'title': str(news_item.get('title', '无标题')),
                    'summary': str(news_item.get('summary', '无内容摘要')),
                    'href': str(news_item.get('href', '#')),
                }
                processed_news.append(processed_item)
            except Exception as e:
                data_logger.error(f"处理单条新闻失败: {str(e)}", exc_info=True)
        
        log_stock_data(stock_code, "news_data", processed_news)
        
        st.subheader("最新新闻")
        for news in processed_news:
            try:
                with st.expander(f"{news['date']} - {news['title']}"):
                    st.write(news['summary'])
                    if news['href'] and news['href'] != '#':
                        st.markdown(f"[阅读全文]({news['href']})")
            except Exception as e:
                data_logger.error(f"显示单条新闻失败: {str(e)}", exc_info=True)
                continue
                
        data_logger.info(f"成功显示 {len(processed_news)} 条新闻")
        
    except Exception as e:
        data_logger.error(f"获取新闻失败 - 股票代码: {stock_code}", exc_info=True)
        st.error(f"获取新闻失败: {str(e)}")

class WorkflowRunner:
    """执行股票分析工作流"""
    def __init__(self, stock_code):
        self.stock_code = stock_code
        self.text_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.finished = False
        self.error = None

    def run(self):
        """在工作线程中执行工作流"""
        try:
            workflow_url = "http://szvkt.top:8880/v1/workflows/run"
            headers = {
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }

            data = {
                "inputs": {
                    "stock_code": self.stock_code
                },
                "response_mode": "streaming",
                "user": "streamlit_user"
            }

            full_text = ""
            with requests.post(
                workflow_url,
                headers=headers,
                json=data,
                stream=True,
                timeout=300
            ) as response:
                
                if response.status_code != 200:
                    self.error = f"❌ 请求失败，状态码: {response.status_code}\n响应内容: {response.text}"
                    return
                
                buffer = ""
                for byte_chunk in response.iter_content(chunk_size=1024):
                    if byte_chunk:
                        chunk = byte_chunk.decode('utf-8')
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_end = buffer.index("\n\n")
                            event_data = buffer[:event_end]
                            buffer = buffer[event_end + 2:]
                            
                            result = self.process_event_data(event_data)
                            if result:
                                event_type, text, log = result
                                
                                if event_type == "text_chunk":
                                    full_text += text
                                    self.text_queue.put(full_text)
                                
                                if log:
                                    self.log_queue.put(log)
            
            self.text_queue.put(full_text)
            self.log_queue.put("🏁 工作流执行完成")
        
        except requests.exceptions.RequestException as e:
            self.error = f"❌ 请求失败: {str(e)}"
        except Exception as e:
            self.error = f"❌ 未知错误: {str(e)}"
        finally:
            self.finished = True

    def process_event_data(self, event_data):
        """处理单个SSE事件数据"""
        try:
            event_lines = event_data.split('\n')
            event_dict = {}
            
            for line in event_lines:
                if line.startswith('data:'):
                    json_str = line[5:].strip()
                    if json_str:
                        event_dict = json.loads(json_str)
            
            if not event_dict:
                return None
            
            event_type = event_dict.get('event')
            text_output = ""
            log_output = ""
            
            if event_type == 'workflow_started':
                log_output = f"⏱️ [工作流开始] ID: {event_dict['data']['id']}\n任务ID: {event_dict['task_id']}"
            
            elif event_type == 'node_started':
                log_output = f"🚀 [节点开始] {event_dict['data']['title']} (类型: {event_dict['data']['node_type']})"
            
            elif event_type == 'text_chunk':
                text_output = event_dict['data']['text']
            
            elif event_type == 'node_finished':
                node_data = event_dict['data']
                status = node_data['status']
                if status == 'failed':
                    log_output = f"❌ [节点失败] {node_data['node_id']} - 错误: {node_data.get('error', '未知错误')}"
                else:
                    log_output = f"✅ [节点完成] {node_data['node_id']} - 状态: {status.upper()}"
            
            elif event_type == 'workflow_finished':
                wf_data = event_dict['data']
                log_output = f"🏁 [工作流完成] 状态: {wf_data['status'].upper()}\n耗时: {wf_data['elapsed_time']}秒"
            
            return event_type, text_output, log_output
        
        except Exception as e:
            logger.error(f"事件处理错误: {str(e)}")
            return None

def show_stock_analysis(stock_code: str):
    """显示股票分析工作流页面"""
    st.subheader("📈 股票智能分析")
    st.markdown("""
    使用此工具分析股票数据。输入股票代码，系统将执行分析工作流并实时显示结果。
    """)
    
    # stock_code = st.text_input("股票代码", "HK2018", key="analysis_input", 
    #                           help="请输入要分析的股票代码，例如：HK2018")
    
    status_area = st.empty()
    result_area = st.empty()
    log_area = st.empty()
    
    if 'runner' not in st.session_state:
        st.session_state.runner = None
    if 'analysis_started' not in st.session_state:
        st.session_state.analysis_started = False
    
    # if st.button("开始分析", type="primary", key="analysis_btn") and not st.session_state.analysis_started:
    #     st.session_state.analysis_started = True
    #     st.session_state.runner = WorkflowRunner(stock_code)
    #     threading.Thread(target=st.session_state.runner.run, daemon=True).start()
    
    if st.session_state.analysis_started and st.session_state.runner:
        status_area.info("🚀 工作流执行中，请稍候...")
        result_placeholder = st.empty()
        log_placeholder = st.empty()
        
        full_text = ""
        full_log = ""
        
        while not st.session_state.runner.finished or not st.session_state.runner.text_queue.empty() or not st.session_state.runner.log_queue.empty():
            try:
                while not st.session_state.runner.text_queue.empty():
                    full_text = st.session_state.runner.text_queue.get()
                    result_placeholder.markdown(f"### 分析结果\n{full_text}")
                
                while not st.session_state.runner.log_queue.empty():
                    log_entry = st.session_state.runner.log_queue.get()
                    full_log += log_entry + "\n\n"
                    log_placeholder.text_area("工作流日志", full_log, height=300)
                
                time.sleep(0.1)
            except queue.Empty:
                break
        
        if st.session_state.runner.finished:
            if st.session_state.runner.error:
                status_area.error(st.session_state.runner.error)
            else:
                status_area.success("✅ 分析完成！")
                result_placeholder.markdown(f"### 最终分析结果\n{full_text}")
                
                st.download_button(
                    label="下载分析报告",
                    data=full_text.encode('utf-8'),
                    file_name=f"{stock_code}_分析报告.txt",
                    mime="text/plain"
                )
            
            st.session_state.analysis_started = False

def show_stock_data(stock_code: str):
    """显示股票数据页面"""
    st.subheader("📊 股票数据分析")
    # stock_code = st.text_input("请输入股票代码 (例如: 600519,HK2018)", 
    #                           DEFAULT_STOCK_CODE, key="stock_input").strip()
    
    if not stock_code:
        st.warning("请输入有效的股票代码")
        return
        
    data_logger.info(f"用户查询股票: {stock_code}")
    
    info = display_stock_info(stock_code)
    if not info:
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        display_chart(stock_code, 'realtime')
    
    with col2:
        display_chart(stock_code, 'history')
    
    display_news(stock_code)

def main():
    """主应用入口"""
    st.title("📊 投资小秘")
    
    
    
    # 侧边栏说明
    stock_code = st.sidebar.text_input("股票代码", "HK2018", key="analysis_input", 
                              help="请输入要分析的股票代码，例如：HK2018")
    
    if st.sidebar.button("开始分析", type="primary", key="analysis_btn") and not st.session_state.analysis_started:
        st.session_state.analysis_started = True
        st.session_state.runner = WorkflowRunner(stock_code)
        threading.Thread(target=st.session_state.runner.run, daemon=True).start()

    st.sidebar.title("使用说明")
    st.sidebar.markdown("""
    ### 功能说明
    1. **股票数据分析**（上方）：
       - 查看实时行情和历史K线图
       - 浏览最新相关新闻
    2. **股票智能分析**（下方）：
       - 使用AI工作流生成深度分析报告
       - 实时显示分析过程和结果
       - 支持下载完整分析报告

    ### 注意事项
    - 股票智能分析可能需要1-3分钟，请耐心等待
    - 确保输入有效的股票代码（如：HK2018, 600519）
    - 分析过程中请不要关闭页面
    """)

    # 显示股票数据分析部分
    show_stock_data(stock_code)
    
    # 添加分隔线
    st.divider()
    
    # 显示股票智能分析部分
    show_stock_analysis(stock_code)

if __name__ == "__main__":
    main()