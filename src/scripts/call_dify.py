import requests
import json

TOKEN = 'app-rCFXuZN6Bwr4P3c5VDsknOt4'

def handle_stream_response(user, stock_code):
    workflow_url = "http://szvkt.top:8880/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"  # 明确要求事件流格式
    }

    data = {
        "inputs": {
            "stock_code": stock_code
        },
        "response_mode": "streaming",
        "user": user
    }

    try:
        # 发送请求并获取SSE流
        with requests.post(
            workflow_url,
            headers=headers,
            json=data,
            stream=True,
            timeout=30  # 添加超时设置
        ) as response:
            
            # 检查响应状态码
            if response.status_code != 200:
                print(f"请求失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return
            
            # 直接处理事件流
            buffer = ""  # 用于处理多行数据的情况
            for byte_chunk in response.iter_content(chunk_size=1024):
                if byte_chunk:
                    # 将字节流解码为字符串
                    chunk = byte_chunk.decode('utf-8')
                    
                    # 将数据添加到缓冲区
                    buffer += chunk
                    
                    # 处理缓冲区中的所有完整事件
                    while "\n\n" in buffer:
                        # 提取第一个完整事件
                        event_end = buffer.index("\n\n")
                        event_data = buffer[:event_end]
                        buffer = buffer[event_end + 2:]  # 移除已处理的事件
                        
                        # 处理单个事件
                        process_event_data(event_data)
    
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {str(e)}")
    except Exception as e:
        print(f"未知错误: {str(e)}")

def process_event_data(event_data):
    """处理单个SSE事件数据"""
    event_lines = event_data.split('\n')
    event_dict = {}
    
    # 解析事件行
    for line in event_lines:
        if line.startswith('data:'):
            # 提取数据部分
            json_str = line[5:].strip()
            if json_str:
                try:
                    event_dict = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {str(e)}")
                    print(f"原始数据: {json_str}")
                    return
    
    # 如果没有有效数据，直接返回
    if not event_dict:
        return
    
    # 根据事件类型处理不同数据
    event_type = event_dict.get('event')
    
    if event_type == 'workflow_started':
        print(f"\n[Workflow Started] ID: {event_dict['data']['id']}")
        print(f"Task ID: {event_dict['task_id']}")
        print(f"Start Time: {event_dict['data']['created_at']}")
    
    elif event_type == 'node_started':
        print(f"\n[Node Started] {event_dict['data']['title']} (Type: {event_dict['data']['node_type']})")
        print(f"Node ID: {event_dict['data']['node_id']}")
        print(f"Sequence: {event_dict['data']['index']}")
    
    elif event_type == 'text_chunk':
        # 流式输出文本片段
        text = event_dict['data']['text']
        print(text, end='', flush=True)  # 实时输出不换行
    
    elif event_type == 'node_finished':
        node_data = event_dict['data']
        status = node_data['status']
        print(f"\n\n[Node Finished] {node_data['node_id']} - Status: {status.upper()}")
        
        if status == 'failed':
            print(f"Error: {node_data.get('error', 'Unknown error')}")
        else:
            print(f"Tokens Used: {node_data.get('total_tokens', 0)}")
            print(f"Cost: {node_data.get('total_price', 0)} {node_data.get('currency', '')}")
    
    elif event_type == 'workflow_finished':
        wf_data = event_dict['data']
        print(f"\n\n[Workflow Finished] Status: {wf_data['status'].upper()}")
        print(f"Total Time: {wf_data['elapsed_time']}s")
        print(f"Total Tokens: {wf_data.get('total_tokens', 0)}")
        
        if wf_data['status'] == 'succeeded':
            print("\nFINAL OUTPUT:")
            print(json.dumps(wf_data.get('outputs', {}), indent=2))

if __name__ == "__main__":
    handle_stream_response('admin', 'HK2018')