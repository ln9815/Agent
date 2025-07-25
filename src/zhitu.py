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
from src.indicators import add_technical_indicators
from src.util import setup_logging


logger = logging.getLogger(__name__)


class ZhituApi:
    # 类级别缓存字典，结构：{token: {'stocks': data, 'stock_indexs': data, 'timestamp': float}}
    _CACHE = {}
    CACHE_TTL = 3600 * 24 * 7  # 7天缓存有效期

    # 新增缓存路径配置
    # 修改为使用appdirs获取跨平台缓存目录
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    CACHE_VERSION = "v1"  # 缓存版本控制

    # 在类属性部分增加缓存保存方法
    def _save_cache_to_disk(self, cache_data):
        """将缓存数据保存到磁盘"""
        cache_path = self._get_cache_path()
        try:
            cache_data['version'] = self.CACHE_VERSION  # 添加版本信息
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
            logger.debug(f"缓存数据已保存到: {cache_path}")
        except Exception as e:
            logger.error(f"缓存保存失败: {str(e)}")

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
            url = f'https://api.zhituapi.com/hs/list/all'
            data = self._send_request(url)
            self.stocks = {x['dm'][:-3]: x for x in data}
            new_cache['stocks'] = self.stocks

            # 加载指数数据
            url = f'http://api.zhituapi.com/hz/list/hszs'
            data = self._send_request(url)
            self.stock_indexs = {x['dm']: x for x in data}
            new_cache['stock_indexs'] = self.stock_indexs

            # 更新缓存并保存到磁盘
            self._CACHE[token] = new_cache
            self._save_cache_to_disk(new_cache)  # 新增保存到磁盘的操作

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
        # print("字段映射关系：")
        # for original, new, comment in mapping:
        #     print(f"{original:6} → {new:28} # {comment}")
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
            response = requests.get(url, params=params, timeout=30)
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
        variable_dict = self._create_variable_dict(variable_mapping) if isinstance(variable_mapping,tuple) else variable_mapping
        if isinstance(data, pd.DataFrame):
            data = data.to_dict('records')
        if isinstance(data, list):
            # 将列表中的每个字典按照字段映射表进行转换
            return [{variable_dict.get(k, k): v for k, v in item.items()} for item in data]
        # 将字典按照字段映射表进行转换
        return {variable_dict.get(k, k): v for k, v in data.items()}

    def refresh_cache(self):
        """强制刷新缓存"""
        if self.token in self._CACHE:
            del self._CACHE[self.token]
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            os.remove(cache_path)
        # 重新加载数据并保存新缓存
        self.__init__(self.token)  # 这会触发新的缓存保存

    
    def _validate_params(self, period, adjust):
        """校验周期和复权参数"""
        valid_periods = ['1', '5', '15', '30', '60', 'd', 'w', 'm', 'y']
        valid_adjusts = ['n', 'f', 'b', 'fr', 'br']
        if period not in valid_periods:
            raise ValueError("无效周期参数")
        if adjust not in valid_adjusts:
            raise ValueError("无效复权参数")

    def get_stock_code_name(self, code_or_name):
        '''
        获取股票代码和名称
        '''
        stocks = [(k,v['mc']) for k, v in self.stocks.items()]

        result = next((item for item in stocks if item[0] == code_or_name), None)
        if result:
            return {'code':result[0], 'name':result[1]}
        result = next((item for item in stocks if item[1] == code_or_name), None)
        if result:
            return {'code':result[0], 'name':result[1]}
        raise ValueError(f"未找到股票代码或名称为 {code_or_name} 的股票")

    def get_stock_basic_info(self, code):
        '''
        获取股票基本信息
        '''
        variable_mapping = {
            'ei': '交易所代码（如: SH/SZ/HK）',
            'ii': '股票代码（不含交易所后缀）',
            'name': '股票全称',
            'od': '上市日期（YYYY-MM-DD格式）',
            'pc': '前收盘价（单位：元）',
            'up': '涨停价（单位：元）',
            'dp': '跌停价（单位：元）',
            'fv': '流通股本（单位：万股）',
            'tv': '总股本（单位：万股）',
            'pk': '最小价格变动单位（单位：元）',
            'is': '停牌状态（0:正常 -1:复牌 >0:停牌天数）'
        }
        url = f'http://api.zhituapi.com/hs/instrument/{self.stocks[code]["dm"]}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)

    # 修改各方法示例（以get_real_transcation为例）
    def get_stock_real_transcation(self, code):
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

        variable_mapping = {
            # 实时价格指标
            'p': '当前价格（元）',
            'h': '当日最高价（元）',
            'l': '当日最低价（元）',
            'o': '当日开盘价（元）',
            'yc': '昨日收盘价（元）',
            
            # 涨跌相关指标
            'ud': '涨跌额（当前价-昨收，单位：元）',
            'pc': '涨跌幅（(当前价-昨收)/昨收*100%）',
            'zs': '涨速（最近1分钟价格变化率%）',
            'zf': '振幅（(最高价-最低价)/昨收*100%）',
            'fm': '五分钟涨跌幅（%）',
            'zdf60': '60日涨跌幅（%）',
            'zdfnc': '年初至今涨跌幅（%）',
            
            # 量能指标
            'v': '成交量（单位：手，1手=100股）',
            'cje': '成交额（单位：元）',
            'lb': '量比（当前成交量/过去5日同期平均成交量*100%）',
            'hs': '换手率（成交量/流通股本*100%）',
            
            # 市值指标
            'sz': '总市值（单位：元）',
            'lt': '流通市值（单位：元）',
            
            # 估值指标
            'pe': '动态市盈率（总市值/预估全年净利润）',
            'sjl': '市净率（总市值/净资产）',
            
            # 时间信息
            't': '更新时间（格式：yyyy-MM-ddHH:mm:ss）'
        }
        
        # url = f'https://api.zhituapi.com/hs/real/ssjy/{self.stocks[code]['dm']}'
        url = f'https://api.zhituapi.com/hs/real/ssjy/{code}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)


    def get_stock_latest_transcation(self, code, period='d'):
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
        adjust='n'
        self._validate_params(period, adjust)
            
        variable_mapping = {
            't': '交易时间（格式：YYYY-MM-DD HH:MM:SS）',
            'o': '开盘价（单位：元）',
            'h': '最高价（单位：元）',
            'l': '最低价（单位：元）',
            'c': '收盘价（单位：元）',
            'v': '成交量（单位：手，1手=100股）',
            'a': '成交额（单位：元）',
            'pc': '前收盘价（单位：元）',
            'sf': '停牌标志（1:停牌 0:正常交易）'
        }

        url = f"https://api.zhituapi.com/hs/latest/{self.stocks[code]['dm']}/{period}/{adjust}"
        # url = f"https://api.zhituapi.com/hs/real/time/股票代码?token=token证书"
        data = self._send_request(url)
        data_with_indicator = add_technical_indicators(data)
        return self._transform_data(data_with_indicator,variable_mapping)
    
    def get_stock_history_transcation(self, code, start_date, end_date, period='d', adjust='n'):
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
        # try:
        #     start = datetime.strptime(start_date, '%Y%m%d')
        #     end = datetime.strptime(end_date, '%Y%m%d')
        #     if end - start > timedelta(days=365):
        #         end = start + timedelta(days=365)
        #         end_date = end.strftime('%Y%m%d')
        #         logger.warning(f"日期范围超过1年，自动截断为 {start_date} 到 {end_date}")
        # except ValueError:
        #     raise ValueError("日期格式错误，应为YYYYMMDD")

        variable_mapping = {
            't': '交易时间（格式：YYYY-MM-DD HH:MM:SS）',
            'o': '开盘价（单位：元）',
            'h': '最高价（单位：元）',
            'l': '最低价（单位：元）',
            'c': '收盘价（单位：元）',
            'v': '成交量（单位：手，1手=100股）',
            'a': '成交额（单位：元）',
            'pc': '前收盘价（单位：元）',
            'sf': '停牌标志（1:停牌 0:正常交易）'
        }

        url = f'https://api.zhituapi.com/hs/history/{self.stocks[code]["dm"]}/{period}/{adjust}'
        params = {'st': start_date, 'et': end_date}
        data = self._send_request(url, params)
        data_with_indicator = add_technical_indicators(data)
        return self._transform_data(data_with_indicator,variable_mapping)
    
    def get_index_real_transcation(self,index_code):
        '''
        获取实时指数数据
        
        Args:
            index_code (str): 指数代码（如：000001.SH）
            
        Returns:
            pd.DataFrame: 实时指数数据表格，包含指数代码、指数名称、指数值等字段
        '''
        variable_mapping = {
            # 价格数据
            'p': '最新价',
            'o': '开盘价',
            'h': '最高价',
            'l': '最低价',
            'yc': '前收盘价',
            'c': '收盘价',
            'pc': '前收盘价',
            
            # 成交量数据
            'cje': '成交总额(元)',
            'v': '成交总量(手)',
            'pv': '原始成交总量',
            'a': '成交额(元)',
            
            # 涨跌数据
            'ud': '涨跌额',
            'pc': '涨跌幅(%)',
            'zf': '振幅(%)',
            
            # 时间数据
            't': '更新时间/交易时间'
        }
        url = f'https://api.zhituapi.com/hz/real/ssjy/{index_code}'
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_index_latest_transaction(self, code, period='5'):
        '''
        获取新分时交易
        
        Args:
            code (str): 指数代码（如：000001.SH）
            period (str): 数据周期，可选 ['5','15','30','60']
            
        Returns:
            pd.DataFrame: 新分时交易数据表格，包含指数代码、指数名称、指数值等字段
        '''
        variable_mapping = {
            't': '交易时间（格式：YYYY-MM-DD HH:MM:SS）',
            'o': '开盘价（单位：元）',
            'h': '最高价（单位：元）',
            'l': '最低价（单位：元）',
            'c': '收盘价（单位：元）',
            'v': '成交量（单位：手，1手=100股）',
            'a': '成交额（单位：元）',
            'pc': '前收盘价（单位：元）'
        }
        url = f"https://api.zhituapi.com/hz/latest/fsjy/{self.stock_indexs[code]['dm']}/{period}"
        data = self._send_request(url)
        data_with_indicator = add_technical_indicators(data)
        return self._transform_data(data_with_indicator,variable_mapping)

    
    def get_index_history_transaction(self, code, start_date, end_date, period='d'):
        '''
        获取历史指数数据
        
        Args:
            code (str): 指数代码（如：000001.SH）
            
        Returns:
            pd.DataFrame: 历史指数数据表格，包含指数代码、指数名称、指数值等字段
        '''
        variable_mapping = {
            't': '交易时间（格式：YYYY-MM-DD HH:MM:SS）',
            'o': '开盘价（单位：元）',
            'h': '最高价（单位：元）',
            'l': '最低价（单位：元）',
            'c': '收盘价（单位：元）',
            'v': '成交量（单位：手，1手=100股）',
            'a': '成交额（单位：元）',
            'pc': '前收盘价（单位：元）'
        }
        logging.debug(f'start date: {start_date}, end date: {end_date}, period: {period}')
        url = f'https://api.zhituapi.com/hz/history/fsjy/{self.stock_indexs[code]["dm"]}/{period}?st={start_date}&et={end_date}'
        data = self._send_request(url)
        logger.debug(f'获取指数历史数据：\n{pd.DataFrame(data).tail(5)}')
        data_with_indicator = add_technical_indicators(data)
        return self._transform_data(data_with_indicator,variable_mapping)

    def get_companny_finance_index(self,code):
        '''
        获取公司财务指标数据
        
        Args:
            code (str): 股票代码（如：605268）
            
        Returns:
            pd.DataFrame: 公司财务指标数据表格，包含指标名称、指标值等字段
        '''
        variable_mapping = {
            # 每股指标
            'tbmg': '摊薄每股收益(元)',
            'jqmg': '加权每股收益(元)',
            'mgsy': '每股收益_调整后(元)',
            'kfmg': '扣除非经常性损益后的每股收益(元)',
            'mgjz': '每股净资产_调整前(元)',
            'mgjzad': '每股净资产_调整后(元)',
            'mgjy': '每股经营性现金流(元)',
            'mggjj': '每股资本公积金(元)',
            'mgwly': '每股未分配利润(元)',

            # 利润率指标
            'zclr': '总资产利润率(%)',
            'zylr': '主营业务利润率(%)',
            'zzlr': '总资产净利润率(%)',
            'cblr': '成本费用利润率(%)',
            'yylr': '营业利润率(%)',
            'zycb': '主营业务成本率(%)',
            'xsjl': '销售净利率(%)',
            'gbbc': '股本报酬率(%)',
            'jzbc': '净资产报酬率(%)',
            'zcbc': '资产报酬率(%)',
            'xsml': '销售毛利率(%)',
            'xxbz': '三项费用比重',
            'fzy': '非主营比重',
            'zybz': '主营利润比重',
            'gxff': '股息发放率(%)',
            'tzsy': '投资收益率(%)',

            # 利润相关
            'zyyw': '主营业务利润(元)',
            'jzsy': '净资产收益率(%)',
            'jqjz': '加权净资产收益率(%)',
            'kflr': '扣除非经常性损益后的净利润(元)',

            # 增长率指标
            'zysr': '主营业务收入增长率(%)',
            'jlzz': '净利润增长率(%)',
            'jzzz': '净资产增长率(%)',
            'zzzz': '总资产增长率(%)',

            # 周转率指标
            'yszz': '应收账款周转率(次)',
            'yszzt': '应收账款周转天数(天)',
            'chzz': '存货周转天数(天)',
            'chzzl': '存货周转率(次)',
            'gzzz': '固定资产周转率(次)',
            'zzzzl': '总资产周转率(次)',
            'zzzzt': '总资产周转天数(天)',
            'ldzz': '流动资产周转率(次)',
            'ldzzt': '流动资产周转天数(天)',
            'gdzz': '股东权益周转率(次)',

            # 偿债能力
            'ldbl': '流动比率',
            'sdbl': '速动比率',
            'xjbl': '现金比率(%)',
            'lxzf': '利息支付倍数',
            'zjbl': '长期债务与营运资金比率(%)',
            'gdqy': '股东权益比率(%)',
            'cqfz': '长期负债比率(%)',
            'gdgd': '股东权益与固定资产比率(%)',
            'fzqy': '负债与所有者权益比率(%)',
            'zczjbl': '长期资产与长期资金比率(%)',
            'zblv': '资本化比率(%)',
            'gdzcjz': '固定资产净值率(%)',
            'zbgdh': '资本固定化比率(%)',
            'cqbl': '产权比率(%)',
            'qxjzb': '清算价值比率(%)',
            'gdzcbz': '固定资产比重(%)',
            'zcfzl': '资产负债率(%)',

            # 其他财务数据
            'zzc': '总资产(元)',
            'jyxj': '经营现金净流量对销售收入比率(%)',
            'zcjyxj': '资产的经营现金流量回报率(%)',
            'jylrb': '经营现金净流量与净利润的比率(%)',
            'jyfzl': '经营现金净流量对负债比率(%)',
            'xjlbl': '现金流量比率(%)',

            # 投资相关
            'dqgptz': '短期股票投资(元)',
            'dqzctz': '短期债券投资(元)',
            'dqjytz': '短期其它经营性投资(元)',
            'qcgptz': '长期股票投资(元)',
            'cqzqtz': '长期债券投资(元)',
            'cqjyxtz': '长期其它经营性投资(元)',

            # 应收款项明细
            'yszk1': '1年以内应收帐款(元)',
            'yszk12': '1-2年以内应收帐款(元)',
            'yszk23': '2-3年以内应收帐款(元)',
            'yszk3': '3年以内应收帐款(元)',
            'yfhk1': '1年以内预付货款(元)',
            'yfhk12': '1-2年以内预付货款(元)',
            'yfhk23': '2-3年以内预付货款(元)',
            'yfhk3': '3年以内预付货款(元)',
            'ysk1': '1年以内其它应收款(元)',
            'ysk12': '1-2年以内其它应收款(元)',
            'ysk23': '2-3年以内其它应收款(元)',
            'ysk3': '3年以内其它应收款(元)'
        }
        url = f"https://api.zhituapi.com/hs/gs/cwzb/{code}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_companny_cash_follow(self,code):
        '''
        获取公司现金流量指标数据
        
        Args:
            code (str): 股票代码（如：605268）
            
        Returns:
            pd.DataFrame: 公司现金流量指标数据表格，包含指标名称、指标值等字段
        '''
        variable_mapping = {
            'date': '截止日期yyyy-MM-dd',
            'jyin': '经营活动现金流入小计（万元）',
            'jyout': '经营活动现金流出小计（万元）',
            'jyfinal': '经营活动产生的现金流量净额（万元）',
            'tzin': '投资活动现金流入小计（万元）',
            'tzout': '投资活动现金流出小计（万元）',
            'tzfinal': '投资活动产生的现金流量净额（万元）',
            'czin': '籌资活动现金流入小计（万元）',
            'czout': '籌资活动现金流出小计（万元）',
            'czfinal': '籌资活动产生的现金流量净额（万元）',
            'hl': '汇率变动对现金及现金等价物的影响（万元）',
            'cashinc': '现金及现金等价物净增加额（万元）',
            'cashs': '期初现金及现金等价物余额（万元）',
            'cashe': '期末现金及现金等价物余额（万元）'
        }
    
        url = f"https://api.zhituapi.com/hs/gs/jdxj/{code}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_companny_profit(self,code):
        '''
        
        Args:
            code (str): 股票代码（如：605268）
            
        Returns:
            pd.DataFrame: 公司利润指标数据表格，包含指标名称、指标值等字段
        '''
        variable_mapping ={
            'date': '截止日期yyyy-MM-dd',
            'income': '营业收入（万元）',
            'expend': '营业支出（万元）',
            'profit': '营业利润（万元）',
            'totalp': '利润总额（万元）',
            'reprofit': '净利润（万元）',
            'basege': '基本每股收益(元/股)',
            'ettege': '稀释每股收益(元/股)',
            'otherp': '其他综合收益（万元）',
            'totalcp': '综合收益总额（万元）'
        }
        url = f"https://api.zhituapi.com/hs/gs/jdlr/{code}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_company_dividends_in_recent_years(self,code):
        '''
        获取公司最近几年的分红数据
        
        Args:
            code (str): 股票代码（如：605268）
            
        Returns:
            pd.DataFrame: 公司最近几年的分红数据表格，包含指标名称、指标值等字段
        '''
        variable_mapping ={
            'sdate': '公告日期yyyy-MM-dd',
            'give': '每10股送股(单位：股)',
            'change': '每10股转增(单位：股)',
            'send': '每10股派息(税前，单位：元)',
            'line': '进度',
            'cdate': '除权除息日yyyy-MM-dd',
            'edate': '股权登记日yyyy-MM-dd',
            'hdate': '红股上市日yyyy-MM-dd'
        }
        url = f"https://api.zhituapi.com/hs/gs/jnff/{code}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)
    
    def get_companny_introduction(self,code):
        '''
        获取公司介绍数据
        
        Args:
            code (str): 股票代码（如：605268）
            
        Returns:
            pd.DataFrame: 公司介绍数据表格，包含指标名称、指标值等字段
        '''
        variable_mapping ={
            'name': '公司名称',
            'ename': '公司英文名称',
            'market': '上市市场',
            'idea': '概念及板块，多个概念由英文逗号分隔',
            'ldate': '上市日期，格式yyyy-MM-dd',
            'sprice': '发行价格（元）',
            'principal': '主承销商',
            'rdate': '成立日期',
            'rprice': '注册资本',
            'instype': '机构类型',
            'organ': '组织形式',
            'secre': '董事会秘书',
            'phone': '公司电话',
            'sphone': '董秘电话',
            'fax': '公司传真',
            'sfax': '董秘传真',
            'email': '公司电子邮箱',
            'semail': '董秘电子邮箱',
            'site': '公司网站',
            'post': '邮政编码',
            'infosite': '信息披露网址',
            'oname': '证券简称更名历史',
            'addr': '注册地址',
            'oaddr': '办公地址',
            'desc': '公司简介',
            'bscope': '经营范围',
            'printype': '承销方式',
            'referrer': '上市推荐人',
            'putype': '发行方式',
            'pe': '发行市盈率（按发行后总股本）',
            'firgu': '首发前总股本（万股）',
            'lastgu': '首发后总股本（万股）',
            'realgu': '实际发行量（万股）',
            'planm': '预计募集资金（万元）',
            'realm': '实际募集资金合计（万元）',
            'pubfee': '发行费用总额（万元）',
            'collect': '募集资金净额（万元）',
            'signfee': '承销费用（万元）',
            'pdate': '招股公告日'
        }
        url = f"https://api.zhituapi.com/hs/gs/gsjj/{code}"
        data = self._send_request(url)
        return self._transform_data(data, variable_mapping)

