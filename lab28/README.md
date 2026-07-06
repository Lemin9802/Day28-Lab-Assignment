# Lab28 - Hướng dẫn setup và runbook

Folder này là package chính để chạy Lab #28: Full Platform Integration Sprint.

Mục tiêu của file này là hướng dẫn đầy đủ cách setup, chạy platform, chạy pipeline, chạy smoke tests, kiểm tra production readiness và mở các dashboard quan sát hệ thống.

---

## 1. Chuẩn bị

Cần có:

- Docker Desktop
- Docker Compose
- Python 3.10+
- Git
- Kaggle Notebook có GPU nếu muốn chạy real vLLM demo
- LangSmith project nếu muốn verify tracing

---

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

---

## 3. Thiết lập environment

Tạo `.env` từ file mẫu:

```bash
cd lab28
cp .env.example .env
```

Với Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Các biến cần điền nếu chạy real demo:

```env
VLLM_TUNNEL_URL=<kaggle-vllm-public-url>
EMBED_TUNNEL_URL=<kaggle-embedding-public-url>
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
- Nếu không có Kaggle tunnel, API Gateway vẫn chạy được bằng fallback mode.
- Không commit `.env`.

Chi tiết Kaggle setup: [`../KAGGLE_SETUP.md`](../KAGGLE_SETUP.md)

---

## 4. Chạy platform

```bash
docker compose up -d --build
```

Kiểm tra containers:

```bash
docker compose ps
```

Các service chính:

| Service | Port | Vai trò |
|---|---:|---|
| API Gateway | 8000 | Serving API |
| Prefect UI | 4200 | Theo dõi flow/task runs |
| Qdrant | 6333 | Vector store |
| Redis | 6379 | Feature store |
| Kafka | 9092 | Event bus |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboard |

---

## 5. Kiểm tra health/readiness

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Kết quả mong muốn:

```text
status: ok
status: ready
fallback_enabled: True
```

Nếu real vLLM tunnel đã được cấu hình thì `/ready` có thêm:

```text
vllm_configured: True
```

---

## 6. Chạy pipeline end-to-end

### Bước 1 - Ingest events vào Kafka

```bash
python scripts/01_ingest_to_kafka.py
```

Kết quả mong muốn:

```text
Integration 1 OK
```

### Bước 2 - Kafka -> Lakehouse bằng Prefect flow

Chạy local:

```bash
python prefect/flows/kafka_to_delta.py
```

Kết quả mong muốn:

```text
Consumed records from Kafka topic data.raw
Saved records to Delta Lake path delta-lake/raw/...
```

Chạy qua Docker worker environment:

```bash
docker compose exec prefect-worker sh -lc "cd /opt/prefect/flows && PREFECT_API_URL=http://prefect-orion:4200/api python kafka_to_delta.py"
```

Nếu muốn chạy dạng Prefect serve mode:

```bash
PREFECT_MODE=serve python prefect/flows/kafka_to_delta.py
```

Windows PowerShell:

```powershell
$env:PREFECT_MODE="serve"
python prefect/flows/kafka_to_delta.py
```

Sau đó mở Prefect UI:

```text
http://localhost:4200
```

### Bước 3 - Lakehouse -> Redis feature store

```bash
python scripts/03_delta_to_feast.py
```

Kết quả mong muốn:

```text
Integration 3+4 OK: Lakehouse -> Feast/Redis
```

### Bước 4 - Lakehouse -> Qdrant vector store

```bash
python scripts/05_embed_to_qdrant.py
```

Kết quả mong muốn khi có real embedding tunnel:

```text
Embedding service OK: received 3 embeddings
Integration 5 OK: stored 3 vectors in Qdrant collection 'documents'
```

Nếu không có embedding tunnel, script vẫn có fallback embedding local để phục vụ smoke tests.

### Bước 5 - Register model metadata vào MLflow

```bash
python scripts/06_register_model_mlflow.py
```

Kết quả mong muốn:

```text
Registered model: lab28-fallback-llm
Integration 6 OK
```

---

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

Kết quả mong muốn khi real vLLM hoạt động:

```text
model         : Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
fallback_used : False
context_items : 3
error         :
```

Kết quả mong muốn nếu Kaggle tunnel không khả dụng:

```text
model         : fallback-local
fallback_used : True
```

---

## 8. Chạy smoke tests

```bash
pytest smoke-tests/ -v
```

Kết quả đã verify:

```text
8 passed, 1 warning
```

Screenshot: [`smoke_tests_results.png`](smoke_tests_results.png)

---

## 9. Production readiness

```bash
python scripts/production_readiness_check.py
```

Kết quả đã verify:

```text
Production Readiness Score: 14/14 = 100%
Target: >80% - Status: READY
```

Screenshot: [`production_readiness.png`](production_readiness.png)

---

## 10. Kiểm tra observability

```bash
python scripts/09_verify_observability.py
```

Kết quả mong muốn:

```text
Integration 9 OK: Prometheus metrics flowing for API Gateway
Integration 10 OK: LangSmith traces visible in project lab28-platform
```

---

## 11. Dashboards

| Tool | URL | Ghi chú |
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

Query hữu ích:

```text
up
http_requests_total
```

---

## 12. Screenshots nộp bài

Các file evidence đã có sẵn:

```text
screenshots/prefect_ui.png
screenshots/api_gateway.png
screenshots/grafana_dashboard.png
smoke_tests_results.png
production_readiness.png
```

---

## 13. Troubleshooting

### API trả fallback

Kiểm tra:

```bash
curl http://localhost:8000/ready
```

Nếu `vllm_configured` là `False`, cập nhật `VLLM_TUNNEL_URL` trong `.env`, sau đó restart API Gateway:

```bash
docker compose up -d --force-recreate api-gateway
```

### Qdrant chưa có vectors

Chạy lại:

```bash
python scripts/05_embed_to_qdrant.py
```

### Redis chưa có features

Chạy lại:

```bash
python scripts/03_delta_to_feast.py
```

### Grafana không có data

Trong Grafana Explore, chọn datasource `prometheus`, rồi query:

```text
up
```

Nếu vẫn không có data, kiểm tra Prometheus targets:

```text
http://localhost:9090/targets
```

---

## 14. Dừng platform

```bash
docker compose down
```

Nếu muốn xóa volumes để reset sạch:

```bash
docker compose down -v
```
