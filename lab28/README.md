# Lab28 - Setup & Runbook

Folder này là package chính để chạy Lab #28: Full Platform Integration Sprint.

## 1. Prerequisites

Cần có:

- Docker Desktop
- Docker Compose
- Python 3.10+
- Git
- Kaggle notebook có GPU nếu muốn chạy real vLLM demo
- LangSmith project nếu muốn verify tracing

## 2. Cấu trúc chính

```text
lab28/
├── docker-compose.yml
├── api-gateway/
├── prefect/flows/
├── scripts/
├── monitoring/
├── smoke-tests/
├── screenshots/
├── smoke_tests_results.png
├── production_readiness.png
└── README.md
```

## 3. Environment setup

Tạo `.env` từ file mẫu:

```bash
cd lab28
cp .env.example .env
```

Với Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Các giá trị cần điền nếu chạy real demo:

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
LLM_TIMEOUT_SECONDS=20
ENABLE_LLM_FALLBACK=true
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
```

Ghi chú:

- `VLLM_TUNNEL_URL`: lấy từ Kaggle vLLM service port `8001`.
- `EMBED_TUNNEL_URL`: lấy từ Kaggle embedding service port `8002`.
- Nếu không có Kaggle tunnel, API Gateway vẫn chạy bằng fallback mode.
- Không commit `.env`.

Chi tiết Kaggle setup: [`../KAGGLE_SETUP.md`](../KAGGLE_SETUP.md)

## 4. Start platform

```bash
docker compose up -d --build
```

Kiểm tra containers:

```bash
docker compose ps
```

Các service chính:

| Service | Port |
|---|---:|
| API Gateway | 8000 |
| Prefect UI | 4200 |
| Qdrant | 6333 |
| Redis | 6379 |
| Kafka | 9092 |
| Prometheus | 9090 |
| Grafana | 3000 |

## 5. Health checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Expected:

```text
status: ok
status: ready
vllm_configured: True
fallback_enabled: True
```

## 6. Run end-to-end pipeline

### Step 1 - Ingest events to Kafka

```bash
python scripts/01_ingest_to_kafka.py
```

Expected:

```text
Integration 1 OK
```

### Step 2 - Kafka -> Lakehouse with Prefect flow

Local run:

```bash
python prefect/flows/kafka_to_delta.py
```

Expected:

```text
Consumed records from Kafka topic data.raw
Saved records to Delta Lake path delta-lake/raw/...
```

Run through Docker worker environment:

```bash
docker compose exec prefect-worker sh -lc "cd /opt/prefect/flows && PREFECT_API_URL=http://prefect-orion:4200/api python kafka_to_delta.py"
```

Optional scheduled run using Prefect serve mode:

```bash
PREFECT_MODE=serve python prefect/flows/kafka_to_delta.py
```

Windows PowerShell:

```powershell
$env:PREFECT_MODE="serve"
python prefect/flows/kafka_to_delta.py
```

Then open Prefect UI:

```text
http://localhost:4200
```

### Step 3 - Lakehouse -> Redis feature store

```bash
python scripts/03_delta_to_feast.py
```

Expected:

```text
Integration 3+4 OK: Lakehouse -> Feast/Redis
```

### Step 4 - Lakehouse -> Qdrant vector store

```bash
python scripts/05_embed_to_qdrant.py
```

Expected with real embedding tunnel:

```text
Embedding service OK: received 3 embeddings
Integration 5 OK: stored 3 vectors in Qdrant collection 'documents'
```

### Step 5 - Register model metadata in MLflow

```bash
python scripts/06_register_model_mlflow.py
```

Expected:

```text
Registered model: lab28-fallback-llm
Integration 6 OK
```

## 7. Test API Gateway real serving

PowerShell example:

```powershell
$embedding = @(1..384 | ForEach-Object {0.1})

$body = @{
  query = "Explain the Lab 28 platform in one short paragraph."
  embedding = $embedding
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri http://localhost:8000/api/v1/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Expected real vLLM output:

```text
model         : Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
fallback_used : False
context_items : 3
error         :
```

Expected fallback output if Kaggle tunnel is unavailable:

```text
model         : fallback-local
fallback_used : True
```

## 8. Smoke tests

```bash
pytest smoke-tests/ -v
```

Current verified result:

```text
8 passed, 1 warning
```

Screenshot: [`smoke_tests_results.png`](smoke_tests_results.png)

## 9. Production readiness

```bash
python scripts/production_readiness_check.py
```

Current verified result:

```text
Production Readiness Score: 14/14 = 100%
Target: >80% - Status: READY
```

Screenshot: [`production_readiness.png`](production_readiness.png)

## 10. Observability verification

```bash
python scripts/09_verify_observability.py
```

Expected:

```text
Integration 9 OK: Prometheus metrics flowing for API Gateway
Integration 10 OK: LangSmith traces visible in project lab28-platform
```

## 11. Dashboards

| Tool | URL | Note |
|---|---|---|
| API Gateway | http://localhost:8000 | Main service |
| API docs | http://localhost:8000/docs | FastAPI Swagger |
| Prefect UI | http://localhost:4200 | Flow/task runs |
| Qdrant dashboard | http://localhost:6333/dashboard | Vector collection |
| Prometheus | http://localhost:9090 | Metrics |
| Grafana | http://localhost:3000 | Login `admin/admin` |

Grafana datasource:

```text
Name: prometheus
URL: http://prometheus:9090
```

Useful query:

```text
up
http_requests_total
```

## 12. Submission screenshots

Required files already included:

```text
screenshots/prefect_ui.png
screenshots/api_gateway.png
screenshots/grafana_dashboard.png
smoke_tests_results.png
production_readiness.png
```

## 13. Troubleshooting

### API returns fallback

Check:

```bash
curl http://localhost:8000/ready
```

If `vllm_configured` is `False`, set the Kaggle vLLM tunnel value in `.env`, then restart:

```bash
docker compose up -d --force-recreate api-gateway
```

### Qdrant has no vectors

Run:

```bash
python scripts/05_embed_to_qdrant.py
```

### Redis has no features

Run:

```bash
python scripts/03_delta_to_feast.py
```

### Grafana no data

In Grafana Explore, choose Prometheus datasource and query:

```text
up
```

If there is still no data, check Prometheus:

```text
http://localhost:9090/targets
```

## 14. Stop platform

```bash
docker compose down
```

To remove volumes too:

```bash
docker compose down -v
```
