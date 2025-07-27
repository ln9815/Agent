from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
import re

logger = logging.getLogger(__name__)

DEFAULT_TRADING_HOURS = "0930-1200,1300-1610"
DEFAULT_PRICE_FACTOR = 1000  # 默认价格因子
PERIOD_MAP = {
    '5m': '5min',
    '15m': '15min',
    '20m': '20min',
    '30m': '30min',
    'd': 'd',
    'w': 'w-mon',
    'm': 'm',
    'y': 'y',
}

STOCK_VAR_MAP ={
    '5':'股票编码',
    'name':'股票名称',
    '6': '昨收',
    '7': '开盘',
    '8': '最高',
    '9': '最低',
    '10': '收盘',
    '264648': '涨幅',
    '199112': '涨幅(%)',
    '13': '成交量',
    '19': '成交额',
    '1968584': '换手率',
    '526792': '振幅',
    '3541450': '总市值',
    '3475914': '流通市值',
    '134152': '市盈率(动)',
    '1149395': '市净率',
    '2034120': '市盈率',
    '1771976': '换手率',
}
def extract_json_from_js(js_str: str) -> Optional[Dict]:
    """从JavaScript字符串中提取JSON数据"""
    if not js_str:
        return None
        
    try:
        start_idx = js_str.find('(') + 1
        end_idx = js_str.rfind(')')
        
        if start_idx <= 0 or end_idx <= start_idx:
            logger.error("未找到有效的JSON包装格式")
            return None
            
        json_str = js_str[start_idx:end_idx]
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"JSON提取错误: {e}")
        return None

