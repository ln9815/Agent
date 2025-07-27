
## Docker方式运行
```
# 构建镜像
docker build -t mcp-app .

# 删除旧容器
docker rm -f mymcp

# 运行容器
# 挂载目录 -v /share/CACHEDEV3_DATA/fs/App/Agent:/app
# 共享主机网络 --network host
docker run -d --name mymcp -v /share/CACHEDEV3_DATA/fs/App/Agent:/app --restart always --network host mcp-app

```

我需要用stramlit来展示一个股票的实时信息，用网页html格式现实。
用户输入股票代码，然后显示这个股票的实时行情，以及近1年日K图。
要求有日志功能，即使每步操作都有日志，包括用户输入的股票代码，以及获取到的实时行情数据。

API访问的TOKEN
<Token>
F7A19AE8-38E9-4F94-B189-6A9A161658D8
</>


股票基础信息：
<base_info>
PI地址：http://api.zhituapi.com/hs/instrument/股票代码（如000001.SZ）?token=token证书
描述：依据《股票列表》中的股票代码获取股票的基础信息
返回字段：
字段名称	数据类型	字段说明
ei	string	市场代码
ii	string	股票代码
name	string	股票名称
od	string	上市日期(股票IPO日期)
pc	float	前收盘价格
up	float	当日涨停价
dp	float	当日跌停价
fv	float	流通股本（注意，部分低等级客户端中此字段为FloatVolumn）
tv	float	总股本（注意，部分低等级客户端中此字段为FloatVolumn）
pk	float	最小价格变动单位
is	int	股票停牌状态(<=0:正常交易（-1:复牌）;>=1停牌天数;)
</base_info>

获取实时行情接口：
<real_transaction>
API地址：https://api.zhituapi.com/hs/real/ssjy/股票代码?token=token证书
描述：根据《股票列表》得到的股票代码获取实时交易数据（您可以理解为日线的最新数据）。
返回字段：
字段名称	数据类型	字段说明
fm	number	五分钟涨跌幅（%）
h	number	最高价（元）
hs	number	换手（%）
lb	number	量比（%）
l	number	最低价（元）
lt	number	流通市值（元）
o	number	开盘价（元）
pe	number	市盈率（动态，总市值除以预估全年净利润，例如当前公布一季度净利润1000万，则预估全年净利润4000万）
pc	number	涨跌幅（%）
p	number	当前价格（元）
sz	number	总市值（元）
cje	number	成交额（元）
ud	number	涨跌额（元）
v	number	成交量（手）
yc	number	昨日收盘价（元）
zf	number	振幅（%）
zs	number	涨速（%）
sjl	number	市净率
zdf60	number	60日涨跌幅（%）
zdfnc	number	年初至今涨跌幅（%）
t	string	更新时间yyyy-MM-ddHH:mm:ss
</real_transaction>

历史分时交易
<history_transaction>
API地址：https://api.zhituapi.com/hs/history/股票代码.市场（如000001.SZ）/分时级别(如d)/除权方式?token=token证书&st=开始时间(如20240601)&et=结束时间(如20250430)
描述：根据《股票列表》得到的股票代码和分时级别获取历史交易数据，交易时间升序。目前分时级别支持1分钟、5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为1、5、15、30、60、d、w、m、y，除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。
字段名称	数据类型	字段说明
t	string	交易时间
o	float	开盘价
h	float	最高价
l	float	最低价
c	float	收盘价
v	float	成交量
a	float	成交额
pc	float	前收盘价
sf	int	停牌 1停牌，0 不停牌
</history_transaction>


我需要用stramlit来展示一个股票的实时信息，用网页html格式现实。
用户输入股票代码，然后显示这个股票的实时行情（每1分钟的K线），以及近90天日K图。要显示股票基本信息，以及最新新闻。
要求有日志功能，记录用户输入的股票代码，以及行情数据。


