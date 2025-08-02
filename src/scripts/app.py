from fastmcp import FastMCP
from thx.thx_tool import ThxApi

mcp = FastMCP("My MCP Server")

@mcp.tool
async def stock_info(
    code: str
):
    """获取股票基本信息"""
    thx =ThxApi(code)
    return thx.basic_info()

@mcp.tool
async def stock_news(
    code: str,
    count: int = 10
):
    """获取股票新闻"""
    thx =ThxApi(code)
    return thx.news(count)

@mcp.tool
async def stock_last(
    code: str,
    period: str = '5m'
):
    """获取股票最新数据"""
    thx =ThxApi(code)
    return thx.last(period)

@mcp.tool
async def stock_history(
    code: str,
    period: str = 'd',
    count: int = 90
):
    """获取股票历史数据"""
    thx =ThxApi(code)
    return thx.history(period,count)

@mcp.tool
async def stock_market(
    code: str
):
    """获取股票市场数据"""
    thx =ThxApi(code)
    return thx.makert_hq()

def main():
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8010, path="/mcp")

if __name__ == "__main__":
    main()