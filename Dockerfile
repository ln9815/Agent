# 使用官方 Python 基础镜像
FROM python:3.11-slim-bullseye

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
# COPY . .

# 设置启动命令 (根据实际入口修改)
CMD ["python", "app.py"]