可以从入下API中获取股票基本信息，新闻，实时数据，历史数据。
实时数据：5分钟的分时数据，历史数据：近90天的日期线数据。
返回的数据中，o为开盘价，h为最高价，l为最低价，c为收盘价，v为成交量，a为成交额，pc为前收盘价，sf为停牌状态。
<api>
from thx import ThxApi
class TxhApi:

    def __init__(self, code: str)
    def basic_info(self):
        '''获取股票基本信息'''
        返回值样例：
        {'市净率': '7.075',
        '市盈率': '17.020',
        '市盈率(动)': '21.197',
        '开盘': '1491.40',
        '总市值': '1827767800000.000',
        '成交量': '4191126.00',
        '成交额': '6140078700.00',
        '振幅': '2.575',
        '换手率': '1.080',
        '收盘': '1455.00',
        '昨收': '1491.50',
        '最低': '1453.00',
        '最高': '1491.40',
        '流通市值': '1827767800000.000',
        '涨幅': '-36.500',
        '涨幅(%)': '-2.45',
        '股票名称': '贵州茅台',
        '股票编码': '600519'}
    def news(self,count=10):
        '''获取股票新闻'''
        返回样例：
        [{'date': '2025-07-27', 'summary': '...', 'title': '茅台营销亮眼一“夏”，多线程加速三个转型'},
        {'date': '2025-07-26', 'summary': '...', 'title': '白酒激战，买还是卖'},
        {'date': '2025-07-26',
        'summary': '新任茅台技开公司党委书记、董事长王登发调研两家子公司',
        'title': '新任茅台技开公司党委书记、董事长王登发调研两家子公司'},]
    def last(self,period='5m'):
        '''获取股票实时数据'''
        返回数据样例：
        [{'t': Timestamp('2025-07-25 14:40:00'), 'o': 1455.3, 'h': 1466.054, 'l': 1465.877, 'c': 1455.11, 'v': 126752100.0, 'pc': 1456.67, 'PCT_CHANGE': -0.11, 'MA5': 1456.16, 'MA10': 1458.05, 'MA20': 1459.57, 'BOLL_MID': 1459.57, 'BOLL_UP': 1464.35, 'BOLL_DOWN': 1454.79, 'MACD': -2.3599999999999, 'MACD_SIGNAL': -2.19, 'MACD_HIST': -0.17, 'RSI': 30.17, 'K': -488.53, 'D': -529.04, 'J': -407.51}, ]
    def history(self,period='d',count='90'):
        '''获取股票历史数据'''
        返回数据样例：
        [{'t': '20250714', 'v': '2778094', 'o': 1430.0, 'c': 1423.6, 'h': 1434.98, 'l': 1421.6, 'pc': 1427.0, 'PCT_CHANGE': -0.24, 'MA5': 1422.42, 'MA10': 1417.53, 'MA20': 1410.7, 'BOLL_MID': 1410.7, 'BOLL_UP': 1431.28, 'BOLL_DOWN': 1390.12, 'MACD': -10.809999999999945, 'MACD_SIGNAL': -17.14, 'MACD_HIST': 6.33, 'RSI': 57.84, 'K': 51.91, 'D': 56.9, 'J': 41.93},]
</api>

2025-07-27 11:29:45,531 - urllib3.connectionpool - DEBUG [connectionpool.py:544] - https://stockpage.10jqka.com.cn:443 "GET /600519/ HTTP/1.1" 200 18448
警告: dt和dd标签数量不匹配
2025-07-27 11:29:45,557 - __main__ - INFO [thx.py:261] - 获取到最新信息:
{'市净率': '7.075',
 '市盈率': '17.020',
 '市盈率(动)': '21.197',
 '开盘': '1491.40',
 '总市值': '1827767800000.000',
 '成交量': '4191126.00',
 '成交额': '6140078700.00',
 '振幅': '2.575',
 '换手率': '1.080',
 '收盘': '1455.00',
 '昨收': '1491.50',
 '最低': '1453.00',
 '最高': '1491.40',
 '流通市值': '1827767800000.000',
 '涨幅': '-36.500',
 '涨幅(%)': '-2.45',
 '股票名称': '贵州茅台',
 '股票编码': '600519'}
