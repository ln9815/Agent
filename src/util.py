import logging
import os

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


    