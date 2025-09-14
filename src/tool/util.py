import logging
import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import dotenv

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

def setup_logging(log_file, level=logging.DEBUG):
    """配置日志记录，同时输出到控制台和文件"""
    log_dir = os.path.join(os.getcwd(), "logs")
    
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_file)
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




def parse_stock_input(input):
    """根据输入的字符串查询相关的股票代码，名称和所属市场"""
    def _parse_stock_string(stock_str):
        parts = stock_str.split()
        if len(parts) < 3:
            return None  
        code_part = parts[0]
        if "||" in code_part:
            stock_code = code_part.split("||")[-1]
        else:
            stock_code = code_part
        stock_market = 'A股' if parts[-1] =='股票' else parts[-1]
        stock_name = parts[1]

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "stock_market": stock_market
        }

    def _parse_stock_data(json_data):
        results = []
        for sublist in json_data:
            if not isinstance(sublist, list):
                continue
                
            for stock_str in sublist:
                if not isinstance(stock_str, str):
                    continue
                    
                stock_info = _parse_stock_string(stock_str)
                if stock_info:
                    results.append(stock_info)
        return results
    url = f'https://news.10jqka.com.cn/public/index_keyboard_{input.strip()}_stock,hk,usa_5_jsonp.html'
    headers = {
        "referer": "https://stockpage.10jqka.com.cn/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    jsonp_data = response.text
    if jsonp_data.startswith('jsonp(') and jsonp_data.endswith(')'):
        json_str = jsonp_data[6:-1]  
    else:
        json_str = jsonp_data
    parsed_data = json.loads(json_str)
    standard_json = json.dumps(parsed_data, ensure_ascii=False, indent=2)
    data = json.loads(standard_json)
    result = _parse_stock_data(data)
    if len(result) == 0:
        raise ValueError(f'查询不到股票代码和名称: {input}')
    return result[0]

def send_email_via_126(
    sender_email: str,
    sender_auth_code: str,
    recipient_emails: list,
    email_subject: str,
    email_content: str,
    sender_name: str = 'Auto System',
    content_type: str = "plain"  # "plain" 文本格式，"html" HTML格式
) -> bool:
    """
    用126邮箱发送邮件的封装函数
    
    参数说明：
    --------
    sender_email: str
        发件人126邮箱地址（如 "your_account@126.com"）
    sender_auth_code: str
        126邮箱的SMTP授权码（非登录密码，需提前在邮箱设置中开启获取）
    recipient_emails: list
        收件人邮箱列表（如 ["recipient1@qq.com", "recipient2@gmail.com"]）
    email_subject: str
        邮件主题
    email_content: str
        邮件内容（文本或HTML字符串，需与content_type匹配）
    content_type: str, optional
        内容格式，默认"plain"（纯文本），可选"html"（支持HTML标签排版）
    
    返回值：
    ------
    bool: 
        发送成功返回True，失败返回False
    """
    SMTP_SERVER = "smtp.126.com"  
    SMTP_PORT = 465  # 非SSL端口（SSL端口为465，需用SMTP_SSL连接）

    try:
        msg = MIMEText(email_content, content_type, "utf-8")
        msg["From"] = formataddr((sender_name, sender_email))
        msg["To"] = ",".join(recipient_emails)
        msg["Subject"] = email_subject
        smtp_conn = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        smtp_conn.login(sender_email, sender_auth_code)
        smtp_conn.sendmail(sender_email, recipient_emails, msg.as_string())
        logger.info(f"邮件发送成功！发件人：{sender_email}，收件人：{recipient_emails}，主题：{email_subject}")

        # 5. 关闭连接（避免资源占用）
        smtp_conn.quit()
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(f"邮件发送失败：登录认证错误！请检查126邮箱授权码是否正确，或SMTP服务是否开启")
        return False
    except smtplib.SMTPConnectError:
        logger.error(f"邮件发送失败：无法连接SMTP服务器 {SMTP_SERVER}:{SMTP_PORT}，请检查网络或端口")
        return False
    except Exception as e:
        logger.error(f"邮件发送失败：未知错误 - {str(e)}", exc_info=True)  # exc_info=True打印堆栈，便于排查
        return False

def send_mail(to_mail, subject, content,sender_name='Auto System'):
    sender = os.getenv('VKATE_MAIL')
    token = os.getenv('VKATE_TOKEN')
    if isinstance(to_mail, str):
        to_mail = [to_mail]
    send_email_via_126(sender, token, to_mail, subject, content)
    logger.info(f'邮件发送成功！发件人：{sender}，收件人：{to_mail}，主题：{subject}')

if __name__ == '__main__':
    # print(parse_stock_input('600519'))
    setup_logging('util.log')
    send_mail('mingxiangy@126.com', '测试', '这是一封测试邮件')
