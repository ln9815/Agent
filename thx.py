import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime
import time
import re
import os
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class StockDataFetcher:
    def __init__(self, stock_market='', stock_code='HK2018'):
        """
        初始化股票数据获取器
        :param stock_code: 股票代码（港股格式如HK2018）
        """
        self.stock_code = stock_code.upper()
        self.stock_market = 'hk' if 'HK' in stock_code else stock_market
        self.base_url = f'https://stockpage.10jqka.com.cn/{stock_code}/'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
            'Referer': self.base_url
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def _get_page_content(self, url):
        """获取页面内容"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None
    
    def _parse_json_data(self, html_content, pattern):
        """从HTML中提取JSON数据"""
        match = re.search(pattern, html_content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                print("JSON解析错误")
            return None
        
    def get_realtime_transactions(self):
        """
        解析股票分时数据字符串
        格式：时分,现价,成交额,均价,成交量;时分,现价,成交额,均价,成交量;...
        
        参数:
            None
        
        返回:
            list: 包含多个字典的列表，每个字典格式为:
                {
                    'time': str,        # 时分 (HH:MM)
                    'current_price': float,  # 现价
                    'turnover': float,  # 成交额 (单位：元)
                    'avg_price': float, # 均价
                    'volume': int       # 成交量 (单位：手)
                }
        """
        logger.info(f"开始获取分时数据，股票代码: {self.stock_code}")
        url = f'https://d.10jqka.com.cn/v6/time/{self.stock_market}_{self.stock_code}/defer/last.js'
        content = self._get_page_content(url)
        if content is None:
            logger.error(f"获取分时数据失败，股票代码: {self.stock_code}")
            return None
        match = re.search(r'\{[\s\S]*\}', content)
        if match is None:
            logger.error(f"分时数据解析失败，股票代码: {self.stock_code}")
            return None
        data_json = json.loads(match.group())[f'{self.stock_market}_{self.stock_code}']
        logger.info(f"成功解析分时数据，股票代码: {self.stock_code}")

        result = []
        # 按分号分割每组数据
        groups = data_json['data'].split(';')
        
        for group in groups:
            # 跳过空组
            if not group.strip():
                continue
                
            # 按逗号分割组内数据
            parts = group.split(',')
            
            # 验证数据格式
            if len(parts) != 5:
                raise ValueError(f"无效数据格式: 每组应包含5个值，实际得到 {len(parts)} 个值: '{group}'")
            
            try:
                # 解析并转换各字段
                time_str = parts[0].strip()
                current_price = float(parts[1].strip())
                turnover = float(parts[2].strip())
                avg_price = float(parts[3].strip())
                volume = int(parts[4].strip())
                
                # 添加到结果列表
                result.append({
                    'time': time_str,
                    'current_price': current_price,
                    'turnover': turnover,
                    'avg_price': avg_price,
                    'volume': volume
                })
                
            except ValueError as e:
                logger.error(f"数据转换错误: '{group}' - {str(e)}")
        
        data_json['data'] = pd.DataFrame(result)
        return data_json
    
    def get_today_quotes(self):
        '''
        获取今日行情
        '''
        logger.info(f"开始获取今日行情，股票代码: {self.stock_code}")
        url = f'https://d.10jqka.com.cn/v6/line/{self.stock_market}_{self.stock_code}/01/defer/today.js'
        content = self._get_page_content(url)

        if content is None:
            logger.error(f"获取今日行情失败，股票代码: {self.stock_code}")
            return None

        match = re.search(r'\{[\s\S]*\}', content)
        if match is None:
            logger.error(f"今日行情数据解析失败，股票代码: {self.stock_code}")
            return None

        data_json = json.loads(match.group())[f'{self.stock_market}_{self.stock_code}']
        logger.info(f"成功解析今日行情数据，股票代码: {self.stock_code}")

        logger.info(data_json)

        return {
            "date": data_json["1"],
            "name":data_json["name"],
            "open": data_json["7"],
            "close": data_json["11"],
            # "previous_close": data_json["8"],
            "turnover": data_json["19"],
            "turnover_rate": data_json["1968584"],
            "high": data_json["8"],
            "low": data_json["9"],
            "volume": data_json["13"],
            }
    def get_all_data(self):
        logger.info(f"开始获取所有数据，股票代码: {self.stock_code}")
        url = f'https://d.10jqka.com.cn/v6/line/{self.stock_market}_{self.stock_code}/01/all.js'
        content = self._get_page_content(url)

        if content is None:
            logger.error(f"获取所有数据失败，股票代码: {self.stock_code}")
            return None

        match = re.search(r'\{[\s\S]*\}', content)
        if match is None:
            logger.error(f"所有数据数据解析失败，股票代码: {self.stock_code}")
            return None

        data_json = json.loads(match.group())
        logger.info(f"成功解析所有数据数据，股票代码: {self.stock_code}")

        logger.info(data_json)

        return data_json

# 使用示例
if __name__ == "__main__":
    fetcher = StockDataFetcher('HK2018')
    logging.basicConfig(level=logging.DEBUG)

    # print(fetcher.get_realtime_transactions())
    
    print(fetcher.get_all_data())