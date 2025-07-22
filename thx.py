from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import requests
import logging
import requests
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


import json
def extract_json_from_js(js_str):
    # 找到第一个左括号和最后一个右括号的位置
    start_idx = js_str.find('(') + 1
    end_idx = js_str.rfind(')')
    
    if start_idx >= end_idx:
        raise ValueError("未找到有效的JSON包裹")
    
    # 提取JSON字符串
    json_str = js_str[start_idx:end_idx]
    
    # 解析JSON
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"提取的JSON字符串: {json_str}")
        return None

def parse_report_links(html_content):
    """先截取相关研报部分，再解析HTML内容提取相关研报链接和标题"""
    report_list = []
    
    # 先使用BeautifulSoup解析整个HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找包含"相关研报"的块
    report_section = soup.find('div', id='report')
    
    # 如果找不到相关研报块，直接返回空列表
    if not report_section:
        return report_list
    
    # 从相关研报块中提取所有的dl元素
    report_items = report_section.find_all('dl')
    
    for item in report_items:
        title_link = item.find('a', class_='client')
        date_span = item.find('span', class_='date')
        
        if title_link and date_span:
            report = {
                'type': '相关研报',
                'publish_date': date_span.text.strip(),
                'title': title_link.get('title'),
                'href': title_link.get('href'),
            }
            report_list.append(report)
    
    return report_list

def parse_hot_news(html_content):
    """解析HTML内容,提取热点新闻链接、标题、发布日期和内容"""
    hot_news_list = []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找id为'news'的部分
    news_section = soup.find('div', id='news')
    
    if news_section:
        # 解析第一种格式的新闻(dl格式)
        news_items = news_section.find_all('dl')
        for item in news_items:
            title_link = item.find('a', class_='client')
            date_span = item.find('span', class_='date')
            summary_dd = item.find('dd', class_='hot_preview')
            
            if title_link and date_span and summary_dd:
                summary = summary_dd.find('p').text.strip()
                hot_news = {
                    'type': '热点新闻',
                    'publish_date': date_span.text.strip('[]'),
                    'title': title_link.get('title'),
                    'href': title_link.get('href'),
                    'summary': summary,
                }
                hot_news_list.append(hot_news)
        
        # 解析第二种格式的新闻(ul>li格式)
        ul_lists = news_section.find_all('ul', class_='news_lists')
        for ul in ul_lists:
            li_items = ul.find_all('li')
            for li in li_items:
                a_tag = li.find('a', class_='client')
                date_span = li.find('span')
                
                if a_tag and date_span:
                    # 从a标签中提取标题和链接
                    title = a_tag.get('title')
                    href = a_tag.get('href')
                    
                    # 日期格式转换(07/18 -> 2025-07-18)
                    month_day = date_span.text.strip()
                    current_year = datetime.now().year
                    publish_date = f"{current_year}-{month_day.replace('/', '-')}"
                    
                    # 内容就是a标签内的文本(去除日期部分)
                    content = a_tag.text.replace(date_span.text, '').strip()
                    
                    hot_news = {
                        'type': '热点新闻',
                        'publish_date': publish_date,
                        'title': title,
                        'href': href,
                        'summary': content,
                    }
                    hot_news_list.append(hot_news)
    
    return hot_news_list
def parse_announcements(html_content):
    """解析HTML内容,提取公司公告链接、标题、发布日期"""
    announcement_list = []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找id为'pubs'的部分
    announcements_section = soup.find('div', id='pubs')
    
    if announcements_section:
        # 从'pubs'部分中提取公告列表
        announcement_items = announcements_section.find_all('li')
        for item in announcement_items:
            a_tag = item.find('a', class_='client')
            date_span = item.find('span')
            
            if a_tag and date_span:
                announcement = {
                    'type': '公司公告',
                    'publish_date': date_span.text.strip(),
                    'title': a_tag.get('title'),
                    'href': a_tag.get('href')
                }
                announcement_list.append(announcement)
    
    return announcement_list


