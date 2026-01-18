FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先复制依赖清单以利用缓存（改代码不需要重装依赖）
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --no-compile -r /app/requirements.txt \
    && pip uninstall -y pyarrow \
    && find /usr/local -type d -name '__pycache__' -prune -exec rm -rf '{}' + \
    && find /usr/local -type f -name '*.pyc' -delete

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
