ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

# 环境变量设置
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 构建参数
ARG TALIB_C_VERSION="0.6.4"
ARG TALIB_PY_MAJOR_MIN_VERSION="0.6"

# 包管理变量
ENV APT_PKG_TEMPORARY="build-essential autoconf automake autotools-dev cmake python3-dev python3-venv libtool-bin libopenblas-dev wget" \
    APT_PKG="python3 python3-pip liblapack3" \
    TALIB_C_VERSION=${TALIB_C_VERSION} \
    TALIB_PY_MAJOR_MIN_VERSION=${TALIB_PY_MAJOR_MIN_VERSION}

# 设置工作目录
WORKDIR /app

# 安装系统依赖和TA-Lib C库
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ${APT_PKG_TEMPORARY} ${APT_PKG} && \
    ln -s /usr/include/locale.h /usr/include/xlocale.h && \
    \
    # 根据架构选择安装方式
    arch="$(dpkg --print-architecture)" && \
    case "$arch" in \
        amd64|x86_64) final_arch="amd64" ;; \
        arm64|aarch64) final_arch="arm64" ;; \
        *) final_arch="" ;; \
    esac && \
    \
    if [ -n "$final_arch" ]; then \
        echo "Detected $arch, using TA-Lib $TALIB_C_VERSION .deb" && \
        TALIB_URL="https://github.com/TA-Lib/ta-lib/releases/download/v${TALIB_C_VERSION}/ta-lib_${TALIB_C_VERSION}_${final_arch}.deb" && \
        wget -O /tmp/ta-lib.deb "$TALIB_URL" && \
        dpkg -i /tmp/ta-lib.deb && \
        rm -f /tmp/ta-lib.deb; \
    else \
        echo "Arch $arch not supported, building TA-Lib from source" && \
        wget -O /tmp/ta-lib-src.tgz "https://github.com/TA-Lib/ta-lib/releases/download/v${TALIB_C_VERSION}/ta-lib-${TALIB_C_VERSION}-src.tar.gz" && \
        mkdir /tmp/ta-lib && \
        tar xf /tmp/ta-lib-src.tgz -C /tmp/ta-lib --strip-components=1 && \
        cd /tmp/ta-lib && \
        ./configure --prefix=/usr && \
        make -j$(nproc) && \
        make install && \
        libtool --finish /usr/lib && \
        rm -rf /tmp/ta-lib /tmp/ta-lib-src.tgz; \
    fi && \
    \
    # 创建虚拟环境并安装Python依赖
    python3 -m venv /venv && \
    /venv/bin/pip install --no-cache-dir --upgrade pip cython && \
    /venv/bin/pip install --no-cache-dir "TA-Lib~=${TALIB_PY_MAJOR_MIN_VERSION}" pandas && \
    \
    # 清理工作
    apt-get autoremove -y ${APT_PKG_TEMPORARY} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* ${WHEEL_FILE}

# 构建参数
ARG WHEEL_FILE="stock_tool-0.1.2-py3-none-any.whl"
# 复制wheel文件到容器中
COPY ${WHEEL_FILE} .

# 安装应用
RUN /venv/bin/pip install --no-cache-dir ${WHEEL_FILE}

# 设置容器入口点
CMD ["/venv/bin/StockAgent"]