
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