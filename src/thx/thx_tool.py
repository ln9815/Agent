import pandas as pd
import requests
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from tool.ta import caculate_ta, resample_df
from thx.thx_helper import extract_json_from_js, process_stock_data_all,process_stock_data_last
from thx.thx_helper import parse_hot_news,parse_report_links,parse_announcements
from thx.thx_helper import convert_datetime


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


class ThxApi:
    """同花顺API客户端类"""
    
    def __init__(self, code: str):
        self.full_code = self._normalize_stock_code(code)
        self.makert,self.code = self.full_code.split('_')[0],self.full_code.split('_')[-1]
        logger.info(f"标准化股票代码: {self.full_code},市场代码: {self.makert}, 股票代码:{self.code}")
        self.headers = {
            **HEADERS,
            'Referer': f"{STOCK_PAGE_URL}/{self.full_code}/"
        }
    
    def _normalize_stock_code(self, code: str) -> str:
        """标准化股票代码格式"""
        code = code.upper().strip()

         # 如果已经有前缀，直接返回
        if '_' in code:
            return code
        elif code.startswith('HK'):
            return f'hk_{code}'
        elif code[0] in ('0', '3', '6', '8') and len(code) == 6:
            return f'hs_{code}'
        else:
            raise ValueError("股票代码格式错误,仅支持A股和港股.")
    
    def _make_request(self, url: str, timeout: int = 10, headers: Dict[str, str] = {},**argv) -> Optional[Dict]:
        """发送HTTP请求并提取JSON数据"""
        try:
            common_header = self.headers.copy()
            if headers:
                common_header.update(headers)
            response = requests.get(url, headers=common_header, timeout=timeout,**argv)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return None
    
    def _get_stock_latest_info(self) -> Dict[str, Any]:
        """获取股票最新信息"""
        from thx.thx_helper import STOCK_VAR_MAP

        url = f'{BASE_URL}/v6/realhead/{self.full_code}/defer/last.js'
        response = self._make_request(url)
        data = extract_json_from_js(response.text)['items']
        parsed_data = { v: data[k] for k, v in STOCK_VAR_MAP.items()}
        return parsed_data
    

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

                    df = pd.DataFrame(all_data)
                    df['date'] = df['date'].apply(convert_datetime)
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
            df['publish_date'] = df['publish_date'].apply(convert_datetime)
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
        from thx.thx_helper import parse_financial_data
        code = self.code.split('_')[-1] if '_' in self.code else self.code
        url = f'{STOCK_PAGE_URL}/{code}/'
        response = self._make_request(url)
        html_content = response.text
        
        if html_content:
            financial_data = parse_financial_data(html_content)
            return financial_data
        return {}
    
    def makert(self):
        '''获取A股大盘交易评级'''
        def level_name(score):
            if(score < 2.5):
                return '大盘风险极大，请勿参与'
            elif (score >= 2.5 and score < 4):
                return '大盘风险较大，请谨慎参与'
            elif (score >= 4 and score < 6):
                return '大盘震荡，适当参与'
            elif (score >= 6 and score < 8):
                return '大盘走势良好，积极参与'
            elif (score >= 8):
                return '大盘走势极好，积极参与'

        url = 'https://q.10jqka.com.cn/api.php?t=indexflash&'
        cookies = {'v': 'A6eYRyoggzYYLQe6to35ccgYMNBxLHsO1QD_gnkUwzZdaMkagfwLXuXQj9SK'}
        hd = {'Referer': 'https://q.10jqka.com.cn/','host':'q.10jqka.com.cn'}
        response = self._make_request(url,headers=hd,cookies=cookies)
        data = response.json()
        return {
            '大盘评分(满分:10)':data['dppj_data'],
            '大盘评级':level_name(data['dppj_data']),
            '股票数(涨)':data['zdfb_data']['znum'],
            '股票数(跌)':data['zdfb_data']['dnum'],
        }
    
    def basic_info(self):
        '''获取股票基本信息'''
        parsed_data = self._get_stock_latest_info()
        financial_data = self._get_financial_data()
        parsed_data.update(financial_data)  
        return parsed_data
    
    def news(self,count=30):
        """获取股票新闻列表"""
        if self.makert.startswith('hs'):
            return self._get_stock_news_list_v1(count)
        elif self.makert.startswith('hk'):
            return self._get_stock_news_list_v2(count)
        else:
            return []
    
    def last(self,period='5m'):
        """获取股票最新交易数据"""
        url = f"{BASE_URL}/v6/time/{self.full_code}/defer/last.js"
        response = self._make_request(url)
        data = extract_json_from_js(response.text)
        all_data = process_stock_data_last(data[self.full_code])

        df = pd.DataFrame(all_data)
        df_resampled = resample_df(df, period,self.makert)
        df_indicator = caculate_ta(df_resampled)

        return df_indicator.to_dict(orient='records')
    
    def history(self,period='d',count='90'):
        """获取股票所有历史交易数据"""
        url = f"{BASE_URL}/v6/line/{self.full_code}/01/all.js"
        respnse = self._make_request(url)
        data = extract_json_from_js(respnse.text)
 
        all_data = process_stock_data_all(data)
        df = pd.DataFrame(all_data)
        df_resampled = resample_df(df, period,self.makert)
        df_indicator = caculate_ta(df_resampled)
        df_indicator = df_indicator.tail(count)

        return df_indicator.to_dict(orient='records')

def main():
    """主函数示例"""
    # try:
    from tool.util import setup_logging
    setup_logging(log_file='txh.log')
    
    # 测试不同的股票代码格式
    test_codes = [
        # 'HK2018',
        'HK0981',
        '600519',
        # '000001'
    ]
    
    for stock_code in test_codes:
        logger.info(f"开始处理股票代码: {stock_code}")
        
        api = ThxApi(stock_code)

        # 获取大盘信息
        # market_info = api.makert()
        # logger.info(f'获取到大盘信息:\n{market_info}')

        # 获取个股基本信息
        info = api.basic_info()
        logger.info(f'获取到基本信息:\n{info}')
        
        # 获取新闻
        news_list = api.news()
        logger.info(f'获取到新闻 {len(news_list)} 条.\n{pd.DataFrame(news_list).tail(10)}')
        
        # 获取最新交易数据
        latest_data = api.last('1m')
        logger.info(f'获取到最新数据 {len(latest_data)} 条记录:\n{pd.DataFrame(latest_data).tail(10)}')
        
        # 获取所有历史数据
        all_data = api.history('d',90)
        logger.info(f"获取到历史数据{len(all_data)} 条记录:\n{pd.DataFrame(all_data).tail(10)}")

if __name__ == '__main__':
    main()