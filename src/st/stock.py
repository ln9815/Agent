import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots  # 添加这行导入
import numpy as np  # 添加这行导入
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import json
from thx.thx_tool import ThxApi
from typing import Optional, Dict, List, Any

# 常量定义
LOG_DIR = 'logs'
DATA_LOG_PREFIX = 'data_'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_STOCK_CODE = 'HK2018'


def filter_trading_hours(df, is_intraday=False, is_hk=False):
    """过滤非交易时间的数据点"""
    if is_intraday:
        # 对于日内数据，只保留交易时间段 
        df = df.copy()
        df['time_only'] = df['t'].dt.time
        
        # 根据市场类型定义交易时间段
        if is_hk:
            # 港股交易时间: 9:30-12:00, 13:00-16:00
            trade_time = [('09:30:00', '12:00:00'), ('13:00:00', '16:10:00')]
        else:
            # A股交易时间: 9:30-11:30, 13:00-15:00
            trade_time = [('09:30:00', '11:30:00'), ('13:00:00', '15:00:00')]
        
        # 创建过滤条件
        conditions = []
        for start, end in trade_time:
            start_time = pd.to_datetime(start).time()
            end_time = pd.to_datetime(end).time()
            conditions.append((df['time_only'] >= start_time) & (df['time_only'] <= end_time))
        
        # 合并所有条件
        combined_condition = conditions[0]
        for cond in conditions[1:]:
            combined_condition |= cond
        
        # 过滤数据
        df = df[combined_condition]
        df = df.drop(columns=['time_only'])
    else:
        # 对于日线数据，确保只保留交易日
        df = df.dropna(subset=['o', 'h', 'l', 'c'])
    
    return df

def convert_datetime_column(df, column_name):
    """专门处理日期时间列的转换"""
    if column_name not in df.columns:
        return df, "缺少时间列"
    
    # 尝试多种格式转换
    formats = [
        '%Y%m%d',    # 20250319
        '%Y-%m-%d',  # 2025-03-19
        '%Y/%m/%d',  # 2025/03/19
        '%m/%d/%Y',  # 03/19/2025 (美国格式)
        '%d/%m/%Y'   # 19/03/2025 (欧洲格式)
    ]
    
    for fmt in formats:
        try:
            df[column_name] = pd.to_datetime(df[column_name], format=fmt, errors='coerce')
            # 检查是否所有值都转换成功
            if not df[column_name].isnull().any():
                return df, None
        except:
            continue
    
    # 如果以上格式都不行，尝试通用转换
    try:
        df[column_name] = pd.to_datetime(df[column_name], errors='coerce')
    except Exception as e:
        return df, f"时间转换失败: {str(e)}"
    
    # 检查转换结果
    if df[column_name].isnull().any():
        failed_values = df.loc[df[column_name].isnull(), column_name].unique()
        failed_sample = failed_values[0] if len(failed_values) > 0 else "N/A"
        return df, f"无法转换的时间值: {failed_sample} (样本)"
    
    return df, None

