# uStudy Backend Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 配置国内 apt 镜像源（阿里云）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libreoffice-impress \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 先安装 CPU 版本的 PyTorch（避免下载 2GB+ 的 CUDA 版本）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 安装其他 Python 依赖（使用阿里云镜像）
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 安装代码沙箱所需的科学计算库
RUN pip install --no-cache-dir \
    numpy pandas matplotlib sympy scipy \
    scikit-learn seaborn networkx \
    statsmodels jieba wordcloud \
    -i https://mirrors.aliyun.com/pypi/simple/

# 创建沙箱用户（用于后续安全加固）
RUN useradd -r -s /bin/false -d /tmp sandbox_user

# 复制应用代码
COPY . .

# 创建上传目录和证书挂载点
RUN mkdir -p /app/uploads /app/certs
RUN chmod +x /app/scripts/start.sh

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["sh", "/app/scripts/start.sh"]