hs_600519
2025-07-27 11:29:45,558 - urllib3.connectionpool - DEBUG [connectionpool.py:1049] - Starting new HTTPS connection (1): d.10jqka.com.cn:443
2025-07-27 11:29:45,795 - urllib3.connectionpool - DEBUG [connectionpool.py:544] - https://d.10jqka.com.cn:443 "GET /v6/time/hs_600519/defer/last.js HTTP/1.1" 200 None
/Users/victor/App/Agent/src/indicators.py:76: FutureWarning: A value is trying to be set on a copy of a DataFrame or Series through chained assignment using an inplace method.
The behavior will change in pandas 3.0. This inplace method will never work because the intermediate object on which we are setting values always behaves as a copy.

For example, when doing 'df[col].method(value, inplace=True)', try using 'df.method({col: value}, inplace=True)' or df[col] = df[col].method(value) instead, to perform the operation inplace on the original object.


  df['pc'].fillna(df['o'], inplace=True)
2025-07-27 11:29:45,810 - __main__ - INFO [thx.py:268] - 获取到最新数据 50 条记录
600519 最新数据:

                     t        o         h         l        c            v       pc  PCT_CHANGE      MA5  ...  BOLL_UP  BOLL_DOWN  MACD  MACD_SIGNAL  MACD_HIST    RSI       K       D       J
45 2025-07-25 14:40:00  1455.30  1466.054  1465.877  1455.11  126752100.0  1456.67       -0.11  1456.16  ...  1464.35    1454.79 -2.36        -2.19      -0.17  30.17 -488.53 -529.04 -407.51
46 2025-07-25 14:45:00  1454.69  1465.795  1465.633  1457.96  141815600.0  1455.11        0.20  1456.55  ...  1464.21    1454.65 -2.18        -2.19       0.01  43.41 -431.64 -496.57 -301.78
47 2025-07-25 14:50:00  1457.25  1465.612  1465.432  1455.96  126850900.0  1457.96       -0.14  1456.74  ...  1463.95    1454.27 -2.17        -2.19       0.02  38.46 -413.60 -468.91 -302.98
48 2025-07-25 14:55:00  1455.40  1465.344  1465.148  1455.11  173211300.0  1455.96       -0.06  1456.16  ...  1463.79    1453.79 -2.22        -2.19      -0.03  37.67 -424.64 -454.15 -365.62
49 2025-07-25 15:00:00  1455.00  1465.019  1465.019  1455.00   77647500.0  1455.11       -0.01  1455.83  ...  1463.56    1453.36 -2.23        -2.20      -0.03  37.41 -442.73 -450.34 -427.51

[5 rows x 21 columns]
2025-07-27 11:29:45,819 - urllib3.connectionpool - DEBUG [connectionpool.py:1049] - Starting new HTTPS connection (1): d.10jqka.com.cn:443
2025-07-27 11:29:46,005 - urllib3.connectionpool - DEBUG [connectionpool.py:544] - https://d.10jqka.com.cn:443 "GET /v6/line/hs_600519/01/all.js HTTP/1.1" 200 None
/Users/victor/App/Agent/src/indicators.py:76: FutureWarning: A value is trying to be set on a copy of a DataFrame or Series through chained assignment using an inplace method.
The behavior will change in pandas 3.0. This inplace method will never work because the intermediate object on which we are setting values always behaves as a copy.

For example, when doing 'df[col].method(value, inplace=True)', try using 'df.method({col: value}, inplace=True)' or df[col] = df[col].method(value) instead, to perform the operation inplace on the original object.


  df['pc'].fillna(df['o'], inplace=True)
600519 历史数据:

           t        o        h        l        c                                    v       pc  PCT_CHANGE      MA5  ...  BOLL_UP  BOLL_DOWN   MACD  MACD_SIGNAL  MACD_HIST    RSI      K      D      J