class StockApp:
    def __init__(self):
        """初始化应用"""
        self._setup_directories()
        self.logger = self._setup_logger()
        self._configure_page()
        
    def _setup_directories(self):
        """创建必要的目录"""
        os.makedirs(LOG_DIR, exist_ok=True)
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('StockApp')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        
        file_handler = TimedRotatingFileHandler(
            filename=f'{LOG_DIR}/stock_app.log',
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def _configure_page(self):
        """配置Streamlit页面"""
        st.set_page_config(page_title="投资小秘", layout="wide")
        # st.title("投资小秘")
    
    def log_stock_data(self, stock_code: str, data_type: str, data: Dict[str, Any]):
        """记录股票数据"""
        try:
            # 转换数据中的 Timestamp 对象为字符串
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
            
            # 记录详细数据到单独的JSON文件
            data_log_path = f'{LOG_DIR}/{DATA_LOG_PREFIX}{datetime.now().strftime("%Y%m%d")}.json'
            with open(data_log_path, 'a', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False)
                f.write('\n')
            
            self.logger.info(f"数据记录 - 股票代码: {stock_code}, 类型: {data_type}")
        except Exception as e:
            self.logger.error(f"数据记录失败: {str(e)}")
    
    def _create_candlestick_chart(self, df: pd.DataFrame, title: str, stock_code: str, is_intraday=False) -> go.Figure:
        """创建图表，实时图表使用分时线（带当日均线），日K线使用蜡烛图，并添加成交量副图"""
        # 根据股票代码判断市场类型
        is_hk = stock_code.startswith('HK') or stock_code.startswith('hk')
        currency_unit = 'HKD' if is_hk else 'CNY'
        
        # 过滤非交易时间数据
        df = filter_trading_hours(df, is_intraday=is_intraday, is_hk=is_hk)
        
        if df.empty:
            # 返回一个友好的空图表提示
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
            # 创建带有副图的图表（适用于所有图表类型）
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3]  # 价格图占70%，成交量占30%
            )
            
            # 添加价格图表（实时使用分时线，日K使用蜡烛图）
            if is_intraday:
                # 计算当日均价（分时均线）
                if 'v' in df.columns and 'c' in df.columns:
                    # 计算加权平均价格（成交额/成交量）
                    df['cum_amount'] = (df['c'] * df['v']).cumsum()
                    df['cum_volume'] = df['v'].cumsum()
                    df['avg_price'] = df['cum_amount'] / df['cum_volume']
                else:
                    # 使用简单移动平均作为备选
                    df['avg_price'] = df['c'].rolling(window=5, min_periods=1).mean()
                
                # 实时图表使用分时线（收盘价折线）
                price_trace = go.Scatter(
                    x=df['t'],
                    y=df['c'],
                    mode='lines',
                    name='价格',
                    line=dict(color='blue', width=2)
                )
                fig.add_trace(price_trace, row=1, col=1)
                
                # 添加分时均线
                avg_trace = go.Scatter(
                    x=df['t'],
                    y=df['avg_price'],
                    mode='lines',
                    name='均价',
                    line=dict(color='orange', width=2, dash='dash')
                )
                fig.add_trace(avg_trace, row=1, col=1)
                
                # 添加零轴参考线（昨日收盘价）
                if 'prev_close' in df.columns and not df['prev_close'].isnull().all():
                    prev_close = df['prev_close'].iloc[0]
                    fig.add_hline(
                        y=prev_close, 
                        line=dict(color='gray', width=1, dash='dash'),
                        annotation_text=f"昨收: {prev_close:.2f}",
                        row=1, col=1
                    )
            else:
                # 日K线图使用蜡烛图
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
            
            # 添加成交量到副图（如果有成交量数据）
            if 'v' in df.columns:
                # 根据涨跌设置颜色（红涨绿跌）
                if is_intraday:
                    # 分时图：使用当前价格与前一笔比较判断涨跌
                    # 第一根用当前价格与昨日收盘价比较
                    colors = ['red'] * len(df)  # 默认红色
                    for i in range(len(df)):
                        if i == 0:
                            if 'prev_close' in df.columns and not pd.isnull(df['prev_close'].iloc[0]):
                                if df['c'].iloc[i] < df['prev_close'].iloc[0]:
                                    colors[i] = 'green'
                        else:
                            if df['c'].iloc[i] < df['c'].iloc[i-1]:
                                colors[i] = 'green'
                else:
                    # 日K线：使用收盘价与开盘价比较
                    colors = np.where(df['c'] >= df['o'], 'red', 'green')
                
                # 创建成交量柱状图
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
            
            # 添加移动平均线到日K线图
            if not is_intraday and len(df) > 5 and 'c' in df.columns:
                try:
                    # 5周期移动平均
                    df['MA5'] = df['c'].rolling(window=5, min_periods=1).mean()
                    fig.add_trace(go.Scatter(
                        x=df['t'],
                        y=df['MA5'],
                        mode='lines',
                        name='MA5',
                        line=dict(color='orange', width=2)
                    ), row=1, col=1)
                    
                    # 20周期移动平均（仅当有足够数据点时）
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
                    self.logger.warning(f"添加移动平均线失败: {str(e)}")
            
            # 设置布局
            layout_params = {
                'title': title,
                'height': 700,  # 固定高度以容纳副图
                'legend': dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='right',
                    x=1
                )
            }
            
            # 对于日内图表（分时线），设置更紧凑的时间轴
            if is_intraday:
                # 定义市场交易时间段
                if is_hk:
                    # 港股交易时间: 9:30-12:00, 13:00-16:00
                    rangebreaks = [
                        # 隐藏中午休市时间 (12:00-13:00)
                        dict(bounds=[12, 13], pattern="hour"),
                        # 隐藏夜间休市时间 (16:00-次日9:30)
                        dict(bounds=[16, 9.5], pattern="hour"),
                        # 隐藏周末
                        dict(bounds=["sat", "mon"])
                    ]
                else:
                    # A股交易时间: 9:30-11:30, 13:00-15:00
                    rangebreaks = [
                        # 隐藏中午休市时间 (11:30-13:00)
                        dict(bounds=[11.5, 13], pattern="hour"),
                        # 隐藏夜间休市时间 (15:00-次日9:30)
                        dict(bounds=[15, 9.5], pattern="hour"),
                        # 隐藏周末
                        dict(bounds=["sat", "mon"])
                    ]
                
                # 应用范围限制到两个X轴
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
                # 对于日线图表，设置日期格式
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
            
            # 如果有成交量数据，设置成交量轴标题
            if has_volume:
                fig.update_yaxes(title_text="成交量", row=2, col=1)
            else:
                # 如果没有成交量数据，隐藏副图
                fig.update_layout(row_heights=[1.0, 0])  # 成交量区域高度为0
            
            return fig
            
        except Exception as e:
            self.logger.error(f"创建图表失败: {str(e)}", exc_info=True)
            # 创建简单折线图作为后备
            fig = go.Figure(data=[go.Scatter(
                x=df['t'],
                y=df['c'],
                mode='lines+markers',
                name='收盘价',
                line=dict(color='blue', width=2)
            )])
            fig.update_layout(title=title)
            return fig
    
    def display_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """显示股票基本信息"""
        is_hk = stock_code.startswith('HK') or stock_code.startswith('hk')
        currency_unit = 'HKD' if is_hk else 'CNY'
        try:
            api = ThxApi(stock_code)
            info = api.basic_info()
            
            self.log_stock_data(stock_code, "basic_info", info)
            
            if not info:
                self.logger.warning(f"获取到空的基本信息 - 股票代码: {stock_code}")
                st.warning("未获取到股票基本信息")
                return None
            
            st.subheader(f"{info.get('股票名称', 'N/A')} ({info.get('股票编码', 'N/A')})")
            
            col1, col2,col3,col4 = st.columns(4)
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
            self.logger.error(f"获取股票信息失败 - 股票代码: {stock_code}, 错误: {str(e)}")
            st.error(f"获取股票基本信息失败: {str(e)}")
            return None
    
    def display_chart(self, stock_code: str, chart_type: str = 'realtime'):
        """显示K线图（实时或历史）"""
        try:
            self.logger.info(f"开始获取{chart_type}数据，股票代码: {stock_code}")
            api = ThxApi(stock_code)
            
            if chart_type == 'realtime':
                data = api.last(period='1m')
                data_type = "realtime_data"
                title = f'{stock_code} 实时K线图 (5分钟)'
            else:
                # 尝试多种获取历史数据的方法
                try:
                    data = api.history(period='d', count=90)
                    data_type = "history_data"
                    title = f'{stock_code} 历史K线图 (90天)'
                except Exception as api_error:
                    self.logger.warning(f"使用默认参数获取历史数据失败，尝试其他方法: {str(api_error)}")
                    # 尝试不同的参数组合
                    data = api.history(period='1d', count=90)  # 尝试数字参数
                    data_type = "history_data"
                    title = f'{stock_code} 历史K线图 (90天)'
            
            if not data:
                self.logger.error(f"获取{chart_type}数据为空 - 股票代码: {stock_code}")
                st.error(f"获取{chart_type}数据失败: 返回数据为空")
                return
                
            self.logger.debug(f"原始{chart_type}数据: {data}")  # 记录原始数据用于调试
            
            # 转换数据中的字符串数字为浮点数
            def convert_numeric_fields(obj):
                if isinstance(obj, dict):
                    return {k: convert_numeric_fields(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numeric_fields(item) for item in obj]
                elif isinstance(obj, str):
                    # 处理可能包含逗号的数字字符串
                    clean_str = obj.replace(',', '').replace(' ', '')
                    if clean_str.replace('.', '', 1).replace('-', '', 1).isdigit():
                        return float(clean_str)
                return obj

            processed_data = convert_numeric_fields(data)
            self.log_stock_data(stock_code, data_type, processed_data)
            
            # 创建DataFrame
            df = pd.DataFrame(processed_data)
            self.logger.debug(f"转换后的DataFrame: \n{df.head()}")
            
            # 检查必要的列是否存在
            required_columns = ['t', 'o', 'h', 'l', 'c']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"数据缺失必要列: {missing_columns}")
                st.error(f"数据格式错误: 缺少必要的列 {', '.join(missing_columns)}")
                return
                
            # 转换时间列
            try:
                df['t'] = pd.to_datetime(df['t'])
            except Exception as e:
                self.logger.error(f"时间转换失败: {str(e)}")
                st.error("时间数据处理失败")
                return
                
            # 确保所有数值列都是数字类型
            numeric_cols = ['o', 'h', 'l', 'c']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 检查是否有NaN值
            if df[numeric_cols].isnull().values.any():
                self.logger.warning(f"数据包含NaN值，将尝试填充")
                df[numeric_cols] = df[numeric_cols].fillna(method='ffill')
            
            # st.write(f"### 原始数据预览 ({chart_type})")
            # st.json(data[-10:])  # 显示前3条原始数据

            # st.write(f"### 处理后的DataFrame ({chart_type})")
            # st.dataframe(df.tail(10))
            
            # 转换时间列
            df, error = convert_datetime_column(df, 't')
            if error:
                self.logger.error(error)
                st.error("时间数据处理失败")
                return
                
            # 确保时间列是datetime类型
            if not pd.api.types.is_datetime64_any_dtype(df['t']):
                self.logger.error("时间列转换后仍不是datetime类型")
                st.error("时间数据处理失败")
                return
            
            # 绘制图表
            try:
                fig = self._create_candlestick_chart(
                    df, 
                    title,
                    stock_code,  # 传递股票代码
                    is_intraday=(chart_type == 'realtime')
                )
                st.plotly_chart(fig, use_container_width=True)
                self.logger.info(f"成功显示{chart_type}图表")
            except Exception as e:
                self.logger.error(f"绘制图表失败: {str(e)}")
                st.error(f"绘制{chart_type}图表失败")
                
        except Exception as e:
            self.logger.error(f"获取{chart_type}数据失败 - 股票代码: {stock_code}", exc_info=True)
            st.error(f"获取{chart_type}数据失败: {str(e)}")
    
    def display_news(self, stock_code: str):
        """显示股票新闻，添加更健壮的错误处理和链接支持"""
        try:
            if not stock_code or not isinstance(stock_code, str):
                self.logger.warning(f"无效的股票代码: {stock_code}")
                st.warning("请输入有效的股票代码")
                return

            self.logger.info(f"开始获取新闻数据，股票代码: {stock_code}")
            
            api = ThxApi(stock_code)
            news_data = api.news(count=10)  # 假设API返回一个新闻列表
            
            if not news_data:
                self.logger.warning(f"获取到空的新闻数据 - 股票代码: {stock_code}")
                st.warning("暂无相关新闻")
                return
                
            if not isinstance(news_data, list):
                self.logger.error(f"新闻数据格式不正确，期望列表，得到: {type(news_data)}")
                st.error("新闻数据格式错误")
                return

            # 记录新闻数据（先处理确保可序列化）
            processed_news = []
            for news_item in news_data:
                try:
                    if not isinstance(news_item, dict):
                        continue
                    processed_item = {
                        'date': str(news_item.get('date', '无日期')),
                        'title': str(news_item.get('title', '无标题')),
                        'summary': str(news_item.get('summary', '无内容摘要')),
                        'href': str(news_item.get('href', '#')),  # 添加链接字段，默认为 '#'
                    }
                    processed_news.append(processed_item)
                except Exception as e:
                    self.logger.error(f"处理单条新闻失败: {str(e)}", exc_info=True)
            
            self.log_stock_data(stock_code, "news_data", processed_news)
            
            # 显示新闻
            st.subheader("最新新闻")
            for news in processed_news:
                try:
                    with st.expander(f"{news['date']} - {news['title']}"):
                        st.write(news['summary'])
                        if news['href'] and news['href'] != '#':
                            # 添加可点击的链接
                            st.markdown(f"[阅读全文]({news['href']})")
                except Exception as e:
                    self.logger.error(f"显示单条新闻失败: {str(e)}", exc_info=True)
                    continue
                    
            self.logger.info(f"成功显示 {len(processed_news)} 条新闻")
            
        except Exception as e:
            self.logger.error(f"获取新闻失败 - 股票代码: {stock_code}", exc_info=True)
            st.error(f"获取新闻失败: {str(e)}")
    
    def run(self):
        """运行应用"""
        stock_code = st.text_input("请输入股票代码 (例如: 600519,HK2018)", DEFAULT_STOCK_CODE).strip()
        
        if not stock_code:
            st.warning("请输入有效的股票代码")
            return
            
        self.logger.info(f"用户查询股票: {stock_code}")
        
        # 显示基本信息
        info = self.display_stock_info(stock_code)
        if not info:
            return
            
        # 分栏显示图表
        col1, col2 = st.columns(2)
        
        with col1:
            self.display_chart(stock_code, 'realtime')
        
        with col2:
            self.display_chart(stock_code, 'history')
        
        # 显示新闻
        self.display_news(stock_code)

def main():
    app = StockApp()
    app.run()

if __name__ == "__main__":
    main()