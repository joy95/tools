FROM python:3.9-slim-buster

WORKDIR /app

# 安装 Poetry
RUN pip install poetry

# 复制 Poetry 配置和依赖文件
COPY poetry.lock pyproject.toml ./  

# 安装项目依赖
RUN poetry install --no-root --no-interaction --no-ansi

# 复制应用代码
COPY . .

# 安装 PaddleOCR 的额外依赖 (如果需要)
# RUN pip install paddlepaddle-gpu -i https://pypi.tuna.tsinghua.edu.cn/simple
# RUN pip install paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple

# 暴露 FastAPI 端口
EXPOSE 8000

# 启动 Uvicorn 服务器
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
