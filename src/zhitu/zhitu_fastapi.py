from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from starlette.routing import Mount
from zhitu.zhitu import ZhituApi,setup_logging
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional

# 初始化日志和API

TOKEN = "666DCAEA-708B-48E2-A7A9-89F5352E7BAA"
api = ZhituApi(TOKEN)

# Create your FastMCP server
mcp = FastMCP("MyServer")

@mcp.tool
def analyze_data(query: str) -> dict:
    """Analyze data based on the query."""
    return {"result": f"Analysis for: {query}"}

# Create the ASGI app from your MCP server
mcp_app = mcp.http_app(path='/mcp')


app = FastAPI(title="Zhitu Stock API", 
              description="知图股票数据API封装",
              version="1.0.0")
app.mount("/mcp-server", mcp_app)


@app.get("/stock/{code}/instrument")
async def get_stock_instrument(code: str):
    """获取股票基本信息"""
    try:
        return api.get_stock_instrument(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/stock/{code}/realtime")
async def get_real_transaction(code: str):
    """获取股票实时交易数据"""
    try:
        return api.get_real_transcation(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/stock/{code}/latest")
async def get_latest_transaction(
    code: str,
    period: str = 'd',
    adjust: str = 'n'
):
    """获取股票近期交易数据"""
    try:
        return api.get_latest_transcation(code, period, adjust)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/stock/{code}/history")
async def get_history_transaction(
    code: str,
    start_date: str,
    end_date: str,
    period: str = 'd',
    adjust: str = 'n'
):
    """获取股票历史交易数据"""
    try:
        # 设置默认日期范围(最近2个月)
        if not start_date or not end_date:
            current_date = datetime.now()
            months_ago = current_date - relativedelta(months=2)
            end_date = current_date.strftime('%Y%m%d')
            start_date = months_ago.strftime('%Y%m%d')
        
        return api.get_history_transcation(
            code, 
            start_date=start_date, 
            end_date=end_date,
            period=period,
            adjust=adjust
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/index/{code}/realtime")
async def get_real_index(code: str):
    """获取指数实时数据"""
    try:
        return api.get_real_index(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/index/{code}/history")
async def get_history_index(
    code: str,
    period: str = 'd'
):
    """获取指数历史数据"""
    try:
        return api.get_history_index(code, period)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    # import uvicorn
    # setup_logging('zhitu_fastapi.log',level=logging.DEBUG)
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    mcp.run(transport="sse")  # Run as MCP server