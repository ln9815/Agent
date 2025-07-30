import streamlit as st
import requests
import json
import time
import queue
import threading
import logging
import re
import traceback
from dotenv import load_dotenv
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("DIFY_TOKEN","")

class WorkflowRunner:
    def __init__(self, stock_code):
        self.stock_code = stock_code
        self.text_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.finished = False
        self.error = None
        self.start_time = time.time()
        self.cancel_flag = False
        self.progress = 0
        self.last_update_time = time.time()

    def run(self):
        """在工作线程中执行工作流"""
        try:
            workflow_url = "http://szvkt.top:8880/v1/workflows/run"
            headers = {
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }

            data = {
                "inputs": {
                    "stock_code": self.stock_code
                },
                "response_mode": "streaming",
                "user": "streamlit_user"
            }

            full_text = ""
            node_count = 0
            completed_nodes = 0
            
            with requests.post(
                workflow_url,
                headers=headers,
                json=data,
                stream=True,
                timeout=300
            ) as response:
                
                if response.status_code != 200:
                    self.error = f"❌ 请求失败，状态码: {response.status_code}\n响应内容: {response.text}"
                    return
                
                buffer = ""
                for byte_chunk in response.iter_content(chunk_size=1024):
                    if self.cancel_flag:
                        self.log_queue.put("⏹️ 用户中断分析")
                        return
                    
                    if byte_chunk:
                        chunk = byte_chunk.decode('utf-8')
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_end = buffer.index("\n\n")
                            event_data = buffer[:event_end]
                            buffer = buffer[event_end + 2:]
                            
                            result = self.process_event_data(event_data)
                            if result:
                                event_type, text, log = result
                                
                                if event_type == "text_chunk":
                                    full_text += text
                                    self.text_queue.put(full_text)
                                
                                if log:
                                    self.log_queue.put(log)
                                
                                # 更新进度
                                if event_type == "node_started":
                                    node_count += 1
                                elif event_type == "node_finished":
                                    completed_nodes += 1
                                    self.progress = min(95, int((completed_nodes / max(1, node_count)) * 95))
            
            self.text_queue.put(full_text)  # 最终文本
            self.progress = 100
            elapsed = time.time() - self.start_time
            self.log_queue.put(f"🏁 工作流执行完成 | 总耗时: {elapsed:.1f}秒")
        
        except requests.exceptions.RequestException as e:
            self.error = f"❌ 请求失败: {str(e)}"
        except Exception as e:
            self.error = f"❌ 未知错误: {str(e)}"
            logger.exception("工作流执行异常")
        finally:
            self.finished = True

    def process_event_data(self, event_data):
        """处理单个SSE事件数据"""
        try:
            event_lines = event_data.split('\n')
            event_dict = {}
            
            for line in event_lines:
                if line.startswith('data:'):
                    json_str = line[5:].strip()
                    if json_str:
                        try:
                            event_dict = json.loads(json_str)
                        except json.JSONDecodeError:
                            logger.warning(f"JSON解析失败: {json_str}")
                            return None
            
            if not event_dict:
                return None
            
            event_type = event_dict.get('event')
            text_output = ""
            log_output = ""
            
            if event_type == 'workflow_started':
                workflow_id = event_dict['data'].get('id', '未知ID')
                log_output = f"⏱️ [工作流开始] ID: {workflow_id}"

            elif event_type == 'node_started':
                node_title = event_dict['data'].get('title', '未知节点')
                node_type = event_dict['data'].get('node_type', '未知类型')
                log_output = f"🚀 [节点开始] {node_title} (类型: {node_type})"

            elif event_type == 'text_chunk':
                text_output = event_dict['data'].get('text', '')

            elif event_type == 'node_finished':
                node_data = event_dict['data']
                node_id = node_data.get('node_id', '未知节点')
                status = node_data.get('status', 'unknown')
                
                if status == 'failed':
                    error_msg = node_data.get('error', '未知错误')
                    log_output = f"❌ [节点失败] {node_id} - 错误: {error_msg}"
                else:
                    log_output = f"✅ [节点完成] {node_id} - 状态: {status.upper()}"

            elif event_type == 'workflow_finished':
                wf_data = event_dict['data']
                status = wf_data.get('status', 'unknown').upper()
                elapsed_time = wf_data.get('elapsed_time', 0)
                log_output = f"🏁 [工作流完成] 状态: {status} | 耗时: {elapsed_time}秒"
            
            return event_type, text_output, log_output
        
        except Exception as e:
            logger.error(f"事件处理错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def cancel(self):
        """取消分析任务"""
        self.cancel_flag = True
        self.finished = True
        self.error = "分析已被用户中断"

# Streamlit UI
st.set_page_config(
    page_title="股票分析工作流",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 股票分析工作流")
st.markdown("""
使用此工具分析股票数据。输入股票代码，系统将执行分析工作流并实时显示结果。
""")

# 初始化会话状态
if 'runner' not in st.session_state:
    st.session_state.runner = None
if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = ""
if 'analysis_log' not in st.session_state:
    st.session_state.analysis_log = ""
if 'stock_code' not in st.session_state:
    st.session_state.stock_code = "HK2018"
if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0

# 用户输入
with st.sidebar:
    st.header("参数设置")
    stock_code = st.text_input("股票代码", st.session_state.stock_code, 
                             help="请输入要分析的股票代码，例如：HK2018",
                             key="stock_code_input")
    
    # 添加股票代码验证
    if stock_code and not re.match(r"^[A-Za-z0-9]{2,10}$", stock_code):
        st.warning("股票代码格式不正确！应包含2-10位字母或数字")
    
    st.markdown("### 使用说明")
    st.markdown("""
    1. 在输入框中输入股票代码
    2. 点击"开始分析"按钮
    3. 实时查看分析结果和工作流日志
    4. 分析完成后可下载报告
    
    ### 注意事项
    - 请勿在分析过程中刷新页面
    - 大型分析可能需要1-3分钟
    - 中断分析可能导致不完整结果
    """)
    
    # 添加历史记录功能
    if st.session_state.history:
        st.markdown("### 历史记录")
        for i, item in enumerate(st.session_state.history[:5]):
            if st.button(f"{item['code']} - {item['time']}", key=f"history_{i}"):
                st.session_state.stock_code = item['code']
                st.session_state.analysis_started = False
                st.rerun()

# 主界面布局
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("分析结果")
    result_placeholder = st.empty()
    
    if st.session_state.analysis_result:
        result_placeholder.markdown(st.session_state.analysis_result)
    else:
        result_placeholder.info("👆 点击开始分析按钮获取结果")

with col2:
    st.subheader("工作流日志")
    log_placeholder = st.empty()
    # 移除了 key 参数
    log_placeholder.text_area("", st.session_state.analysis_log, 
                            height=400, label_visibility="collapsed")

# 状态区域
status_placeholder = st.empty()
progress_placeholder = st.empty()
control_placeholder = st.container()

# 执行按钮
if not st.session_state.analysis_started:
    if control_placeholder.button("🚀 开始分析", type="primary", use_container_width=True):
        if not re.match(r"^[A-Za-z0-9]{2,10}$", st.session_state.stock_code_input):
            status_placeholder.error("❌ 股票代码格式不正确！")
        else:
            st.session_state.analysis_started = True
            st.session_state.stock_code = st.session_state.stock_code_input
            st.session_state.runner = WorkflowRunner(st.session_state.stock_code)
            st.session_state.analysis_result = ""
            st.session_state.analysis_log = ""
            threading.Thread(target=st.session_state.runner.run, daemon=True).start()
            status_placeholder.info("🚀 工作流执行中，请稍候...")
            
            # 添加到历史记录
            history_entry = {
                "code": st.session_state.stock_code,
                "time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.history.insert(0, history_entry)
            if len(st.session_state.history) > 10:
                st.session_state.history = st.session_state.history[:10]

# 更新UI的函数
def update_ui():
    """更新UI而不刷新整个页面"""
    current_time = time.time()
    
    # 限制更新频率：每0.3秒最多更新一次
    if current_time - st.session_state.last_update < 0.3:
        return
    
    st.session_state.last_update = current_time
    
    # 更新结果
    if st.session_state.runner and not st.session_state.runner.text_queue.empty():
        st.session_state.analysis_result = st.session_state.runner.text_queue.get()
        result_placeholder.markdown(st.session_state.analysis_result)
    
    # 更新日志 - 使用更安全的方式
    log_updated = False
    while st.session_state.runner and not st.session_state.runner.log_queue.empty():
        log_entry = st.session_state.runner.log_queue.get()
        st.session_state.analysis_log += log_entry + "\n\n"
        log_updated = True
    
    if log_updated:
        # 清除后重新写入
        log_placeholder.empty()
        log_placeholder.text_area("", st.session_state.analysis_log, 
                                height=400, label_visibility="collapsed")
    
    # 更新进度条
    if st.session_state.runner and st.session_state.runner.progress > 0:
        progress_placeholder.progress(st.session_state.runner.progress)

# 显示实时结果
if st.session_state.analysis_started and st.session_state.runner:
    # 更新UI
    update_ui()
    
    # 检查完成状态
    if st.session_state.runner.finished:
        # 最终更新
        update_ui()
        
        if st.session_state.runner.error:
            status_placeholder.error(st.session_state.runner.error)
            progress_placeholder.empty()
        else:
            status_placeholder.success("✅ 分析完成！")
            progress_placeholder.progress(100)
            
            # 添加下载按钮
            st.download_button(
                label="📥 下载分析报告",
                data=st.session_state.analysis_result.encode('utf-8'),
                file_name=f"{st.session_state.stock_code}_分析报告.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # 添加重新开始按钮
        if control_placeholder.button("🔄 重新开始", use_container_width=True):
            st.session_state.analysis_started = False
            st.session_state.runner = None
            st.session_state.analysis_result = ""
            st.session_state.analysis_log = ""
            st.rerun()
    
    # 处理进行中的状态
    else:
        # 添加停止按钮
        if control_placeholder.button("⏹️ 停止分析", type="secondary", use_container_width=True):
            st.session_state.runner.cancel()
            st.session_state.analysis_started = False
            status_placeholder.warning("分析已中断")
            progress_placeholder.empty()
            st.rerun()

# 添加性能监控
if st.sidebar.checkbox("显示性能信息"):
    if st.session_state.history:
        st.sidebar.write("### 最近分析")
        for item in st.session_state.history[:3]:
            st.sidebar.caption(f"{item['code']} - {item['time']}")
    
    st.sidebar.write("### 系统状态")
    st.sidebar.metric("活动线程数", threading.active_count())
    # 添加内存监控（需要安装psutil）
    try:
        import psutil
        mem_usage = psutil.Process().memory_info().rss / 1024 ** 2
        st.sidebar.metric("内存使用", f"{mem_usage:.1f} MB")
    except ImportError:
        st.sidebar.metric("内存使用", "N/A (需安装psutil)")

# 自动更新机制 - 使用Streamlit的自动重运行功能
if st.session_state.analysis_started and st.session_state.runner and not st.session_state.runner.finished:
    # 设置一个短暂的延迟后自动重运行
    time.sleep(0.3)  # 增加延迟减少重绘频率
    st.rerun()