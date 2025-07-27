import pandas as pd
from datetime import datetime, time
import requests
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
import pprint
from indicators import add_technical_indicators
from thx_helper import resample_with_trading_hours

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

from thx_helper import extract_json_from_js, process_stock_data_all, process_stock_data_last,parse_hot_news,parse_report_links,parse_announcements,resample_with_trading_hours



class ThxApi:
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
            return response
        except requests.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return None
    
    def get_stock_transaction_all(self) -> List[Dict[str, Any]]:
        """获取股票所有历史交易数据"""
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f"{BASE_URL}/v6/line/{self.code}/01/all.js"
        respnse = self._make_request(url)
        data = extract_json_from_js(respnse.text)
        
        if data:
            return process_stock_data_all(data)
        return []
    
    def get_stock_transaction_last(self) -> List[Dict[str, Any]]:
        """获取股票最新交易数据"""
        print(self.code)
        url = f"{BASE_URL}/v6/time/{self.code}/defer/last.js"
        response = self._make_request(url)
        data = extract_json_from_js(response.text)
        
        if data and self.code in data:
            return process_stock_data_last(data[self.code])
        return []
    
    def get_stock_latest_info(self) -> Dict[str, Any]:
        """获取股票最新信息"""
        # code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f'{BASE_URL}/v6/realhead/{self.code}/defer/last.js'

        response = self._make_request(url)
        data = extract_json_from_js(response.text)['items']
        from thx_helper import STOCK_VAR_MAP
        parsed_data = { v: data[k] for k, v in STOCK_VAR_MAP.items()}
        financial_data = self._get_financial_data()
        parsed_data.update(financial_data)  
        return parsed_data
    
    def get_stock_news_list(self,count=10) -> List[Dict[str, Any]]:
        """获取股票新闻列表"""
        if self.code.startswith('hs_'):
            return self._get_stock_news_list_v1(count)
        return self._get_stock_news_list_v2(count)
    
    def _get_stock_news_list_v2(self,count=10) -> List[Dict[str, Any]]:
        """获取股票新闻列表（版本2）"""

        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f"https://stockpage.10jqka.com.cn/{code}/quote/news/"

        try:
            response = self._make_request(url)

            # 使用正则表达式提取JSON部分
            pattern = r'var newsinfo=({.*?})(?=\s*$|\s*;)'
            match = re.search(pattern, response.text, re.DOTALL | re.MULTILINE)
            
            if match:
                json_str = match.group(1)
                try:
                    news_data = json.loads(json_str)
                    data = news_data.get('data', [])
                    all_data = data['mine'] + data['pub']
                    print(all_data)
                    logger.info(f"成功获取 {len(all_data)} 条新闻")

                    df = pd.DataFrame(all_data)
                    from thx_helper import format_date
                    df['date'] = df['date'].apply(format_date)
                    df['date'] = pd.to_datetime(df['date'])

                    df = df.sort_values(by='date', ascending=False)
                    df['summary'] = ''
                    df.rename(columns={'url': 'href'}, inplace=True)
                    df = df.head(count)[['date', 'title','summary','href']]
                    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                    
                    return df.to_dict(orient='records')
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
    def _get_stock_news_list_v1(self,count=10) -> List[Dict[str, Any]]:
        """Get news, reports and announcements for the stock."""
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f"{STOCK_PAGE_URL}/ajax/code/{code}/type/news/"
        
        try:
            response = self._make_request(url)
            html_content = response.text
            
            if not html_content:
                return []
            
            news_items = parse_hot_news(html_content)
            reports = parse_report_links(html_content)
            announcements = parse_announcements(html_content)
            all_items = news_items + reports + announcements

            df = pd.DataFrame(all_items)
            from thx_helper import format_date
            df['publish_date'] = df['publish_date'].apply(format_date)
            df['publish_date'] = pd.to_datetime(df['publish_date'])

            df = df.sort_values(by='publish_date', ascending=False)
            df = df.head(count)[['publish_date', 'title','summary','href']]
            df = df.rename(columns={'publish_date': 'date'})
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    
            return df.to_dict(orient='records')
        
        except requests.RequestException as e:
            logger.error(f"Failed to fetch news for {self.code}: {e}")
            return []
    def _get_financial_data(self) -> Dict[str, str]:
        """获取股票财务数据"""
        from thx_helper import parse_financial_data
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f'{STOCK_PAGE_URL}/{code}/'
        response = self._make_request(url)
        html_content = response.text
        
        
        if not html_content:
            return {}
        
        financial_data = parse_financial_data(html_content)
        return financial_data
    
    def basic_info(self):
        '''获取股票基本信息'''
        return self.get_stock_latest_info()
    def news(self,count=10):
        '''获取股票新闻'''
        return self.get_stock_news_list(count)
    def last(self,period='5m'):
        '''获取股票最新数据'''
        
        all_data = self.get_stock_transaction_last()
        df = pd.DataFrame(all_data)
        if period =='1m':
            df_resampled = df
        else:
            df_resampled = resample_with_trading_hours(df, period)
        df_resampled = df_resampled.sort_values(by='t', ascending=True)
        df_indicator = add_technical_indicators(df_resampled)

        return df_indicator.to_dict(orient='records')
    def history(self,period='d',count='90'):
        '''获取股票历史数据'''
        all_data = self.get_stock_transaction_all()
        df = pd.DataFrame(all_data)
        
        df_resampled = df
        # if period =='w':
        #     df_resampled = resample_with_trading_hours(df, 'w')
        # elif period =='m':
        df_resampled = resample_with_trading_hours(df, period)
        df_resampled = df_resampled.sort_values(by='t', ascending=True)
        df_indicator = add_technical_indicators(df_resampled)
        df_indicator = df_indicator.tail(count)

        return df_indicator.to_dict(orient='records')

def main():
    """主函数示例"""
    try:
        from util import setup_logging
        setup_logging(log_file='txh.log')
        
        # 测试不同的股票代码格式
        test_codes = [
            'HK2018',
            # 'HK0981',
            # '600519',
            # '000001'
        ]
        
        for stock_code in test_codes:
            logger.info(f"开始处理股票代码: {stock_code}")
            
            try:
                api = ThxApi(stock_code)
                # 获取最新信息
                basic_ = api.basic_info()
                if basic_:
                    logger.info(f'获取到最新信息:\n{pprint.pformat(basic_)}')
                else:
                    logger.warning(f"{stock_code} 未获取到最新信息")
                
                # 获取最新交易数据
                latest_data = api.last('5m')
                if latest_data:
                    logger.info(f'获取到最新数据 {len(latest_data)} 条记录:\n{pd.DataFrame(latest_data).tail(124)}')
                    
                else:
                    logger.warning(f"{stock_code} 未获取到最新数据")
                
                # 获取所有历史数据
                all_data = api.history('d',20)
                df_all = pd.DataFrame(all_data)
                print(f"获取到历史数据{len(df_all)} 条记录:\n{pd.DataFrame(all_data).tail(10)}")

                # 获取新闻列表
                try:
                    news_list = api.news()
                    if news_list:
                        logger.info(f'获取到新闻 {len(news_list)} 条.\n{pprint.pformat(news_list)}')
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