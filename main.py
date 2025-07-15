# main.py

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
from typing import List, Optional, Any, Tuple, Dict, Union, Callable
from pytdx.params import TDXParams
from pydantic import BaseModel
from typing_extensions import Annotated
import pandas as pd
import base64

app = FastAPI(
    title="港股行情查询 API",
    description="基于 pytdx.hq.TdxHq_API 实现的港股行情数据查询接口，包括K线、分时、成交明细、公司公告等。",
    version="1.0.0",
)


def get_api(exhq=False):
    working_servers = [
                        {'ip': '220.178.55.86', 'port': 7709},
                        {'ip': '220.178.55.71', 'port': 7709},
                        {'ip': '202.100.166.21', 'port': 7709},
                        {'ip': '58.63.254.247', 'port': 7709},  # 备用
                    ]
    # 尝试连接可用服务器
    print(f"🔍 [DEBUG] 创建通达信API实例...")
    api = TdxExHq_API() if exhq else TdxHq_API()
    print(f"🔍 [DEBUG] 开始尝试连接服务器...")

    for i, server in enumerate(working_servers):
        try:
            api = TdxExHq_API() if exhq else TdxHq_API()  # 每次创建新实例
            result = api.connect(server['ip'], server['port'])
            if result:
                return api
            api.disconnect()  # 断开无效连接
        except Exception as e:
            print(f"⚠️ 服务器 {server['ip']}:{server['port']} 连接失败: {e}")
            continue

    print("❌ 所有通达信服务器连接失败")
    return None

# 快速依赖注入，保证每次请求连接断开后自动释放资源
# 删除以下全局变量代码：
# api = get_api()
# if api is None:
#     raise HTTPException(400, detail="无法连接到任何通达信服务器")

class SecurityQuotesRequest(BaseModel):
    all_stock: List[List[Union[int, str]]]

class SecurityBarsRequest(BaseModel):
    category: int
    market: int
    code: str
    start: int
    count: int

class GetIndexBarsRequest(BaseModel):
    category: int
    market: int
    code: str
    start: int
    count: int

class MinuteTimeDataRequest(BaseModel):
    market: int
    code: str

class HistoryMinuteTimeDataRequest(BaseModel):
    market: int
    code: str
    date: str

class TransactionDataRequest(BaseModel):
    market: int
    code: str
    start: int
    count: int

class HistoryTransactionDataRequest(BaseModel):
    market: int
    code: str
    start: int
    count: int
    date: str

class XdxrInfoRequest(BaseModel):
    market: int
    code: str

class FinanceInfoRequest(BaseModel):
    market: int
    code: str

class BlockInfoMetaRequest(BaseModel):
    blockfile: str

class BlockInfoRequest(BaseModel):
    blockfile: str
    start: int
    size: int

class ReportFileRequest(BaseModel):
    market: int  # 新增 market 字段
    code: str    # 新增 code 字段
    filename: str
    offset: int  # 原 offset 参数改名为 start
    length: int  # 新增 length 参数

class ReportFileSizeRequest(BaseModel):
    filename: str
    filesize: int = 0

# 将 pandas DataFrame 转换为 JSON 便于返回
def df_to_json(data: Any) -> Dict:
    if isinstance(data, pd.DataFrame):
        return data.to_dict(orient='records')
    else:
        return data

# 🧩 接口：获取个股实时报价
@app.post("/security_quotes")
async def security_quotes(
    request: SecurityQuotesRequest,
    api: TdxHq_API = Depends(get_api)
):
    try:
        result = api.get_security_quotes(request.all_stock)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📈 接口：获取个股K线行情（如日线、分钟线等）
@app.post("/security_bars")
async def security_bars(request: SecurityBarsRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_security_bars(request.category, request.market, request.code, request.start, request.count)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📊 接口：获取指数K线行情（如恒生指数等）
@app.post("/index_bars")
async def index_bars(request: GetIndexBarsRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_index_bars(request.category, request.market, request.code, request.start, request.count)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 🕒 接口：获取个股当日分时行情
@app.post("/minute_time")
async def minute_time(request: MinuteTimeDataRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_minute_time_data(request.market, request.code)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 🕓 接口：获取个股历史分时行情
@app.post("/history_minute_time")
async def history_minute_time(request: HistoryMinuteTimeDataRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_history_minute_time_data(request.market, request.code, request.date)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📜 接口：获取个股基本信息（如总股本、行业等）
@app.post("/security_count")
async def security_count(request: dict, api: TdxHq_API = Depends(get_api)):
    try:
        market = int(request.get('market'))
        count = api.get_security_count(market)
        return JSONResponse({"security_count": count})
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/security_list")
async def security_list(request: dict, api: TdxHq_API = Depends(get_api)):
    try:
        market = int(request.get('market'))
        start = int(request.get('start'))
        result = api.get_security_list(market, start)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📦 接口：获取除权除息信息
@app.post("/xdxr_info")
async def xdxr_info(request: XdxrInfoRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_xdxr_info(request.market, request.code)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📄 接口：获取公司公告分类
@app.post("/company_info_category")
async def company_info_category(request: XdxrInfoRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_company_info_category(request.market, request.code)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 🗃 接口：获取公告文件内容（按段分块）
@app.post("/company_info_content")
async def company_info_content(request: ReportFileRequest, api: TdxHq_API = Depends(get_api)):
    try:
        # 修正参数顺序和命名
        result = api.get_company_info_content(request.market, request.code, request.filename, request.offset, request.length)
        return JSONResponse({"filedata": base64.b64encode(result).decode('utf8') if result else None})
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 💰 接口：获取个股财务报告
@app.post("/finance_info")
async def finance_info(request: FinanceInfoRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_finance_info(request.market, request.code)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📁 接口：获取板块信息
@app.post("/block_info_meta")
async def block_info_meta(request: BlockInfoMetaRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_block_info_meta(request.blockfile)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/block_info")
async def block_info(request: BlockInfoRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_block_info(request.blockfile, request.start, request.size)
        return JSONResponse(df_to_json(result))
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 📂 接口：获取报告/公告文件（全量下载，带进度支持）
@app.post("/report_file")
async def report_file(request: ReportFileRequest, api: TdxHq_API = Depends(get_api)):
    try:
        result = api.get_report_file(request.filename, request.offset)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.post("/report_file_by_size")
async def report_file_by_size(request: ReportFileSizeRequest, api: TdxHq_API = Depends(get_api)):
    try:
        data = api.get_report_file_by_size(request.filename, request.filesize, None)
        file_data = base64.b64encode(data).decode("utf-8")
        return JSONResponse({"file_base64": file_data})
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 🔁 接口：心跳保持连接
@app.post("/heartbeat")
async def heartbeat(api: TdxHq_API = Depends(get_api)):
    try:
        api.do_heartbeat()
        return {"status": "alive", "last_ack_time": api.last_ack_time}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

# 💻 启动方式示例
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)