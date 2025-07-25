from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time
import requests
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}
BASE_URL = "https://d.10jqka.com.cn"
STOCK_PAGE_URL = "https://stockpage.10jqka.com.cn"
PERIOD_MAP = {
    '5': '5min',
    '15': '15min',
    '20': '20min',
    '30': '30min',
    'd': 'd',
    'w': 'w-mon',
    'm': 'm',
    'y': 'y',
}
DEFAULT_TRADING_HOURS = "0930-1200,1300-1610"


def extract_json_from_js(js_str: str) -> Optional[Dict]:
    """Extract JSON data from JavaScript string."""
    try:
        start_idx = js_str.find('(') + 1
        end_idx = js_str.rfind(')')
        
        if start_idx >= end_idx:
            raise ValueError("No valid JSON wrapper found")
            
        return json.loads(js_str[start_idx:end_idx])
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"JSON extraction error: {e}")
        return None


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
                publish_date = f"{current_year}-{month_day.replace('/', '-')}"
                
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


def get_plain_text_from_html(url: str) -> str:
    """Extract plain text from HTML content at given URL."""
    headers = {**HEADERS, 'referer': 'https://news.10jqka.com.cn/'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if content_div := soup.find('div', id='contentApp'):
            return content_div.get_text(strip=True)
        
        plain_text = soup.get_text()
        return re.sub(r'\n+', '\n', '\n'.join(line.strip() for line in plain_text.split("\n")))
    
    except requests.RequestException as e:
        logger.error(f"Failed to fetch content from {url}: {e}")
        return ""


def process_stock_data_all(data: Dict[str, str]) -> List[Dict[str, Any]]:
    """Process market data, combining dates, prices and volumes into unified format."""
    if not all(key in data for key in ["dates", "price", "volumn"]):
        raise ValueError("Missing required fields in data")
    
    # Process dates
    date_parts = data["dates"].split(",")
    dates = []
    current_index = 0
    
    for year, count in data["sortYear"]:
        parts = date_parts[current_index:current_index + count]
        dates.extend(f"{year}{part}" for part in parts)
        current_index += count
    
    # Process prices
    price_values = data['price'].split(',')
    if len(price_values) % 4 != 0:
        raise ValueError("Price data format error - not divisible by 4")
    
    prices = []
    for i in range(0, len(price_values), 4):
        group = price_values[i:i+4]
        base_price = float(group[0]) / 1000
        prices.append({
            "o": base_price + float(group[1]) / 1000,
            "c": base_price + float(group[3]) / 1000,
            "h": base_price + float(group[2]) / 1000,
            "l": base_price
        })
    
    # Process volumes
    volumes = data["volumn"].split(",")
    print(volumes)
    
    # Reverse all lists and merge
    min_length = min(len(prices), len(dates), len(volumes))
    return [
        {
            "t": dates[i],
            "v": volumes[i],
            **prices[i]
        }
        for i in range(min_length)
    ]


def process_stock_data_last(data: Dict[str, str]) -> List[Dict[str, Any]]:
    """Process last transaction data."""
    if 'data' not in data:
        return []
    
    prices = []
    for min_values in data['data'].split(';'):
        group = min_values.split(',')
        if len(group) < 4:
            continue
            
        prices.append({
            "t": f'{data["date"]} {group[0][:2]}:{group[0][-2:]}',
            "o": float(group[1]),
            "c": float(group[1]),
            "h": float(group[3]),
            "l": float(group[3]),
            "v": float(group[2]),
        })
    return prices


def parse_trading_hours(trading_hours: str = DEFAULT_TRADING_HOURS) -> List[Tuple[time, time]]:
    """Parse trading hours string into list of time ranges."""
    time_ranges = []
    for period in trading_hours.split(','):
        try:
            start_str, end_str = period.split('-')
            start_time = time(int(start_str[:2]), int(start_str[2:]))
            end_time = time(int(end_str[:2]), int(end_str[2:]))
            time_ranges.append((start_time, end_time))
        except ValueError:
            logger.warning(f"Invalid time period format: {period}")
    return time_ranges


def resample_with_trading_hours(
    df: pd.DataFrame, 
    period: str, 
    trading_periods: str = DEFAULT_TRADING_HOURS
) -> pd.DataFrame:
    """Resample data strictly within trading hours."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")
    
    if 't' not in df.columns:
        raise ValueError("DataFrame must contain 't' column for timestamps")
    
    period = period.lower()
    if period not in PERIOD_MAP:
        raise ValueError(f"Invalid period: {period}. Valid options: {list(PERIOD_MAP.keys())}")
    
    df = df.copy()
    df['t'] = pd.to_datetime(df['t'])
    df = df.set_index('t').sort_index()
    
    if period in ('5', '15', '20', '30'):
        if not trading_periods:
            raise ValueError("Trading periods required for intraday resampling")
            
        result = pd.DataFrame()
        for start_time, end_time in parse_trading_hours(trading_periods):
            mask = (df.index.time >= start_time) & (df.index.time <= end_time)
            period_df = df[mask]
            
            if not period_df.empty:
                resampled = period_df.resample(PERIOD_MAP[period]).agg({
                    'o': 'first',
                    'h': 'max',
                    'l': 'min',
                    'c': 'last',
                    'v': 'sum'
                })
                result = pd.concat([result, resampled])
        
        return result.dropna()
    
    return df.resample(PERIOD_MAP[period]).agg({
        'o': 'first',
        'h': 'max',
        'l': 'min',
        'c': 'last',
        'v': 'sum'
    }).dropna()


class TxhApi:
    def __init__(self, code: str):
        self.code = code
        self.headers = {
            **HEADERS,
            'Referer': f"{STOCK_PAGE_URL}/{self.code}/"
        }
    
    def _make_request(self, url: str) -> Optional[Dict]:
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return extract_json_from_js(response.text)
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    def get_stock_transaction_all(self) -> List[Dict[str, Any]]:
        """Get all historical transaction data for the stock."""
        url = f"{BASE_URL}/v6/line/{self.code}/01/all.js"
        if data := self._make_request(url):
            return process_stock_data_all(data)
        return []
    
    def get_stock_transaction_last(self) -> Optional[Dict[str, Any]]:
        """Get the last transaction data for the stock."""
        url = f"{BASE_URL}/v6/time/{self.code}/defer/last.js"
        if data := self._make_request(url):
            if self.code in data:
                data['data'] = process_stock_data_last(data[self.code])
                return data
        return None
    
    def get_stock_news_list(self) -> List[Dict[str, Any]]:
        """Get news, reports and announcements for the stock."""
        url = f"{STOCK_PAGE_URL}/ajax/code/{self.code}/type/news/"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
            
            if not html_content:
                return []
            
            news_items = parse_hot_news(html_content)
            reports = parse_report_links(html_content)
            announcements = parse_announcements(html_content)
            
            all_items = news_items + reports + announcements
            
            for item in all_items:
                item['content'] = get_plain_text_from_html(item['href'])
            
            return all_items
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news for {self.code}: {e}")
            return []


if __name__ == '__main__':
    from src.util import setup_logging
    
    setup_logging(log_file='txh.log')
    stock_code = 'hk_HK2018'
    api = TxhApi(stock_code)
    
    # Example usage
    data = api.get_stock_transaction_all()
    logger.debug(f'Total {len(data)} records found. Sample:\n{pd.DataFrame(data).tail(10)}')
    
    resampled_data = resample_with_trading_hours(pd.DataFrame(data), 'd')
    logger.debug(f'Resampled data:\n{resampled_data.tail()}')