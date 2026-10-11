FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /tmp/llama.tar.gz \
    https://github.com/ggerganov/llama.cpp/releases/download/b11553/llama-b11553-bin-ubuntu-x64.tar.gz \
    && mkdir -p /tmp/llama \
    && tar -xzf /tmp/llama.tar.gz -C /tmp/llama \
    && find /tmp/llama -name "llama-server" -type f -exec cp {} /usr/local/bin/llama-server \; \
    && chmod +x /usr/local/bin/llama-server \
    && rm -rf /tmp/llama.tar.gz /tmp/llama

RUN mkdir -p /models /app/data

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV DUCKDB_PATH=/app/data/agentic_ai_erp.duckdb
ENV LLM_MODEL_GGUF=qwen2.5-0.5b-instruct-q4_k_m.gguf
ENV MODEL_DOWNLOAD_AUTO=false
ENV LLAMA_PORT=8088
ENV LLAMA_CTX=2048
ENV LLAMA_NGL=0
ENV LLAMA_THREADS=3
ENV LLAMA_BASE_URL=http://127.0.0.1:8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
