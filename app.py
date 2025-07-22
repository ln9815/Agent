from fastmcp import FastMCP
from zhitu import ZhituApi,setup_logging
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('ZHITU_TOKEN')

api = ZhituApi(TOKEN)

mcp = FastMCP("My MCP Server")


@mcp.tool
async def get_stock_basic_info(code: str):
    """获取股票基本信息"""
    return api.get_stock_basic_info(code)

@mcp.tool
async def get_stock_real_transcation(code: str):
    """获取股票实时交易数据"""
    return api.get_stock_real_transcation(code)

@mcp.tool
async def get_stock_latest_transcation(
    code: str,
    period: str = 'd',
    adjust: str = 'n'
):
    """获取股票最新分时数据"""
    return api.get_stock_latest_transcation(code, period)

@mcp.tool
async def get_stock_history_transcation(
    code: str,
    start_date: str,
    end_date: str,
    period: str = 'd',
    adjust: str = 'n'
):
    """获取股票历史交易数据"""
    return api.get_stock_history_transcation(
        code, 
        start_date=start_date, 
        end_date=end_date,
        period=period,
        adjust=adjust
    )

@mcp.tool
async def get_stock_history_transcation_last_monthes(
    code: str,
    months: int = 6,
    period: str = 'd'
):
    """获取最近n个月的股票历史交易数据"""
    
    # 设置日期范围
    from dateutil.relativedelta import relativedelta
    from datetime import datetime
    current_date = datetime.now()
    first_day_of_current_month = datetime(current_date.year,current_date.month,1)
    months_ago = first_day_of_current_month - relativedelta(months=months)
    end_date = current_date.strftime('%Y%m%d')
    start_date = months_ago.strftime('%Y%m%d')

    return api.get_stock_history_transcation(
        code, 
        start_date=start_date, 
        end_date=end_date,
        period=period
    )
@mcp.tool
async def get_stock_news(
    code: str
):
    """获取个股新闻"""
    from thx import TxhApi
    api = TxhApi(code)
    return api.get_stock_news_list()
    
@mcp.tool
async def get_index_real_transcation(code: str):
    """获取指数实时数据"""
    return api.get_index_real_transcation(code)

@mcp.tool
async def get_index_latest_transaction(
    code: str,
    period: str = 'd'
):
    """获取指数最新分时数据"""
    return api.get_index_latest_transaction(code, period)

@mcp.tool
async def get_index_history_transaction(
    code: str,
    start_date: str,
    end_date: str,
    period: str = 'd'
):
    """获取指数历史分时数据"""
    return api.get_index_history_transaction(code, start_date, end_date, period)

@mcp.tool
async def get_index_history_transcation_last_monthes(
    code: str,
    months: int = 6,
    period: str = 'd'
):
    """获取最近n个月的指数历史交易数据"""
    # 设置日期范围
    from dateutil.relativedelta import relativedelta
    from datetime import datetime
    current_date = datetime.now()
    first_day_of_current_month = datetime(current_date.year,current_date.month,1)
    months_ago = first_day_of_current_month - relativedelta(months=months)
    end_date = current_date.strftime('%Y%m%d')
    start_date = months_ago.strftime('%Y%m%d')

    return api.get_index_history_transaction(
        code, 
        start_date=start_date, 
        end_date=end_date,
        period=period
    )
@mcp.tool
async def get_companny_introduction(
    code: str
):
    """获取公司介绍"""
    return api.get_companny_introduction(code)

@mcp.tool
async def get_companny_finance_index(
    code: str
):
    """获取公司财务指标"""
    return api.get_companny_finance_index(code)

@mcp.tool
async def get_companny_cash_follow(
    code: str
):
    """获取公司现金流指标"""
    return api.get_companny_cash_follow(code)

@mcp.tool
async def get_company_dividends_in_recent_years(
    code: str
):
    """获取公司最近几年分红数据"""
    return api.get_company_dividends_in_recent_years(code)

@mcp.tool
async def get_stock_code_name(
    code_or_name: str
):
    """获取股票代码和名称"""
    return api.get_stock_code_name(code_or_name)

if __name__ == "__main__":
    # mcp.run(transport='sse')
    setup_logging('mcp.log')
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8010, path="/mcp")
