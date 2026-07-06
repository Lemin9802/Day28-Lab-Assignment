# Kaggle setup guide for Lab28

This guide explains the 3 environment values used by the local `.env` file.

## What you need to fill

| `.env` name | Where it comes from | Required? | Meaning |
|---|---|---:|---|
| `VLLM_TUNNEL_URL` | Kaggle cloudflared tunnel for vLLM, port 8001 | Yes for real model demo | Local API Gateway calls this URL for LLM inference |
| `EMBED_TUNNEL_URL` | Kaggle cloudflared tunnel for embedding API, port 8002 | Optional | Qdrant script calls this URL to create embeddings |
| `LANGCHAIN_API_KEY` | LangSmith Settings -> API Keys | Yes for LangSmith tracing | Sends request traces to LangSmith project |

If `VLLM_TUNNEL_URL` is empty or slow, the API Gateway still works because `ENABLE_LLM_FALLBACK=true`.

If `EMBED_TUNNEL_URL` is empty, the Qdrant script uses local deterministic embeddings, so smoke tests still work.

## Step 1 - Create Kaggle notebook

1. Open Kaggle.
2. Create a new Notebook.
3. Enable GPU in notebook settings.
4. Run the cells below in order.

## Step 2 - Install dependencies

```python
!pip install -q vllm fastapi uvicorn sentence-transformers cloudflared
```

## Step 3 - Start vLLM server on port 8001

```python
import subprocess
import threading
import time

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"

def run_vllm():
    subprocess.run([
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", "8001",
        "--max-model-len", "4096",
        "--gpu-memory-utilization", "0.5",
    ])

threading.Thread(target=run_vllm, daemon=True).start()
time.sleep(60)
print("vLLM server started on http://localhost:8001")
```

## Step 4 - Start embedding API on port 8002

```python
%%writefile embed_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Lab28 Embedding Service")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class EmbedRequest(BaseModel):
    texts: list[str]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/embed")
def embed(payload: EmbedRequest):
    vectors = model.encode(payload.texts, normalize_embeddings=True).tolist()
    return {"embeddings": vectors}
```

```python
import subprocess
import threading
import time

def run_embed_api():
    subprocess.run(["uvicorn", "embed_server:app", "--host", "0.0.0.0", "--port", "8002"])

threading.Thread(target=run_embed_api, daemon=True).start()
time.sleep(20)
print("Embedding server started on http://localhost:8002")
```

## Step 5 - Create cloudflared URL for vLLM

```python
import subprocess
import re

vllm_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

for line in vllm_proc.stdout:
    print(line, end="")
    match = re.search(r"https://[-a-zA-Z0-9.]+trycloudflare.com", line)
    if match:
        print("\nCOPY THIS TO .env:")
        print("VLLM_TUNNEL_URL=" + match.group(0))
        break
```

Copy the printed value into local `.env`, for example:

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
```

## Step 6 - Create cloudflared URL for embedding API

```python
import subprocess
import re

embed_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://localhost:8002"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

for line in embed_proc.stdout:
    print(line, end="")
    match = re.search(r"https://[-a-zA-Z0-9.]+trycloudflare.com", line)
    if match:
        print("\nCOPY THIS TO .env:")
        print("EMBED_TUNNEL_URL=" + match.group(0))
        break
```

Copy the printed value into local `.env`, for example:

```env
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
```

## Step 7 - Get LangSmith key

1. Open LangSmith.
2. Go to Settings.
3. Open API Keys.
4. Create a new key.
5. Copy the key into local `.env`.

Example:

```env
LANGCHAIN_API_KEY=your_real_key_here
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
```

Do not paste the real key into ChatGPT, GitHub, screenshots, or README.

## Final `.env` shape

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
LLM_TIMEOUT_SECONDS=1.2
ENABLE_LLM_FALLBACK=true
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
LANGCHAIN_API_KEY=your_real_langsmith_key
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
API_GATEWAY_URL=http://localhost:8000
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DELTA_LAKE_PATH=delta-lake/raw
```

For smoke tests, keep `LLM_TIMEOUT_SECONDS=1.2` so fallback protects latency. For a live demo with real vLLM output, use `LLM_TIMEOUT_SECONDS=20`.