def get_plain_text_from_html(url):
    """从 request 返回的 HTML 中获取纯文本信息"""
    headers = {
        'referer': 'https://news.10jqka.com.cn/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    response.encoding = response.apparent_encoding
    html_content = response.text

    # 使用 BeautifulSoup 解析 HTML 并提取纯文本
    soup = BeautifulSoup(html_content, 'html.parser')

    content_div = soup.find('div', id='contentApp')
    if content_div:
        # 提取纯文本
        text_content = content_div.get_text(strip=True)
        logger.debug(f'提取纯文本: \n{text_content}')
        return text_content
    else:
        plain_text = soup.get_text()# 使用正则表达式替换多个换行符为单个换行符
        cleaned_text = re.sub(r'\n+', '\n', '\n'.join(line.strip() for line in plain_text.split("\n")))
        logger.debug(f"未找到指定的div内容, 全部文本为：\n{cleaned_text}") 
        return cleaned_text


def process_stock_data_all(data: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    处理市场数据，将日期、价格和成交量合并为统一格式
    
    参数:
        data: 包含原始数据的字典，应包含'dates'、'price'和'volumn'字段
    
    返回:
        处理并合并后的市场数据列表，每个元素包含日期、成交量和价格信息
    """


    # 分割并反转日期数据
    date_parts = data["dates"].split(",")
    dates = []
    current_index = 0
    
    for year, count in data["sortYear"]:
        start_idx = current_index
        end_idx = current_index + count # type: ignore
        parts_for_year = date_parts[start_idx:end_idx]
        dates.extend([f"{year}{part}" for part in parts_for_year])
        current_index = end_idx
    
    # 分割并处理价格数据
    price_values = data['price'].split(',')
    prices = []
    
    # 每4个值为一组，处理OHLC数据
    for i in range(0, len(price_values), 4):
        group = price_values[i:i+4]
        if len(group) != 4:
            raise ValueError(f"价格数据格式错误，在位置{i}处不足4个值")
        
        base_price = float(group[0]) / 1000
        # prices.append({
        #     "open": base_price + float(group[1]) / 1000,
        #     "close": base_price + float(group[3]) / 1000,
        #     "high": base_price + float(group[2]) / 1000,
        #     "low": base_price
        # })
        prices.append({
            "o": base_price + float(group[1]) / 1000,
            "c": base_price + float(group[3]) / 1000,
            "h": base_price + float(group[2]) / 1000,
            "l": base_price
        })
    
    # 分割成交量数据
    volumes = data["volumn"].split(",")
    
    # 反转所有列表（假设需要按相反顺序排列）
    reversed_dates = dates[::-1]
    reversed_prices = prices[::-1]
    reversed_volumes = volumes[::-1]
    
    # 确保所有列表长度一致，防止索引越界
    min_length = min(len(reversed_prices), len(reversed_dates), len(reversed_volumes))
    
    # 合并数据
    merged_data = [
        {
            "t": reversed_dates[i],
            "v": reversed_volumes[i],  # 修正了"volumn"的拼写错误
            **reversed_prices[i]
        }
        for i in range(min_length)
    ]

    return merged_data[::-1]


# # 交易时间配置
# trading_hours = "0930-1200,1300-1610"



def process_stock_data_last(data: Dict[str, str]) -> List[Dict[str, Any]]:
    '''
    '''
    # 分割并处理价格数据
    prices = []

    # 每4个值为一组，处理OHLC数据
    for min_values in data['data'].split(';'):
        group = min_values.split(',')
        # prices.append({
        #     "time": group[0],
        #     "current_price": float(group[1]),
        #     "volumn": float(group[2]),
        #     "averange_price": float(group[3])
        # })
        prices.append({
            "t": f'{data["date"]} {group[0][:2]}:{group[0][-2:]}',
            "o": float(group[1]),
            "c": float(group[1]),
            "h": float(group[3]),
            "l": float(group[3]),
            "v": float(group[2]),
        })
    return prices

class TxhApi:
    def __init__(self, code):
        '''
        code: 股票代码
        '''
        self.code = code
    def get_stock_transcation_all(self):
        url = f"https://d.10jqka.com.cn/v6/line/{self.code}/01/all.js"
        headers = {
                    'Referer': f"https://stockpage.10jqka.com.cn/",
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest',
                }
        response = requests.get(
                    url,
                    headers=headers,
                    timeout=10
                )
        response.raise_for_status()
        data = extract_json_from_js(response.text)
    
        processed_data = process_stock_data_all(data) # type: ignore
        return processed_data
    
    def get_stock_transcation_last(self):
        url = f"https://d.10jqka.com.cn/v6/time/{self.code}/defer/last.js"
        headers = {
                    'Referer': f"https://stockpage.10jqka.com.cn/",
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest',
                }
        response = requests.get(
                    url,
                    headers=headers,
                    timeout=10
                )
        response.raise_for_status()

        data = extract_json_from_js(response.text)
        if data is not None and stock_code in data:
            data['data'] = process_stock_data_last(data[stock_code])
            return data
        else:
            return None

    def get_stock_news_list(self):
        '''
        从同花顺获取新闻
        '''
        stock_code = "601318"
        url = f"https://stockpage.10jqka.com.cn/ajax/code/{self.code}/type/news/"
        headers = {
                    'Referer': f"https://stockpage.10jqka.com.cn/{stock_code}/news/",
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest',
                }
        response = requests.get(
                    url,
                    headers=headers,
                    timeout=10
                )
        response.raise_for_status()

        html_content = response.text
        if html_content:
            news_list = parse_hot_news(html_content)
            report_list = parse_report_links(html_content)
            announcements_list = parse_announcements(html_content)
            
            all_items = news_list + announcements_list + report_list

            for item in all_items:
                item['content'] = get_plain_text_from_html(item['href'])
            return all_items
        return []

def parse_trading_hours(trading_hours = "0930-1200,1300-1610"):
    from datetime import time
    """将交易时间字符串解析为时间范围列表"""
    time_ranges = []
    for period in trading_hours.split(','):
        start_str, end_str = period.split('-')
        start_time = time(int(start_str[:2]), int(start_str[2:]))
        end_time = time(int(end_str[:2]), int(end_str[2:]))
        time_ranges.append((start_time, end_time))
    return time_ranges

def resample_with_trading_hours(df, period, trading_periods=""):
    """严格在交易时间段内进行重采样"""
    # 创建空的DataFrame存储结果
    result = pd.DataFrame()
    
    df['t'] = pd.to_datetime(df['t'])
    df = df.set_index('t')

    period = period.lower()
    
    period_map = {
        '5': '5min',
        '15': '15min',
        '20': '20min',
        '30': '30min',
        'w': 'w-mon',
        'm': 'm',
        'y': 'y',
    }
    if period not in period_map.keys():
        raise ValueError(f"Invalid period: {period}. Please use one of {period_map.keys()}")
    if period in ('5','15','20','30'):
        if trading_periods == "":
            raise ValueError(f"Invalid trading_periods: {trading_periods}. Please use example as '0930-1200,1300-1610'")

    if period in ('5','15','20','30'):
        for start_time, end_time in parse_trading_hours(trading_periods):
            print(start_time,end_time)
            mask = (df.index.time >= start_time) & (df.index.time <= end_time)
            period_df = df[mask].copy()
            
            if not period_df.empty:
                resampled = period_df.resample(period_map[period]).agg({
                    'o': 'first',
                    'h': 'max',
                    'l': 'min',
                    'c': 'last',
                    'v': 'sum'
                })
                result = pd.concat([result, resampled])
    else:
        result = df.resample(period_map[period]).agg({
                    'o': 'first',
                    'h': 'max',
                    'l': 'min',
                    'c': 'last',
                    'v': 'sum'
                })
    result = result.dropna().sort_index()
    return result



if __name__ == '__main__':
    from util import setup_logging
    import pandas as pd
    from indicators import add_technical_indicators

    setup_logging(log_file='txh.log')
    stock_code = 'hk_HK2018'
    api = TxhApi(stock_code)
    # news = api.get_stock_news_list()
    # logger.debug(f'个股 {stock_code} 新闻:\n{news}\n')
    # data = api.get_stock_transcation_all()
    # data = add_technical_indicators(data)
    # logger.debug(f'total {len(data)} got.. \n {pd.DataFrame(data).tail(10)}')
    
    data = api.get_stock_transcation_all()
    logger.debug(f'total {len(data)} got.. \n {pd.DataFrame(data).head(10)}')
    data = resample_with_trading_hours(pd.DataFrame(data),'w')

    # data = api.get_stock_transcation_last()
    # # data_price = add_technical_indicators(data['data'],price_col='c') # type: ignore
    # logger.debug(f'total {len(data['data'])} got.. \n {pd.DataFrame(data['data']).tail(25)}')
    # trading_periods = "0930-1200,1300-1610"
    # data = resample_with_trading_hours(pd.DataFrame(data['data']),'15',trading_periods)
    # logger.debug(f'total {len(data)} got.. \n {pd.DataFrame(data).head(10)}')

