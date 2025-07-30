import pandas as pd
import talib as ta
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple


PERIOD_MAP = {
    '1m': '1min',
    '5m': '5min',
    '15m': '15min',
    '20m': '20min',
    '30m': '30min',
    'd': 'd',
    'w': 'w-mon',
    'm': 'm',
    'y': 'y',
}

def caculate_ta(df: pd.DataFrame) -> pd.DataFrame:
    '''计算技术指标'''

    df = df.copy()
    required_columns = {'open', 'high', 'low', 'close', 'volume'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"DataFrame缺少必要的列: {missing_columns}")

    # 价格相关技术指标
    df['RSI'] = ta.RSI(df['close'], timeperiod=14)
    df['MA5'] = ta.MA(df['close'], timeperiod=5)
    df['MA20'] = ta.MA(df['close'], timeperiod=20)
    df['EMA5']  = ta.EMA(df['close'],  timeperiod=5)
    df['EMA20']  = ta.EMA(df['close'],  timeperiod=20)
    df['DIF'],df['DEM'],df['HISTOGRAM'] = ta.MACD(df['close'],fastperiod=12, slowperiod=26, signalperiod=9)
    df['BBUP'], df['BBMID'], df['BBLOW'] = ta.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    df['MOM'] = ta.MOM(df['close'], timeperiod=10)
    df['ROC'] = ta.ROC(df['close'], timeperiod=12)

    # 波动率相关技术指标
    df['ATR'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    df['SAR'] = ta.SAR(df['high'], df['low'], acceleration=0.02, maximum=0.2)
    df['WILLR'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)

    # 量能相关技术指标
    df['OBV'] = ta.OBV(df['close'], df['volume'])

    return df


def parse_trading_hours(trading_hours: str) -> List[Tuple[time, time]]:
    """解析交易时间字符串为时间范围列表"""
    if not trading_hours:
        return []
        
    time_ranges = []
    for period in trading_hours.split(','):
        try:
            start_str, end_str = period.strip().split('-')
            if len(start_str) != 4 or len(end_str) != 4:
                raise ValueError(f"时间格式错误: {period}")
                
            start_time = time(int(start_str[:2]), int(start_str[2:]))
            end_time = time(int(end_str[:2]), int(end_str[2:]))
            time_ranges.append((start_time, end_time))
        except (ValueError, IndexError) as e:
            raise ValueError(f"无效的时间段格式: {period}, 错误: {e}")
            
    return time_ranges

def resample_df(
    df: pd.DataFrame, 
    period: str, 
    market: str = 'hs'
) -> pd.DataFrame:
    """在交易时间内严格重新采样数据"""
    
    if df.empty:
        return pd.DataFrame()
    
    if 'date' not in df.columns:
        raise ValueError("DataFrame必须包含'date'列作为时间戳")
    
    period = period.lower()
    if period not in PERIOD_MAP:
        raise ValueError(f"无效的周期: {period}. 有效选项: {list(PERIOD_MAP.keys())}")
    
    # 检查必要的列
    required_columns = {'open', 'high', 'low', 'close', 'volume'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"DataFrame缺少必要的列: {missing_columns}")
    
    # 准备数据
    df_copy = df.copy()
    df_copy['date'] = pd.to_datetime(df_copy['date'])
    df_copy = df_copy.set_index('date').sort_index()
    
  
    # 分钟级别重采样需要交易时间
    if period in ('5', '15', '20', '30'):
        trading_periods = "0930-1200,1300-1610" if market.startswith('hk') else "0900-1130,1300-1500"
        
        # 解析交易时间
        time_ranges = parse_trading_hours(trading_periods)
        if not time_ranges:
            raise ValueError("无效的交易时间格式")
        
        result = pd.DataFrame()
        
        # 按交易时间段处理
        for start_time, end_time in time_ranges:
            mask = (df_copy.index.time >= start_time) & (df_copy.index.time <= end_time)
            period_df = df_copy[mask]
            
            if not period_df.empty:
                resampled = period_df.resample(PERIOD_MAP[period]).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                })
                result = pd.concat([result, resampled])
        
        # 重置索引以包含时间戳列
        result = result.reset_index()
        return result.dropna()
    
    # 日、周、月、年级别重采样
    resampled = df_copy.resample(PERIOD_MAP[period]).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # 重置索引以包含时间戳列
    resampled = resampled.reset_index()
    return resampled