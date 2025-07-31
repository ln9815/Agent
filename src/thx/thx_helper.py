from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
import re

logger = logging.getLogger(__name__)

DEFAULT_TRADING_HOURS = "0930-1200,1300-1610"
DEFAULT_PRICE_FACTOR = 1  # 默认价格因子
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
                    "open": base_price + float(group[1]) / price_factor,  # 开盘价
                    "close": base_price + float(group[3]) / price_factor,  # 收盘价
                    "high": base_price + float(group[2]) / price_factor,  # 最高价
                    "low": base_price  # 最低价
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
                "date": dates[i],
                "volume": volumes[i],
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
                    "date": f'{date_str} {formatted_time}',
                    "open": float(group[1]),
                    "close": float(group[1]),
                    "high": float(group[1]),
                    "low": float(group[1]),
                    "volume": float(group[4]),
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"处理最新数据时出错: {e}")
                continue
                
        return prices
    except Exception as e:
        logger.error(f"处理最新股票数据时出错: {e}")
        return []

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

def convert_datetime(time_str:str)->datetime:
    '''
    转换时间字符串为datetime对象
    '''
    from datetime import datetime
    current_year,current_month, current_day= datetime.now().year,datetime.now().month,datetime.now().day
    
    # 处理三种格式
    if ' ' in time_str:  # 格式 "07-30 19:21"
        date_part, time_part = time_str.split(' ')
        month, day = map(int, date_part.split('-'))
        hour, minute = map(int, time_part.split(':'))
    elif '/' in time_str:  # 格式 "07/31"
        month, day = map(int, time_str.split('/'))
        hour, minute = 0, 0
    elif '-' in time_str and len(time_str) == 10:  # 格式 "2025-06-09"
        _, month, day = time_str.split('-')
        month, day = int(month), int(day)
        hour, minute = 0, 0
    else:
        raise ValueError("Unsupported time format")
    
    # 判断年份：如果月日大于当前月日，则用上一年
    if (month, day) > (current_month, current_day):
        year = current_year - 1
    else:
        year = current_year
    
    return datetime.strptime(f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")

def extract_stock_data_hs(response):
    """
    从响应对象中提取股票指数数据
    
    参数:
        response: 包含HTML内容的响应对象，需有text属性
        
    返回:
        dict: 包含股票指数各类数据的字典
    """
    # 创建BeautifulSoup对象
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 定位到board-hq容器并提取数据
    board_hq = soup.find('div', class_='board-hq')
    if not board_hq:
        raise ValueError("未找到class为'board-hq'的div元素")
    
    # 提取指数名称和代码
    h3_tag = board_hq.find('h3')
    index_name = h3_tag.contents[0].strip()
    index_code = h3_tag.find('span').get_text(strip=True)
    
    # 提取当前值
    current_value = board_hq.find('span', class_='board-xj').get_text(strip=True)
    
    # 处理涨跌数据
    zdf_text = board_hq.find('p', class_='board-zdf').get_text(strip=True)
    zdf_parts = zdf_text.split()
    change = zdf_parts[0]
    
    # 构建基础结果字典
    result = {
        '指数名称': index_name,
        '指数代码': index_code,
        '当前指数': float(current_value),
        '涨跌': float(change),
    }
    
    # 提取board-infos中的详细数据
    board_infos = soup.find('div', class_='board-infos')
    if not board_infos:
        raise ValueError("未找到class为'board-infos'的div元素")
    
    dl_tags = board_infos.find_all('dl')
    for dl in dl_tags:
        dt_text = dl.find('dt').get_text(strip=True)
        dd_text = dl.find('dd').get_text(strip=True)
        # 根据内容判断是否转换为数值类型
        if '%' in dd_text:
            result[dt_text] = dd_text
        else:
            result[dt_text] = float(dd_text)
    
    return result