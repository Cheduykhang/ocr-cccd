# Sử dụng image Python 3.11 cơ bản
FROM python:3.11.13-slim

# Đặt thư mục làm việc
WORKDIR /app
# Optional corporate-proxy configuration. Keep disabled for a basic build.
# ARG PROXY_USER
# ARG PROXY_PASS
# ARG PROXY_HOST
# ARG PROXY_PORT
# ENV HTTP_PROXY="http://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}"
# ENV HTTPS_PROXY="http://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}"


# Cài đặt các phụ thuộc hệ thống cần thiết
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libgl1 \
    libcurl4-openssl-dev \
    libgomp1 \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Liên kết python3 với python
RUN ln -s /usr/bin/python3.11 /usr/bin/python

RUN pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org https://www.paddlepaddle.org.cn www.paddlepaddle.org.cn download.pytorch.org"


# Cài đặt các thư viện Python từ các nguồn cụ thể
ENV PIP_NO_VERIFY_CERTS=1
# RUN pip install --upgrade pip



# RUN python -m pip install --no-cache-dir paddlepaddle-gpu==3.1.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/ --trusted-host www.paddlepaddle.org.cn
RUN pip install --no-cache-dir paddlepaddle==3.1.0
RUN pip install --no-cache-dir paddleocr==3.1.0
RUN pip install --no-cache-dir fastapi[standard] "pydantic-settings>=2,<3"
RUN pip install --no-cache-dir onnx==1.18.0
# RUN pip install --no-cache-dir onnxruntime-gpu==1.22.0
RUN pip install --no-cache-dir onnxruntime==1.22.0



# ENV HTTP_PROXY=""
# ENV HTTPS_PROXY=""

# Copy toàn bộ source code vào container
# COPY src/ ./src/

# Thiết lập biến môi trường
# ENV PYTHONPATH=/app/src
ENV PYTHONPATH=/app


# Mở port 9930 cho FastAPI
EXPOSE 9930

# Probe readiness using Python's standard library (no curl dependency).
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:9930/health/ready', timeout=3).close()"]

# Lệnh chạy ứng dụng
CMD ["python3", "main.py"]

# main instruction
# https://grok.com/chat/363ad30c-43fb-4128-bd51-a0d157d8256f
# maker pdf experiments

# Fix bug: ko authen được apt-get
# how to set apt proxy command line
# https://unix.stackexchange.com/questions/590437/specifying-apt-proxy-from-the-command-line

# get proxy từ .env
# https://chatgpt.com/c/688adbc3-c6bc-8012-b2de-5e59e8194d69


# Fix bug: ko authen được pip install
# pip config set global.trusted-host
# https://chatgpt.com/c/688ae974-7044-8012-b42b-f7d9f71bfd5e
# how to set pip proxy command line
# https://stackoverflow.com/questions/19080352/how-to-get-pip-to-work-behind-a-proxy-server
# https://chatgpt.com/c/688ae0a2-2994-8012-80d5-5ede6e3879b7
# libgomp.so.1: cannot open shared object file: No such file or directory
# https://github.com/ggml-org/llama.cpp/issues/7731
# https://stackoverflow.com/questions/43764624/importerror-libgomp-so-1-cannot-open-shared-object-file-no-such-file-or-direc

# BUILD IMAGE COMMAND:
# docker build \
#   --build-arg PROXY_USER=$(grep PROXY_USER .env-docker | cut -d '=' -f2) \
#   --build-arg PROXY_PASS=$(grep PROXY_PASS .env-docker | cut -d '=' -f2) \
#   --build-arg PROXY_HOST=$(grep PROXY_HOST .env-docker | cut -d '=' -f2) \
#   --build-arg PROXY_PORT=$(grep PROXY_PORT .env-docker | cut -d '=' -f2) \
#   -t ocr-app .
# RUN CONTAINER COMMAND
# docker run --gpus all \
#   -v $(pwd)/model:/app/model \
#   -v $(pwd)/src:/app/src \
#   -v $(pwd)/main.py:/app/main.py \
#   -v $(pwd)/configs.yml:/app/configs.yml \
#   -p 9930:9930 \
#   --name ocr-container \
#   ocr-app
