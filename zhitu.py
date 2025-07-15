#
# 参考API文档： https://www.zhituapi.com/hsstockapi.html
#
import requests
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import json
import glob
import appdirs

logger = logging.getLogger(__name__)

def setup_logging(level=logging.DEBUG):
    """配置日志记录，同时输出到控制台和文件"""
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "zhitu_api.log")
    print(f"日志文件路径: {log_file}")
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # 创建并配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 添加文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

class ZhituApi:
    # 类级别缓存字典，结构：{token: {'stocks': data, 'stock_indexs': data, 'timestamp': float}}
    _CACHE = {}
    CACHE_TTL = 3600 * 24 * 7  # 7天缓存有效期

    # 新增缓存路径配置
    # 修改为使用appdirs获取跨平台缓存目录
    CACHE_DIR = os.path.join(appdirs.user_cache_dir(), "zhitu_api")
    CACHE_VERSION = "v1"  # 缓存版本控制


    def __init__(self, token):
        self.token = token
        # 创建缓存目录
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        # 清理过期缓存
        self._clean_old_cache()
        
        # 优先尝试内存缓存
        cache_data = self._CACHE.get(token)
        if cache_data and (time.time() - cache_data['timestamp']) < self.CACHE_TTL:
            self._init_from_cache(cache_data)
            return

        # 尝试加载磁盘缓存
        disk_cache = self._load_cache_from_disk()
        if disk_cache and (time.time() - disk_cache['timestamp']) < self.CACHE_TTL:
            self._init_from_cache(disk_cache)
            # 更新内存缓存
            self._CACHE[token] = disk_cache
            logger.debug("从磁盘加载缓存数据")
            return

        # 缓存失效时重新加载
        self.stocks = {}
        self.stock_indexs = {}
        new_cache = {
            'timestamp': time.time(),
            'stocks': self.stocks,
            'stock_indexs': self.stock_indexs
        }

        try:
            # 加载股票数据
            url = f'https://api.zhituapi.com/hs/list/all?token={self.token}'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.stocks = {x['dm'][:-3]: x for x in data}
            new_cache['stocks'] = self.stocks

            # 加载指数数据
            url = f'http://api.zhituapi.com/hz/list/hszs?token={self.token}'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.stock_indexs = {x['dm']: x for x in data}
            new_cache['stock_indexs'] = self.stock_indexs

            # 更新缓存
            self._CACHE[token] = new_cache
        except Exception as e:
            if cache_data:  # 降级到旧缓存
                self.stocks = cache_data.get('stocks', {})
                self.stock_indexs = cache_data.get('stock_indexs', {})
                logger.warning(f"使用缓存数据（加载失败：{str(e)}）")
            else:
                raise
    
    def _clean_old_cache(self):
        """清理过期的磁盘缓存"""
        cache_files = glob.glob(os.path.join(self.CACHE_DIR, "cache_*.json"))
        for cache_file in cache_files:
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
            except FileNotFoundError:
                # 文件在遍历后被其他进程删除，跳过
                logger.warning(f"缓存文件已不存在: {cache_file}")
                continue
            except json.JSONDecodeError:
                # JSON 解析失败，可能文件损坏，删除文件
                logger.warning(f"缓存文件 JSON 解析失败，将删除该文件: {cache_file}")
                try:
                    os.remove(cache_file)
                except Exception as rm_e:
                    logger.error(f"删除损坏缓存文件失败: {cache_file}, 错误: {str(rm_e)}")
                continue
            except Exception as e:
                logger.warning(f"读取缓存文件失败: {cache_file}, 错误: {str(e)}")
                continue

            if cache_data.get('version') == self.CACHE_VERSION:
                timestamp = cache_data.get('timestamp', 0)
                if time.time() - timestamp > self.CACHE_TTL:
                    try:
                        os.remove(cache_file)
                        logger.debug(f"清理过期缓存文件: {cache_file}")
                    except Exception as rm_e:
                        logger.error(f"删除过期缓存文件失败: {cache_file}, 错误: {str(rm_e)}")

    def _init_from_cache(self, cache_data):
        """从缓存数据初始化实例"""
        self.stocks = cache_data.get('stocks', {})
        self.stock_indexs = cache_data.get('stock_indexs', {})
        logger.debug(f"缓存加载成功 | 股票数: {len(self.stocks)} | 指数数: {len(self.stock_indexs)}")

    def _load_cache_from_disk(self):
        """从磁盘加载缓存"""
        cache_path = self._get_cache_path()
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    disk_cache = json.load(f)
                    if disk_cache.get('version') == self.CACHE_VERSION:
                        return disk_cache
                    logger.warning("磁盘缓存版本不匹配，忽略旧版本缓存")
        except Exception as e:
            logger.warning(f"磁盘缓存加载失败: {str(e)}")
        return None

    def _get_cache_path(self):
        """生成带token的缓存文件名"""
        filename = os.path.join(self.CACHE_DIR, f"cache_{self.token}.json")
        logger.debug(f"缓存路径: {filename}")
        return filename
    
    def _create_variable_dict(self, mapping):
        """创建字段映射字典（内部工具方法）
        
        Args:
            mapping (list): 字段映射元组列表，格式为 [(原字段, 新字段, 注释), ...]
            
        Returns:
            dict: 生成的字段映射字典 {原字段: 新字段}
            
        Raises:
            ValueError: 如果映射表格式不正确
        """
        if not all(isinstance(item, tuple) and len(item) == 3 for item in mapping):
            raise ValueError("映射表格式不正确，应为 [(原字段, 新字段, 注释), ...]")
        print("字段映射关系：")
        for original, new, comment in mapping:
            print(f"{original:6} → {new:28} # {comment}")
        return {item[0]: item[1] for item in mapping}
    

    def _send_request(self, url, params=None):
        """统一处理HTTP GET请求
        
        Args:
            url (str): 请求目标URL
            params (dict, optional): 请求参数，默认自动添加token
            
        Returns:
            dict/list: 解析后的JSON响应数据
            
        Raises:
            RequestException: 网络请求失败时抛出
            JSONDecodeError: 响应内容无法解析为JSON时抛出
        """
        params = params or {}
        params.setdefault('token', self.token)
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败 | URL: {url} | 错误: {str(e)}")
            raise

    def _transform_data(self, data, variable_mapping):
        """统一转换API响应数据结构
        
        Args:
            data (dict/list): 原始API响应数据
            variable_mapping (list): 字段映射配置表
            
        Returns:
            dict/list: 转换后的结构化数据，保留原始数据结构类型
            
        Example:
            输入dict返回dict，输入list返回包含转换后dict的list
        """
        variable_dict = self._create_variable_dict(variable_mapping)
        if isinstance(data, list):
            # 将列表中的每个字典按照字段映射表进行转换
            return pd.DataFrame([{variable_dict.get(k, k): v for k, v in item.items()} for item in data])
        # 将字典按照字段映射表进行转换
        return {variable_dict.get(k, k): v for k, v in data.items()}

    def refresh_cache(self):
        """强制刷新缓存"""
        if self.token in self._CACHE:
            del self._CACHE[self.token]
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            os.remove(cache_path)
        # 重新加载数据
        self.__init__(self.token)

    def get_stock_instrument(self, code):
        '''
        获取股票信息
        '''
        variable_mapping = [
            # 证券标识信息
            ('ei', 'exchange_code', '交易所/市场代码（如：SH/SZ等）'),
            ('ii', 'instrument_id', '证券代码（不含市场前缀）'),
            ('name', 'security_name', '证券全称'),
            ('od', 'ipo_date', '首次公开发行日期（格式：yyyy-MM-dd）'),

            # 价格相关指标
            ('pc', 'previous_close', '前一交易日收盘价'),
            ('up', 'upper_limit', '当日涨停价（价格上限）'),
            ('dp', 'lower_limit', '当日跌停价（价格下限）'),
            ('pk', 'price_tick', '最小价格变动单位（最小报价单位）'),

            # 股本数据（特别说明字段别名）
            ('fv', 'float_shares', '流通股本（单位：股，注意：旧版客户端可能显示为FloatVolumn）'),

            # 交易状态（含复杂状态说明）
            ('is', 'suspension_status', '停牌状态, <=0 : 正常交易（其中-1表示复牌状态,>=1 : 停牌天数（数值表示持续停牌的天数）')
        ]

        url = f'http://api.zhituapi.com/hs/instrument/{self.stocks[code]["dm"]}?token={self.token}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)

    # 修改各方法示例（以get_real_transcation为例）
    def get_real_transcation(self, code):
        """获取实时交易数据
         
        Args:
            code (str): 6位数字股票代码，如 '600000'
            
        Returns:
            dict: 结构化实时行情数据，包含价格、成交量、财务指标等字段
            
        Raises:
            KeyError: 股票代码不存在时抛出
            RequestException: API请求失败时抛出
        """
        if code not in self.stocks:
            logger.error(f"股票代码 {code} 不存在")
            raise KeyError(f"股票代码 {code} 不存在")
        variable_mapping = [
            # 市场实时数据
            ('fm', 'five_minute_change_percent', '五分钟涨跌幅（%）'),
            ('h', 'high_price', '当日最高价（元）'),
            ('hs', 'turnover_rate', '换手率（%）'),
            ('lb', 'volume_ratio', '量比（当前成交量/过去5日平均成交量）'),
            ('l', 'low_price', '当日最低价（元）'),
            
            # 市值相关
            ('lt', 'circulating_market_cap', '流通市值（元）'),
            ('sz', 'total_market_cap', '总市值（元）'),
            
            # 价格数据
            ('o', 'open_price', '当日开盘价（元）'),
            ('p', 'current_price', '当前最新价格（元）'),
            ('yc', 'previous_close', '昨日收盘价（元）'),
            
            # 涨跌相关指标
            ('pc', 'change_percent', '当日涨跌幅（%）'),
            ('ud', 'price_change_amount', '涨跌额（当前价-昨日收盘价）'),
            ('zf', 'amplitude', '振幅（(最高价-最低价)/昨日收盘价）%'),
            ('zs', 'price_change_speed', '涨速（每分钟价格变动百分比）'),
            
            # 成交量数据
            ('v', 'volume', '成交量（手，1手=100股）'),
            ('cje', 'turnover_amount', '成交额（元）'),
            
            # 财务指标
            ('pe', 'pe_ratio', '市盈率（总市值/预估全年净利润）'),
            ('sjl', 'pb_ratio', '市净率（总市值/净资产）'),
            
            # 时间维度涨跌幅
            ('zdf60', 'sixty_day_change_percent', '60日涨跌幅（%）'),
            ('zdfnc', 'year_to_date_change_percent', '年初至今涨跌幅（%）'),
            
            # 时间戳
            ('t', 'update_time', '数据更新时间（格式：yyyy-MM-dd HH:mm:ss）')
        ]
        
        url = f'https://api.zhituapi.com/hs/real/ssjy/{code}?token={self.token}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)

    def _validate_params(self, period, adjust):
        """校验周期和复权参数"""
        valid_periods = ['1', '5', '15', '30', '60', 'd', 'w', 'm', 'y']
        valid_adjusts = ['n', 'f', 'b', 'fr', 'br']
        if period not in valid_periods:
            raise ValueError("无效周期参数")
        if adjust not in valid_adjusts:
            raise ValueError("无效复权参数")

    def get_latest_transcation(self, code, period='d', adjust='n'):
        """获取近期交易数据
        
        Args:
            code (str): 6位数字股票代码
            period (str): 数据周期，可选 ['1','5','15','30','60','d','w','m','y']
            adjust (str): 复权方式，可选 ['n','f','b','fr','br']
            
        Returns:
            pd.DataFrame: 近期交易数据表格，包含时间、OHLC价格、成交量等字段
            
        Raises:
            ValueError: 参数不合法时抛出
        """
        self._validate_params(period, adjust)
            
        # 字段映射表
        variable_mapping = [
            # 时间相关
            ('t', 'trade_time', '交易时间（格式：yyyy-MM-dd HH:mm:ss）'),
            
            # 价格数据
            ('o', 'open_price', '当日开盘价'),
            ('h', 'high_price', '当日最高价'),
            ('l', 'low_price', '当日最低价'),
            ('c', 'close_price', '当日收盘价'),
            ('pc', 'previous_close', '前一个交易日收盘价'),
            
            # 交易量数据
            ('v', 'volume', '成交量（单位：股/手，需确认具体单位）'),
            ('a', 'amount', '成交额（单位：元）'),
            
            # 交易状态
            ('sf', 'is_suspended', '停牌状态（1表示停牌，0表示正常交易）')
        ]

        url = f"https://api.zhituapi.com/hs/latest/{self.stocks[code]['dm']}/{period}/{adjust}?token={self.token}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_history_transcation(self, code, start_date='20240601', end_date='20250430', period='d', adjust='n'):
        """获取历史交易数据
        
        Args:
            code (str): 6位数字股票代码
            start_date (str): 开始日期，格式YYYYMMDD
            end_date (str): 结束日期，格式YYYYMMDD
            period (str): 数据周期，同get_latest_transcation
            adjust (str): 复权方式，同get_latest_transcation
            
        Returns:
            pd.DataFrame: 历史交易数据表格，结构同近期数据
            
        Note:
            日期范围最大支持1年，超出范围会自动截断
        """
        self._validate_params(period, adjust)
        try:
            start = datetime.strptime(start_date, '%Y%m%d')
            end = datetime.strptime(end_date, '%Y%m%d')
            if end - start > timedelta(days=365):
                end = start + timedelta(days=365)
                end_date = end.strftime('%Y%m%d')
                logger.warning(f"日期范围超过1年，自动截断为 {start_date} 到 {end_date}")
        except ValueError:
            raise ValueError("日期格式错误，应为YYYYMMDD")

        variable_mapping = [
            # 时间相关
            ('t', 'trade_time', '交易时间（格式：yyyy-MM-dd HH:mm:ss）'),
            
            # 价格数据
            ('o', 'open_price', '当日开盘价'),
            ('h', 'high_price', '当日最高价'),
            ('l', 'low_price', '当日最低价'),
            ('c', 'close_price', '当日收盘价'),
            ('pc', 'previous_close', '前一个交易日收盘价'),
            
            # 交易量数据
            ('v', 'volume', '成交量（单位：股/手，需确认具体单位）'),
            ('a', 'amount', '成交额（单位：元）'),
            
            # 交易状态
            ('sf', 'is_suspended', '停牌状态（1表示停牌，0表示正常交易）')
        ]

        url = f'https://api.zhituapi.com/hs/history/{self.stocks[code]["dm"]}/{period}/{adjust}'
        params = {'st': start_date, 'et': end_date}
        data = self._send_request(url, params)
        return self._transform_data(data, variable_mapping)
    
    def get_real_index(self,index_code):
        '''
        获取实时指数数据
        
        Args:
            index_code (str): 指数代码（如：000001.SH）
            
        Returns:
            pd.DataFrame: 实时指数数据表格，包含指数代码、指数名称、指数值等字段
        '''
        variable_mapping = [
            # 核心价格数据
            ('p', 'price', '最新价/当前价（单位：元）'),
            ('o', 'open', '当日开盘价（单位：元）'),
            ('h', 'high', '当日最高价（单位：元）'),
            ('l', 'low', '当日最低价（单位：元）'),
            ('c', 'close', '收盘价（单位：元）'),
            
            # 历史价格基准
            ('yc', 'prev_close', '前交易日收盘价（单位：元）'),
            ('pc', 'prev_close', '前交易日收盘价（兼容字段，单位：元）'),
            
            # 成交量能数据
            ('v', 'volume', '成交量（单位：手）'),
            ('pv', 'pure_volume', '未经调整的原始成交量（单位：手）'),
            ('cje', 'turnover', '成交总额（单位：元）'),
            ('a', 'amount', '成交额（兼容字段，单位：元）'),
            
            # 涨跌相关指标
            ('ud', 'change_amount', '涨跌额（当前价-前收盘价，单位：元）'),
            ('pc', 'change_percent', '涨跌幅（单位：%，正数表示上涨）'),
            ('zf', 'amplitude', '振幅（(最高价-最低价)/前收盘价，单位：%）'),
            
            # 时间数据
            ('t', 'update_time', '时间戳')
        ]
        url = f'https://api.zhituapi.com/hz/real/ssjy/{index_code}?token={self.token}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_history_index(self,index_code,period):
        '''
        获取历史指数数据
        
        Args:
            index_code (str): 指数代码（如：000001.SH）
            
        Returns:
            pd.DataFrame: 历史指数数据表格，包含指数代码、指数名称、指数值等字段
        '''
        variable_mapping = [
            # 时间字段
            ('t', 'trade_time', '交易时间戳'),
            
            # 价格四要素
            ('o', 'open_price', '当日开盘价（单位：元，精确到小数点后2位）'),
            ('h', 'high_price',  '当日最高价（单位：元）'),
            ('l', 'low_price',  '当日最低价（单位：元）'),
            ('c', 'close_price', '当日收盘价（单位：元）'),
            
            # 基准价格
            ('pc', 'prev_close', '前收盘价（单位：元）'),
            
            # 量能指标
            ('v', 'volume',  '成交量'),
            ('a', 'turnover', '成交额')
        ]
        url = f'https://api.zhituapi.com/hz/latest/fsjy/{self.stock_indexs[index_code]["dm"]}/{period}?token={self.token}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)

