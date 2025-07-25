from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, time, timedelta
import requests
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'User -Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
}
BASE_URL = "https://d.10jqka.com.cn"
STOCK_PAGE_URL = "https://stockpage.10jqka.com.cn"
PERIOD_MAP = {
    '1m': '1min',
    '5m': '5min',
    '15m': '15min',
    '30m': '30min',
    '60m': '60min',
    '1h': '60min',
    '1d': 'd',
    '5d': 'd',
    '1wk': 'w-mon',
    '1mo': 'm',
    '3mo': 'm',
    '6mo': 'm',
    '1y': 'y',
    '2y': 'y',
    '5y': 'y',
    '10y': 'y',
    'ytd': 'd',
    'max': 'd'
}
DEFAULT_TRADING_HOURS = "0930-1200,1300-1610"

@dataclass
class TickerInfo:
    """Store ticker information similar to yfinance info structure"""
    symbol: str
    short_name: str = ""
    long_name: str = ""
    sector: str = ""
    industry: str = ""
    market: str = ""
    currency: str = "CNY"
    exchange: str = ""

class Ticker:
    """Main ticker class implementing yfinance-like interface"""
    
    def __init__(self, ticker: str, session: Optional[requests.Session] = None):
        """
        Initialize ticker with yfinance-compatible interface
        
        Args:
            ticker: Stock symbol (e.g., 'hk_HK2018', '000001')
            session: Optional requests session for connection pooling
        """
        self.ticker = ticker
        self._session = session or requests.Session()
        self._session.headers.update(HEADERS)
        
        # Initialize common yfinance attributes
        self._history: Optional[pd.DataFrame] = None
        self._info: Optional[Dict] = None
        self._news: Optional[List] = None
        
    @property
    def info(self) -> Dict[str, Any]:
        """Get ticker info (similar to yfinance info property)"""
        if self._info is None:
            self._info = self._fetch_ticker_info()
        return self._info
    
    @property
    def news(self) -> List[Dict[str, Any]]:
        """Get news list (similar to yfinance news property)"""
        if self._news is None:
            self._news = self._fetch_news()
        return self._news
    
    def history(self, 
                period: str = "1mo",
                interval: str = "1d",
                start: Optional[Union[str, datetime]] = None,
                end: Optional[Union[str, datetime]] = None,
                prepost: bool = False,
                auto_adjust: bool = True,
                back_adjust: bool = False,
                repair: bool = False,
                keepna: bool = False,
                actions: bool = True,
                rounding: bool = False) -> pd.DataFrame:
        """
        Get historical market data with yfinance-compatible interface
        
        Args:
            period: Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
            interval: Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
            start: Start date string (YYYY-MM-DD) or datetime object
            end: End date string (YYYY-MM-DD) or datetime object
            prepost: Include pre and post market data
            auto_adjust: Automatically adjust prices
            back_adjust: Back-adjust prices  
            repair: Repair bad data points
            keepna: Keep NaN values
            actions: Include dividends and stock splits
            rounding: Round values
        
        Returns:
            DataFrame with OHLCV data indexed by date
        """
        try:
            # Fetch raw data
            raw_data = self._fetch_historical_data()
            if not raw_data:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(raw_data)
            
            # Convert timestamp column and set as index
            df['Date'] = pd.to_datetime(df['t'])
            df = df.set_index('Date')
            
            # Rename columns to match yfinance format
            df = df.rename(columns={
                'o': 'Open',
                'h': 'High', 
                'l': 'Low',
                'c': 'Close',
                'v': 'Volume'
            })
            
            # Select only OHLCV columns
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            # Apply date filtering if specified
            if start:
                start_date = pd.to_datetime(start) if isinstance(start, str) else start
                df = df[df.index >= start_date]
            
            if end:
                end_date = pd.to_datetime(end) if isinstance(end, str) else end
                df = df[df.index <= end_date]
            
            # Apply period filtering if no start/end specified
            if not start and not end:
                df = self._apply_period_filter(df, period)
            
            # Resample if interval different from daily
            if interval != '1d':
                df = self._resample_data(df, interval)
            
            # Sort by date ascending
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching history for {self.ticker}: {e}")
            return pd.DataFrame()
    
    def get_intraday_data(self, interval: str = '1m', range: str = '1d') -> pd.DataFrame:
        """
        Get intraday market data for the ticker.
        
        Args:
            interval: Valid intervals: 1m, 5m, 15m, 30m, 1h
            range: Valid ranges: 1d, 5d, 1mo
        
        Returns:
            DataFrame with intraday data indexed by timestamp
        """
        if interval not in PERIOD_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid options: {list(PERIOD_MAP.keys())}")
        
        url = f"{BASE_URL}/v6/line/{self.ticker}/01/{range}.js"
        
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            # Extract JSON from JavaScript response
            data = self._extract_json_from_js(response.text)
            if not data:
                return pd.DataFrame()
            
            # Process intraday data
            return self._process_intraday_data(data)
        
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return pd.DataFrame()
    
    def _process_intraday_data(self, data: Dict[str, str]) -> pd.DataFrame:
        """Process intraday market data"""
        if 'data' not in data:
            return pd.DataFrame()
        
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
        
        # Convert to DataFrame
        df = pd.DataFrame(prices)
        df['t'] = pd.to_datetime(df['t'])
        df = df.set_index('t')
        
        return df
    
    def _fetch_historical_data(self) -> List[Dict[str, Any]]:
        """Fetch raw historical data from API"""
        url = f"{BASE_URL}/v6/line/{self.ticker}/01/all.js"
        
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            # Extract JSON from JavaScript response
            data = self._extract_json_from_js(response.text)
            if not data:
                return []
            
            return self._process_stock_data_all(data)
            
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return []
    
    def _fetch_ticker_info(self) -> Dict[str, Any]:
        """Fetch ticker information"""
        # Basic info structure similar to yfinance
        info = {
            'symbol': self.ticker,
            'shortName': self.ticker.split('_')[-1],
            'longName': self.ticker,
            'currency': 'CNY',
            'market': 'cn',
            'exchange': 'SSE' if self.ticker.startswith('6') else 'SZSE'
        }
        
        # Add HK market detection
        if self.ticker.startswith('hk_'):
            info.update({
                'currency': 'HKD',
                'market': 'hk', 
                'exchange': 'HKG'
            })
        
        return info
    
    def _fetch_news(self) -> List[Dict[str, Any]]:
        """Fetch news data"""
        url = f"{STOCK_PAGE_URL}/ajax/code/{self.ticker}/type/news/" # A股地址
        print(self.info)
        url = f"{BASE_URL}/basicapi/notice/pub?type=hk&code={self.info.get('shortName')}&classify=all&page=1&limit=15" # 港股
        headers = {**HEADERS, 'Referer': f"{BASE_URL}/176/{self.info.get('shortName')}/news.html"}
        # https://basic.10jqka.com.cn/176/HK2018/news.html
        try:
            response = self._session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            print(response.json())
            
            return response.json().get('data',[])
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news for {self.ticker}: {e}")
            return []
    
    def _apply_period_filter(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """Apply period filtering to dataframe"""
        if df.empty:
            return df
            
        end_date = df.index.max()
        
        # Calculate start date based on period
        if period == '1d':
            start_date = end_date - timedelta(days=1)
        elif period == '5d':
            start_date = end_date - timedelta(days=5)  
        elif period == '1mo':
            start_date = end_date - timedelta(days=30)
        elif period == '3mo':
            start_date = end_date - timedelta(days=90)
        elif period == '6mo':
            start_date = end_date - timedelta(days=180)
        elif period == '1y':
            start_date = end_date - timedelta(days=365)
        elif period == '2y':
            start_date = end_date - timedelta(days=730)
        elif period == '5y':
            start_date = end_date - timedelta(days=1825)
        elif period == '10y':
            start_date = end_date - timedelta(days=3650)
        elif period == 'ytd':
            start_date = datetime(end_date.year, 1, 1)
        else:  # max
            return df
        
        return df[df.index >= start_date]
    
    def _resample_data(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """Resample data to specified interval"""
        if df.empty or interval == '1d':
            return df
        
        # Map interval to pandas frequency
        freq_map = {
            '1m': '1min', '2m': '2min', '5m': '5min',
            '15m': '15min', '30m': '30min', '60m': '60min',
            '90m': '90min', '1h': '1H', '1wk': '1W', 
            '1mo': '1M', '3mo': '3M'
        }
        
        freq = freq_map.get(interval)
        if not freq:
            logger.warning(f"Unsupported interval: {interval}")
            return df
        
        # Apply resampling with OHLCV aggregation
        resampled = df.resample(freq).agg({
            'Open': 'first',
            'High': 'max', 
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        return resampled
    
    def _extract_json_from_js(self, js_str: str) -> Optional[Dict]:
        """Extract JSON data from JavaScript string"""
        try:
            start_idx = js_str.find('(') + 1
            end_idx = js_str.rfind(')')
            
            if start_idx >= end_idx:
                raise ValueError("No valid JSON wrapper found")
                
            return json.loads(js_str[start_idx:end_idx])
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"JSON extraction error: {e}")
            return None
    
    def _process_stock_data_all(self, data: Dict[str, str]) -> List[Dict[str, Any]]:
        """Process market data, combining dates, prices and volumes"""
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
        
        # Combine data
        min_length = min(len(prices), len(dates), len(volumes))
        return [
            {
                "t": dates[i],
                "v": int(volumes[i]) if volumes[i] else 0,
                **prices[i]
            }
            for i in range(min_length)
        ]
    
    def _parse_hot_news(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse hot news from HTML content"""
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
                p_tag = summary_dd.find('p')
                hot_news.append({
                    'type': '热点新闻',
                    'publish_date': date_span.text.strip('[]'),
                    'title': title_link.get('title', ''),
                    'href': title_link.get('href', ''),
                    'summary': p_tag.text.strip() if p_tag else '',
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
                        'title': a_tag.get('title', ''),
                        'href': a_tag.get('href', ''),
                        'summary': a_tag.text.replace(date_span.text, '').strip(),
                    })
        
        return hot_news
    
    def _parse_report_links(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse research report links from HTML content"""
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
                    'title': title_link.get('title', ''),
                    'href': title_link.get('href', ''),
                })
        
        return reports
    
    def _parse_announcements(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse company announcements from HTML content"""
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
                    'title': a_tag.get('title', ''),
                    'href': a_tag.get('href', ''),
                })
        
        return announcements

def download(tickers: Union[str, List[str]], 
             period: str = "1mo",
             interval: str = "1d", 
             start: Optional[Union[str, datetime]] = None,
             end: Optional[Union[str, datetime]] = None,
             group_by: str = 'ticker',
             auto_adjust: bool = True,
             prepost: bool = False,
             threads: bool = True,
             proxy: Optional[str] = None) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Download historical data for ticker(s) - yfinance compatible function
    
    Args:
        tickers: Ticker symbol(s) 
        period: Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        interval: Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo  
        start: Start date string (YYYY-MM-DD) or datetime object
        end: End date string (YYYY-MM-DD) or datetime object
        group_by: Group by 'ticker' or 'column'
        auto_adjust: Automatically adjust prices
        prepost: Include pre and post market data
        threads: Use threading for multiple tickers
        proxy: Proxy server URL
        
    Returns:
        DataFrame or dict of DataFrames with historical data
    """
    # Convert single ticker to list
    if isinstance(tickers, str):
        tickers = [tickers]
    
    results = {}
    
    # Download data for each ticker
    for ticker_symbol in tickers:
        ticker = Ticker(ticker_symbol)
        data = ticker.history(
            period=period,
            interval=interval, 
            start=start,
            end=end,
            auto_adjust=auto_adjust,
            prepost=prepost
        )
        results[ticker_symbol] = data
    
    # Return format based on number of tickers and group_by
    if len(tickers) == 1:
        return results[tickers[0]]
    
    if group_by == 'ticker':
        return results
    else:
        # Group by column - combine all tickers into multi-index DataFrame
        combined = pd.concat(results, names=['Ticker', 'Date'])
        return combined.unstack(level=0)

# Backward compatibility - keep original TxhApi class
class TxhApi:
    """Legacy API class for backward compatibility"""
    
    def __init__(self, code: str):
        self.ticker = Ticker(code)
    
    def get_stock_transaction_all(self) -> List[Dict[str, Any]]:
        """Get all historical transaction data"""
        return self.ticker._fetch_historical_data()
    
    def get_stock_transaction_last(self) -> Optional[Dict[str, Any]]:
        """Get last transaction data (placeholder)"""
        # This would need additional implementation
        return None
    
    def get_stock_news_list(self) -> List[Dict[str, Any]]:
        """Get news list"""
        return self.ticker.news

if __name__ == '__main__':
    # Example usage similar to yfinance
    
    # Single ticker
    ticker = Ticker('hk_HK2018')
    
    # Get historical data
    hist = ticker.history(period='1mo', interval='1d')
    print(f"History data shape: {hist.shape}")
    print(hist.tail())
    
    # Get ticker info
    print(f"Ticker info: {ticker.info}")
    
    # Get news
    news = ticker.news
    print(f"Found {len(news)} news items")
    
    # Multi-ticker download
    data = download(['hk_HK0004', 'hk_HK0005'], period='1mo')
    print(f"Downloaded data for {len(data)} tickers")