0 2025-05-26  1552.33  1568.27  1517.33  1522.83  19521531979464150902421537002708653  1551.31       -1.84  1538.53  ...  1613.38    1371.46  20.08        15.91       4.17  58.35  55.37  56.06  53.99
1 2025-06-02  1523.33  1530.93  1487.57  1494.33         1775213162656821859583123918  1522.83       -1.87  1532.93  ...  1611.46    1381.58  16.32        15.99       0.33  54.34  47.84  53.32  36.88
2 2025-06-09  1480.34  1495.33  1458.01  1458.44  28979182300809232136625023074495867  1494.33       -2.40  1520.75  ...  1608.82    1388.42  10.31        14.85      -4.54  49.92  31.98  46.21   3.52
3 2025-06-16  1458.33  1466.33  1373.51  1394.62  30492203089282499036159113254288787  1458.44       -4.38  1484.31  ...  1613.62    1378.38   0.39        11.96     -11.57  40.84  24.21  38.88  -5.13
4 2025-06-23  1392.33  1415.77  1377.51  1392.33  27231513076099245007234815812672331  1394.62       -0.16  1452.51  ...  1615.41    1375.09  -7.56         8.06     -15.62  25.06  18.71  32.16  -8.19
5 2025-06-30  1395.68  1428.00  1392.84  1409.52  36311514105007348602538249733045730  1392.33        1.23  1429.85  ...  1614.79    1376.27 -12.33         3.98     -16.31  31.74  17.40  27.24  -2.28
6 2025-07-07  1409.00  1431.89  1400.00  1410.70  19878192621825244126728766912385467  1409.52        0.08  1413.12  ...  1617.03    1370.71 -15.84         0.02     -15.86  33.79  16.68  23.72   2.60
7 2025-07-14  1410.71  1458.00  1410.40  1423.60  18673702774532387250357243352778094  1410.70        0.91  1406.15  ...  1618.26    1366.70 -17.38        -3.46     -13.92  42.60  17.97  21.80  10.31
8 2025-07-21  1420.98  1446.80  1408.32  1443.00  35405782128605231055441823412620331  1423.60        1.36  1415.83  ...  1618.56    1364.76 -16.84        -6.14     -10.70  36.34  23.87  22.49  26.63
9 2025-07-28  1444.00  1499.00  1440.68  1455.00         4211898450448438803644191126  1443.00        0.83  1428.36  ...  1617.57    1361.73 -15.26        -7.96      -7.30  38.93  33.17  26.05  47.41

[10 rows x 21 columns]
2025-07-27 11:29:46,122 - urllib3.connectionpool - DEBUG [connectionpool.py:1049] - Starting new HTTPS connection (1): stockpage.10jqka.com.cn:443
2025-07-27 11:29:46,161 - urllib3.connectionpool - DEBUG [connectionpool.py:544] - https://stockpage.10jqka.com.cn:443 "GET /ajax/code/600519/type/news/ HTTP/1.1" 200 2549
2025-07-27 11:29:46,173 - __main__ - INFO [thx.py:286] - 获取到新闻 10 条.
[{'date': '2025-07-27', 'summary': '...', 'title': '茅台营销亮眼一“夏”，多线程加速三个转型'},
 {'date': '2025-07-26', 'summary': '...', 'title': '白酒激战，买还是卖'},
 {'date': '2025-07-26',
  'summary': '新任茅台技开公司党委书记、董事长王登发调研两家子公司',
  'title': '新任茅台技开公司党委书记、董事长王登发调研两家子公司'},
 {'date': '2025-07-26',
  'summary': '茅台集团招聘堪称“神仙打架”：清华北大、海外名校毕业生争抢入职',
  'title': '茅台集团招聘堪称“神仙打架”：清华北大、海外名校毕业生争抢入职'},
 {'date': '2025-07-26', 'summary': 'i茅台再推新品', 'title': 'i茅台再推新品'},
 {'date': '2025-07-26',
  'summary': '贵州茅台：7月25日获融资买入8.17亿元',
  'title': '贵州茅台：7月25日获融资买入8.17亿元'},
 {'date': '2025-07-26', 'summary': '...', 'title': '技术进化，渠道净化，茅台的“闪电战”与“持久战”'},
 {'date': '2025-07-25',
  'summary': '白酒上市公司上半年业绩惨淡，营收普遍下降',
  'title': '白酒上市公司上半年业绩惨淡，营收普遍下降'},
 {'date': '2025-07-25',
  'summary': '贵州茅台：7月24日获融资买入3.70亿元，占当日流入资金比例为11.73%',
  'title': '贵州茅台：7月24日获融资买入3.70亿元，占当日流入资金比例为11.73%'},
 {'date': '2025-07-25',
  'summary': '周观点：白酒迎来情绪修复，大众品关注个股机会',
  'title': '周观点：白酒迎来情绪修复，大众品关注个股机会'}]