if __name__ == "__main__":
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    from dotenv import load_dotenv

    setup_logging('zhitu.log')

    load_dotenv()
    TOKEN = os.getenv('ZHITU_TOKEN')

    # 获取日期
    current_date = datetime.now()
    months_ago = datetime(current_date.year,current_date.month,1) - relativedelta(months=3)
    end_date = current_date.strftime('%Y%m%d')
    start_date = months_ago.strftime('%Y%m%d')
    logger.debug(f'开始日期:{start_date}，结束日期:{end_date}')

    # 测试知图API
    api = ZhituApi(TOKEN)
    # logger.info(api.stock_indexs)

    # 测试股票信息
    stock_code = '000938'
    # data = api.get_stock_basic_info(stock_code)
    # logger.debug(data)
    # logger.info(f'股票信息：\n{api.get_stock_basic_info(stock_code)}')
    logger.info(f'实时交易数据：\n{api.get_stock_real_transcation(stock_code)}')
    # data = api.get_stock_real_transcation(stock_code)
    # logger.debug(data)
    data = api.get_stock_latest_transcation(stock_code,period='15')
    logger.debug(data)
    # logger.info(f'最新交易数据：\n{pd.DataFrame(data).tail(5)}')
    # data = api.get_stock_history_transcation(stock_code,start_date=start_date, end_date=end_date,period='d')
    # logger.debug(data)
    # logger.info(f'历史交易数据：\n{pd.DataFrame(data).tail(5)}')

    # 测试指数信息
    index_code = '000001.SH'
    # data = api.get_index_real_transcation(index_code)
    # logger.debug(data)
    # logger.info(f'指数实时数据：\n{api.get_index_real_transcation(index_code)}')
    # data = api.get_index_latest_transaction(index_code)
    # logger.debug(data)
    # logger.info(f'指数最新分时数据：\n{pd.DataFrame(data).tail(5)}')
    # data = api.get_index_history_transaction(index_code,start_date=start_date,end_date=end_date,period='y')
    # logger.debug(data)
    # logger.info(f'指数历史数据：\n{pd.DataFrame(data).tail(5)}')

    # 测试股票代码和名称转换
    # logger.info(api.get_stock_code_name('中国宝安'))
    # logger.info(api.get_stock_code_name('002701'))
    # logger.info(api.get_stock_code_name('好股票'))

    # 测试公司相关信息
    # stock_code = '605268'
    # logger.info(api.get_companny_introduction(stock_code))
    # logger.info(api.get_companny_profit(stock_code))
    # logger.info(api.get_companny_cash_follow(stock_code))
    # logger.info(api.get_company_dividends_in_recent_years(stock_code))
    # logger.info(api.get_companny_finance_index(stock_code))