if __name__ == "__main__":
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    setup_logging(level=logging.DEBUG)
    TOKEN = "0E1A565C-601A-4C8B-B4F4-B4AD402651E0"
    TOKEN = "666DCAEA-708B-48E2-A7A9-89F5352E7BAA"


    # 获取日期
    current_date = datetime.now()
    months_ago = current_date - relativedelta(months=2)
    end_date = current_date.strftime('%Y%m%d')
    start_date = months_ago.strftime('%Y%m%d')
    logger.debug(f'开始日期:{start_date}，结束日期:{end_date}')

    # 测试知图API
    api = ZhituApi(TOKEN)

    # 测试股票信息
    stock_code = '605268'
    logger.info(f'股票信息：\n{api.get_stock_instrument(stock_code)}')
    logger.info(f'实时交易数据：\n{api.get_real_transcation(stock_code)}')
    logger.info(f'最新交易数据：\n{api.get_latest_transcation(stock_code)}')
    logger.info(f'历史交易数据：\n{api.get_history_transcation(stock_code,start_date=start_date, end_date=end_date)}')

    # 测试指数信息
    index_code = '000001.SH'
    logger.info(f'指数实时数据：\n{api.get_real_index(index_code)}')
    logger.info(f'指数历史数据：\n{api.get_history_index(index_code,'d')}')
