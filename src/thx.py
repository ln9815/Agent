from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time
import requests
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple

# 配置日志
logger = logging.getLogger(__name__)
charset_logger = logging.getLogger('charset_normalizer')
charset_logger.setLevel(logging.WARNING)

# 常量定义
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
DEFAULT_PRICE_FACTOR = 1000  # 默认价格因子

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
        price_factor = data.get('priceFactor', DEFAULT_PRICE_FACTOR)
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
                    "h": float(group[3]),
                    "l": float(group[3]),
                    "v": float(group[2]),
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
            
            return result.dropna()
        
        # 日、周、月、年级别重采样
        return df_copy.resample(PERIOD_MAP[period]).agg({
            'o': 'first',
            'h': 'max',
            'l': 'min',
            'c': 'last',
            'v': 'sum'
        }).dropna()
        
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



class TxhApi:
    """同花顺API客户端类"""
    
    def __init__(self, code: str):
        if not code:
            raise ValueError("股票代码不能为空")
        
        self.code = self._normalize_stock_code(code)
        logger.info(f"标准化股票代码: {self.code}")
        self.headers = {
            **HEADERS,
            'Referer': f"{STOCK_PAGE_URL}/{self.code}/"
        }
        logger.info(f"初始化股票代码: {self.code}")
    
    def _normalize_stock_code(self, code: str) -> str:
        """标准化股票代码格式"""
        code = code.upper().strip()
        
        # 处理港股代码
        if code.startswith('HK'):
            return f'hk_{code}'
        
        # 处理A股代码
        if code[0] in ('0', '3', '6', '8') and len(code) == 6:
            return f'hs_{code}'
        
        # 如果已经有前缀，直接返回
        if '_' in code:
            return code
            
        # 默认处理
        return code
    
    def _make_request(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """发送HTTP请求并提取JSON数据"""
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return extract_json_from_js(response.text)
        except requests.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return None
    
    def get_stock_transaction_all(self) -> List[Dict[str, Any]]:
        """获取股票所有历史交易数据"""
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f"{BASE_URL}/v6/line/{self.code}/01/all.js"
        data = self._make_request(url)
        
        if data:
            return process_stock_data_all(data)
        return []
    
    def get_stock_transaction_last(self) -> List[Dict[str, Any]]:
        """获取股票最新交易数据"""
        url = f"{BASE_URL}/v6/time/{self.code}/defer/last.js"
        data = self._make_request(url)
        
        if data and self.code in data:
            return process_stock_data_last(data[self.code])
        return []
    
    def get_stock_news_list(self) -> List[Dict[str, Any]]:
        """获取股票新闻列表"""
        if self.code.startswith('hs_'):
            return self.get_stock_news_list_v1()
        return self.get_stock_news_list_v2()
    
    def get_stock_news_list_v2(self) -> List[Dict[str, Any]]:
        """获取股票新闻列表（版本2）"""
        # 提取纯股票代码
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        
        # 构建URL - 这里需要根据实际情况调整
        url = f"https://stockpage.10jqka.com.cn/{code}/quote/news/"
        
        headers = {
            "referer": f"https://stockpage.10jqka.com.cn/{code}/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # 使用正则表达式提取JSON部分
            pattern = r'var newsinfo=({.*?})(?=\s*$|\s*;)'
            match = re.search(pattern, response.text, re.DOTALL | re.MULTILINE)
            
            if match:
                json_str = match.group(1)
                try:
                    news_data = json.loads(json_str)
                    data = news_data.get('data', [])
                    logger.info(f"成功获取 {len(data)} 条新闻")
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {e}")
                    return []
            else:
                logger.warning("未找到匹配的JSON数据")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"请求错误: {e}")
            return []
        except Exception as e:
            logger.error(f"获取新闻时发生未知错误: {e}")
            return []
    def get_stock_news_list_v1(self) -> List[Dict[str, Any]]:
        """Get news, reports and announcements for the stock."""
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f"{STOCK_PAGE_URL}/ajax/code/{code}/type/news/"
        
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
            
            return all_items
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news for {self.code}: {e}")
            return []

def main():
    """主函数示例"""
    try:
        # 这里假设有一个setup_logging函数
        from util import setup_logging
        setup_logging(log_file='txh.log')
        
        # 测试不同的股票代码格式
        test_codes = [
            # 'HK2018',
            'HK0981',
            '300059',
            '000001'
        ]
        
        for stock_code in test_codes:
            logger.info(f"开始处理股票代码: {stock_code}")
            
            try:
                api = TxhApi(stock_code)
                
                # 获取最新交易数据
                latest_data = api.get_stock_transaction_last()
                if latest_data:
                    logger.info(f'获取到最新数据 {len(latest_data)} 条记录')
                    df_latest = pd.DataFrame(latest_data)
                    if not df_latest.empty:
                        print(f"{stock_code} 最新数据:")
                        print(df_latest.tail(5))
                else:
                    logger.warning(f"{stock_code} 未获取到最新数据")
                
                # 获取所有历史数据
                all_data = api.get_stock_transaction_all()
                if all_data:
                    logger.info(f'获取到历史数据 {len(all_data)} 条记录')
                    df_all = pd.DataFrame(all_data)
                    
                    # 重采样为周度数据
                    try:
                        resampled_data = resample_with_trading_hours(df_all, 'w')
                        logger.info(f'重采样后数据: {len(resampled_data)} 条记录')
                        if not resampled_data.empty:
                            print(f"{stock_code} 重采样数据:")
                            print(resampled_data.tail(3))
                    except Exception as e:
                        logger.error(f"重采样失败: {e}")
                else:
                    logger.warning(f"{stock_code} 未获取到历史数据")

                # 获取新闻列表
                try:
                    news_list = api.get_stock_news_list()
                    if news_list:
                        logger.info(f'获取到新闻 {len(news_list)} 条.\n{news_list}')
                    else:
                        logger.warning(f"{stock_code} 未获取到新闻")
                except Exception as e:
                    logger.error(f"获取新闻失败: {e}")
                
                print("-" * 50)
                
            except Exception as e:
                logger.error(f"处理股票代码 {stock_code} 时出错: {e}")
                continue
        
    except Exception as e:
        logger.error(f"主函数执行出错: {e}")

if __name__ == '__main__':
    main()