def process_stock_data_all(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """处理市场数据，将日期、价格和成交量合并为统一格式"""
    if not isinstance(data, dict):
        raise TypeError("数据必须是字典类型")
        
    required_fields = ["dates", "price", "volumn", "sortYear"]
    if not all(key in data for key in required_fields):
        raise ValueError(f"数据缺少必需字段: {required_fields}")
    
    try:
        # 获取价格因子，如果不存在则使用默认值
        price_factor = data.get('priceFactor', 1)
        if not isinstance(price_factor, (int, float)) or price_factor <= 0:
            price_factor = DEFAULT_PRICE_FACTOR
            logger.warning(f"价格因子无效，使用默认值: {DEFAULT_PRICE_FACTOR}")
        
        # 处理日期
        date_parts = data["dates"].split(",")
        dates = []
        current_index = 0
        
        for year, count in data["sortYear"]:
            # if current_index + count > len(date_parts):
            #     logger.warning(f"日期数据不足，年份 {year} 需要 {count} 个数据点")
            #     break
                
            parts = date_parts[current_index:current_index + count]
            dates.extend(f"{year}{part}" for part in parts)
            current_index += count
        
        # 处理价格数据
        price_values = data['price'].split(',')
        if len(price_values) % 4 != 0:
            raise ValueError("价格数据格式错误 - 长度不是4的倍数")
        
        prices = []
        for i in range(0, len(price_values), 4):
            group = price_values[i:i+4]
            try:
                base_price = float(group[0]) / price_factor
                prices.append({
                    "o": base_price + float(group[1]) / price_factor,  # 开盘价
                    "c": base_price + float(group[3]) / price_factor,  # 收盘价
                    "h": base_price + float(group[2]) / price_factor,  # 最高价
                    "l": base_price  # 最低价
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"处理价格数据时出错: {e}")
                continue
        
        # 处理成交量
        volumes = data["volumn"].split(",")
        
        # 合并所有数据
        min_length = min(len(prices), len(dates), len(volumes))
        if min_length == 0:
            logger.warning("处理后的数据为空")
            return []
            
        return [
            {
                "t": dates[i],
                "v": volumes[i],
                **prices[i]
            }
            for i in range(min_length)
        ]
        
    except Exception as e:
        logger.error(f"处理股票数据时出错: {e}")
        return []

def process_stock_data_last(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """处理最新交易数据"""
    if not isinstance(data, dict) or 'data' not in data:
        return []
    
    try:
        prices = []
        date_str = data.get('date', '')
        
        for min_values in data['data'].split(';'):
            if not min_values.strip():
                continue
                
            group = min_values.split(',')
            if len(group) < 4:
                continue
            
            try:
                # 格式化时间
                time_str = group[0].strip()
                if len(time_str) >= 4:
                    formatted_time = f'{time_str[:2]}:{time_str[-2:]}'
                else:
                    formatted_time = time_str
                
                prices.append({
                    "t": f'{date_str} {formatted_time}',
                    "o": float(group[1]),
                    "c": float(group[1]),
                    "h": float(group[1]),
                    "l": float(group[1]),
                    "v": float(group[4]),
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"处理最新数据时出错: {e}")
                continue
                
        return prices
    except Exception as e:
        logger.error(f"处理最新股票数据时出错: {e}")
        return []

def parse_trading_hours(trading_hours: str = DEFAULT_TRADING_HOURS) -> List[Tuple[time, time]]:
    """解析交易时间字符串为时间范围列表"""
    if not trading_hours:
        return []
        
    time_ranges = []
    for period in trading_hours.split(','):
        try:
            start_str, end_str = period.strip().split('-')
            if len(start_str) != 4 or len(end_str) != 4:
                logger.warning(f"时间格式错误: {period}")
                continue
                
            start_time = time(int(start_str[:2]), int(start_str[2:]))
            end_time = time(int(end_str[:2]), int(end_str[2:]))
            time_ranges.append((start_time, end_time))
        except (ValueError, IndexError) as e:
            logger.warning(f"无效的时间段格式: {period}, 错误: {e}")
            
    return time_ranges

def resample_with_trading_hours(
    df: pd.DataFrame, 
    period: str, 
    trading_periods: str = DEFAULT_TRADING_HOURS
) -> pd.DataFrame:
    """在交易时间内严格重新采样数据"""
    # 输入验证
    if not isinstance(df, pd.DataFrame):
        raise TypeError("输入必须是pandas DataFrame")
    
    if df.empty:
        return pd.DataFrame()
    
    if 't' not in df.columns:
        raise ValueError("DataFrame必须包含't'列作为时间戳")
    
    period = period.lower()
    if period not in PERIOD_MAP:
        raise ValueError(f"无效的周期: {period}. 有效选项: {list(PERIOD_MAP.keys())}")
    
    try:
        # 准备数据
        df_copy = df.copy()
        df_copy['t'] = pd.to_datetime(df_copy['t'])
        df_copy = df_copy.set_index('t').sort_index()
        
        # 检查必要的列
        required_columns = {'o', 'h', 'l', 'c', 'v'}
        missing_columns = required_columns - set(df_copy.columns)
        if missing_columns:
            raise ValueError(f"DataFrame缺少必要的列: {missing_columns}")
        
        # 分钟级别重采样需要交易时间
        if period in ('5', '15', '20', '30'):
            if not trading_periods:
                raise ValueError("分钟级重采样需要交易时间段")
            
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
                        'o': 'first',
                        'h': 'max',
                        'l': 'min',
                        'c': 'last',
                        'v': 'sum'
                    })
                    result = pd.concat([result, resampled])
            
            # 重置索引以包含时间戳列
            result = result.reset_index()
            return result.dropna()
        
        # 日、周、月、年级别重采样
        resampled = df_copy.resample(PERIOD_MAP[period]).agg({
            'o': 'first',
            'h': 'max',
            'l': 'min',
            'c': 'last',
            'v': 'sum'
        }).dropna()
        
        # 重置索引以包含时间戳列
        resampled = resampled.reset_index()
        return resampled
        
    except Exception as e:
        logger.error(f"重采样数据时出错: {e}")
        return pd.DataFrame()

def parse_report_links(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML content to extract related research report links and titles."""
    soup = BeautifulSoup(html_content, 'html.parser')
    report_section = soup.find('div', id='report')
    
    if not report_section:
        return []
    
    reports = []
    for item in report_section.find_all('dl'):
        title_link = item.find('a', class_='client')
        date_span = item.find('span', class_='date')
        
        if title_link and date_span:
            reports.append({
                'type': '相关研报',
                'publish_date': date_span.text.strip(),
                'title': title_link.get('title'),
                'href': title_link.get('href'),
            })
    
    return reports


def parse_hot_news(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML content to extract hot news links, titles, dates and content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    news_section = soup.find('div', id='news')
    
    if not news_section:
        return []
    
    hot_news = []
    
    # Parse dl format news
    for item in news_section.find_all('dl'):
        title_link = item.find('a', class_='client')
        date_span = item.find('span', class_='date')
        summary_dd = item.find('dd', class_='hot_preview')
        
        if all([title_link, date_span, summary_dd]):
            hot_news.append({
                'type': '热点新闻',
                'publish_date': date_span.text.strip('[]'),
                'title': title_link.get('title'),
                'href': title_link.get('href'),
                'summary': summary_dd.find('p').text.strip(),
            })
    
    # Parse ul>li format news
    for ul in news_section.find_all('ul', class_='news_lists'):
        for li in ul.find_all('li'):
            a_tag = li.find('a', class_='client')
            date_span = li.find('span')
            
            if a_tag and date_span:
                month_day = date_span.text.strip()
                current_year = datetime.now().year
                # publish_date = f"{current_year}-{month_day.replace('/', '-')}"
                date_obj = datetime.strptime(f"{current_year}/{month_day}", "%Y/%m/%d")
                publish_date = date_obj.strftime("%Y-%m-%d")
                
                hot_news.append({
                    'type': '热点新闻',
                    'publish_date': publish_date,
                    'title': a_tag.get('title'),
                    'href': a_tag.get('href'),
                    'summary': a_tag.text.replace(date_span.text, '').strip(),
                })
    
    return hot_news


def parse_announcements(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML content to extract company announcements."""
    soup = BeautifulSoup(html_content, 'html.parser')
    announcements_section = soup.find('div', id='pubs')
    
    if not announcements_section:
        return []
    
    announcements = []
    for item in announcements_section.find_all('li'):
        a_tag = item.find('a', class_='client')
        date_span = item.find('span')
        
        if a_tag and date_span:
            announcements.append({
                'type': '公司公告',
                'publish_date': date_span.text.strip(),
                'title': a_tag.get('title'),
                'href': a_tag.get('href')
            })
    
    return announcements

from bs4 import BeautifulSoup

def parse_financial_data(html_content: str) -> Dict[str, str]:
    """
    从HTML内容中解析财务数据
    
    参数:
        html_content: 包含财务数据的HTML字符串
    
    返回:
        包含财务数据的字典
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    financial_data = {}
    
    # 查找指定class的dl标签
    dl_tag = soup.find('dl', class_="company_details")
    if not dl_tag:
        print(f"警告: 未找到class为'company_details'的dl标签")
        return financial_data
    
    # 查找dl标签内所有dt和dd标签
    dt_tags = dl_tag.find_all('dt')
    dd_tags = dl_tag.find_all('dd')
    
    # 确保dt和dd标签数量匹配
    if len(dt_tags) == len(dd_tags):
        for dt, dd in zip(dt_tags, dd_tags):
            # 提取键（去除冒号）
            key = dt.get_text(strip=True).replace('：', '')
            # 提取值
            value = dd.get_text(strip=True)
            financial_data[key] = value
    else:
        print("警告: dt和dd标签数量不匹配")
    
    return financial_data
from datetime import datetime, date
import re

import re
from datetime import datetime

def format_date(date_str):
    current_year = datetime.now().year
    current_date = datetime.now().date()
    
    # Check if the string contains a 4-digit year
    if re.search(r'\d{4}', date_str):
        # Extract date part only (remove time if present)
        parts = re.split(r'[\sT]', date_str, 1)
        return parts[0]  # Return the first part (date portion)
    
    # Define month name/abbreviation mappings
    month_names = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 
        'august': 8, 'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }
    
    # Remove time part to avoid interfering with date parsing
    time_match = re.search(r'(\d{1,2}:\d{1,2}(:\d{1,2})?)', date_str)
    if time_match:
        time_part = time_match.group(1)
        date_str = date_str.replace(time_part, '').strip()
        if date_str.endswith(('-', '/', ' ')):
            date_str = date_str[:-1]
    
    # Attempt to match common date formats
    # Format 1: MM/DD or MM-DD (US)
    match = re.match(r'(\d{1,2})[-/](\d{1,2})$', date_str)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return _process_datetime(month, day, current_year, current_date)
    
    # Format 2: DD/MM or DD-MM (European)
    match = re.match(r'(\d{1,2})[-/](\d{1,2})$', date_str)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            if month > 12 or (month == 12 and day > 31):
                return _process_datetime(month, day, current_year, current_date)
    
    # Format 3: MonthName-DD (e.g., "Jan-01")
    match = re.match(r'([a-zA-Z]+)[-/](\d{1,2})$', date_str)
    if match:
        month_name = match.group(1).lower()
        day = int(match.group(2))
        if month_name in month_names:
            month = month_names[month_name]
            return _process_datetime(month, day, current_year, current_date)
    
    # Return original string if no format matches
    return date_str

def _process_datetime(month, day, current_year, current_date):
    """Generate a date string in YYYY-MM-DD format (time discarded)."""
    try:
        # Create a date object for comparison
        temp_date = datetime(current_year, month, day).date()
        if temp_date <= current_date:
            return temp_date.strftime('%Y-%m-%d')
        else:
            # Use previous year if date is in the future
            return datetime(current_year - 1, month, day).strftime('%Y-%m-%d')
    except ValueError:
        # Handle invalid dates (e.g., February 30)
        return f"{current_year}-{month:02d}-{day:02d}"
