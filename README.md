# Lab #28 - Full Platform Integration Sprint

**Sinh viên:** Thái Thị Yến Nhi  
**MSSV:** `2A202600783`  
**Mục tiêu:** demo một AI infrastructure platform end-to-end từ data ingestion đến model serving, có observability, smoke tests và production readiness check.

---

## 1. Chấm nhanh

| Artifact | Link | Kết quả |
|---|---|---|
| Source code | [`lab28/`](lab28/) | Docker Compose stack, scripts, API Gateway, Prefect, monitoring |
| Setup guide | [`lab28/README.md`](lab28/README.md) | Hướng dẫn chạy platform, pipeline, tests, dashboards |
| Kaggle GPU guide | [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md) | vLLM + embedding API + cloudflared tunnel |
| Day 16 -> Day 27 map | [`docs/day16-day27-integration-map.md`](docs/day16-day27-integration-map.md) | Mapping các lab trước vào Lab 28 |
| Prefect UI screenshot | [`lab28/screenshots/prefect_ui.png`](lab28/screenshots/prefect_ui.png) | Flow/task run completed |
| API Gateway screenshot | [`lab28/screenshots/api_gateway.png`](lab28/screenshots/api_gateway.png) | `/health` trả `status: ok` |
| Grafana screenshot | [`lab28/screenshots/grafana_dashboard.png`](lab28/screenshots/grafana_dashboard.png) | Grafana dùng Prometheus datasource, query `up` có data |
| Smoke tests screenshot | [`lab28/smoke_tests_results.png`](lab28/smoke_tests_results.png) | `8 passed` |
| Production readiness screenshot | [`lab28/production_readiness.png`](lab28/production_readiness.png) | `14/14 = 100%`, READY |

> Trong repo này, folder `lab28/` là submission package nên screenshots và result images được đặt trong `lab28/` để đi cùng source code.

---

## 2. Output đã verify

### 2.1 Real vLLM serving qua Kaggle GPU

Kaggle chạy vLLM OpenAI-compatible server với model:

```text
Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
```

Public tunnel test:

```text
status: 200
model: Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
content: public tunnel works
```

Local API Gateway gọi real vLLM thành công:

```text
latency_ms    : 2910.01
model         : Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
fallback_used : False
context_items : 3
error         :
```

### 2.2 Real embedding tunnel -> Qdrant

```text
status: 200
embedding_count: 1
embedding_dim: 384
```

Local indexing script:

```text
Loaded 3 records from Delta Lake path delta-lake\raw
Embedding service OK: received 3 embeddings
Integration 5 OK: stored 3 vectors in Qdrant collection 'documents'
```

### 2.3 Smoke tests

![Smoke tests](lab28/smoke_tests_results.png)

```text
collected 8 items
8 passed, 1 warning
```

### 2.4 Production readiness

![Production readiness](lab28/production_readiness.png)

```text
Production Readiness Score: 14/14 = 100%
Target: >80% - Status: READY
```

### 2.5 Observability

```text
Integration 9 OK: Prometheus metrics flowing for API Gateway
Integration 10 OK: LangSmith traces visible in project lab28-platform
```

![Grafana dashboard](lab28/screenshots/grafana_dashboard.png)

---

## 3. Screenshots demo

### 3.1 Prefect UI

Flow/task run đã completed trong Prefect UI.

![Prefect UI](lab28/screenshots/prefect_ui.png)

### 3.2 API Gateway `/health`

API Gateway health endpoint trả `status: ok`.

![API Gateway health](lab28/screenshots/api_gateway.png)

### 3.3 Grafana / Prometheus datasource

Grafana Explore dùng Prometheus datasource và query `up`, có `api-gateway` value `1`.

![Grafana Prometheus query](lab28/screenshots/grafana_dashboard.png)

---

## 4. Architecture

```mermaid
flowchart LR
    subgraph Local[Local Docker Compose]
        ING[01_ingest_to_kafka.py] --> KAFKA[(Kafka\ndata.raw)]
        KAFKA --> PREFECT[Prefect flow\nkafka_to_delta.py]
        PREFECT --> LAKE[(Lakehouse parquet\ndelta-lake/raw)]
        LAKE --> REDIS[(Redis\nfeature store)]
        LAKE --> QDRANT[(Qdrant\nvector store)]
        API[FastAPI API Gateway\n/api/v1/chat] --> QDRANT
        API --> METRICS[/metrics]
        PROM[Prometheus] --> METRICS
        GRAF[Grafana] --> PROM
        API --> TRACE[LangSmith traces]
        ML[MLflow local registry]
    end

    subgraph Kaggle[Kaggle GPU Runtime]
        VLLM[vLLM server\nQwen2.5-7B GPTQ Int4\nport 8001]
        EMBED[Embedding API\nMiniLM 384-dim\nport 8002]
    end

    API -. cloudflared tunnel .-> VLLM
    QDRANT -. indexed by .-> EMBED
    LAKE --> ML
```

| Layer | Công nghệ | Vai trò |
|---|---|---|
| Ingestion | Kafka | Nhận events vào topic `data.raw` |
| Orchestration | Prefect | Consume Kafka và ghi lakehouse parquet |
| Lakehouse | Parquet local | Lưu dữ liệu processed batch |
| Feature Store | Redis | Online features dạng `feature:*` |
| Vector Store | Qdrant | Lưu document embeddings cho retrieval |
| Model Serving | Kaggle vLLM | Chạy real LLM qua OpenAI-compatible API |
| API Gateway | FastAPI | `/health`, `/ready`, `/api/v1/chat`, `/metrics` |
| Observability | Prometheus, Grafana, LangSmith | Metrics, dashboard, traces |
| Model Registry | MLflow SQLite | Register fallback serving model metadata |

---

## 5. 10 integration points

| # | Requirement | File / implementation | Evidence |
|---:|---|---|---|
| 1 | Data ingestion -> Kafka | [`lab28/scripts/01_ingest_to_kafka.py`](lab28/scripts/01_ingest_to_kafka.py) | Kafka topics verified |
| 2 | Kafka -> pipeline | [`lab28/prefect/flows/kafka_to_delta.py`](lab28/prefect/flows/kafka_to_delta.py) | Prefect UI completed |
| 3 | Pipeline -> Lakehouse | `delta-lake/raw/*.parquet` runtime artifact | `Saved records to Delta Lake path` |
| 4 | Lakehouse -> Feature Store | [`lab28/scripts/03_delta_to_feast.py`](lab28/scripts/03_delta_to_feast.py) | Redis features stored |
| 5 | Data -> Vector Store | [`lab28/scripts/05_embed_to_qdrant.py`](lab28/scripts/05_embed_to_qdrant.py) | Qdrant `documents`, 384-dim embeddings |
| 6 | MLflow -> Model Registry | [`lab28/scripts/06_register_model_mlflow.py`](lab28/scripts/06_register_model_mlflow.py) | `lab28-fallback-llm` registered |
| 7 | Model -> vLLM serving | Kaggle vLLM, documented in [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md) | `status: 200`, model Qwen2.5 GPTQ Int4 |
| 8 | Serving -> API Gateway | [`lab28/api-gateway/main.py`](lab28/api-gateway/main.py) | `fallback_used: False` |
| 9 | Components -> Prometheus/Grafana | [`lab28/monitoring/prometheus.yml`](lab28/monitoring/prometheus.yml) | Grafana screenshot + Prometheus metrics |
| 10 | Components -> LangSmith tracing | API Gateway trace `lab28_chat_pipeline` | Observability script pass |

---

## 6. Day 16 -> Day 27 lineage

Chi tiết: [`docs/day16-day27-integration-map.md`](docs/day16-day27-integration-map.md)

| Day | Capability chính | Lab 28 kế thừa |
|---:|---|---|
| 16 | Cloud infrastructure, IaC, fallback design | Hybrid Local + Kaggle runtime |
| 17 | Data pipeline, streaming | Kafka -> Prefect -> Lakehouse |
| 18 | Lakehouse | Parquet lakehouse layer |
| 19 | Qdrant, Redis feature store | Vector store + online features |
| 20 | Model serving | OpenAI-compatible vLLM endpoint |
| 21 | MLOps, MLflow | Local MLflow registry |
| 22 | LangSmith, LLMOps | Chat pipeline traces |
| 23 | Observability stack | Prometheus + Grafana |
| 24 | Governance | Config-driven platform, no hardcoded runtime values |
| 25 | GPU FinOps | Kaggle GPU only for live demo |
| 26 | Agentic routing | API Gateway as front door |
| 27 | Data defense | Smoke tests + readiness checks |

---

## 7. Hướng dẫn chạy nhanh

Chi tiết đầy đủ nằm trong [`lab28/README.md`](lab28/README.md).

```bash
cd lab28
cp .env.example .env
docker compose up -d --build
```

Run pipeline:

```bash
python scripts/01_ingest_to_kafka.py
python prefect/flows/kafka_to_delta.py
python scripts/03_delta_to_feast.py
python scripts/05_embed_to_qdrant.py
python scripts/06_register_model_mlflow.py
```

Run checks:

```bash
pytest smoke-tests/ -v
python scripts/production_readiness_check.py
python scripts/09_verify_observability.py
```

Dashboards:

| Service | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Prefect UI | http://localhost:4200 |
| Qdrant | http://localhost:6333/dashboard |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

---

## 8. 5 câu hỏi cần trả lời

### 1. Trade-offs trong kiến trúc AI platform

Thiết kế ưu tiên reliability và maintainability trước, sau đó dùng Kaggle GPU để tăng performance khi cần live demo. Data platform chạy local bằng Docker Compose nên dễ reproduce. Model inference nặng được tách sang Kaggle vLLM để local machine không cần GPU. Trade-off là network tunnel có thể chậm hoặc mất kết nối, nên API Gateway có fallback path.

### 2. Hybrid Local + Kaggle xử lý disconnect như thế nào?

Local API Gateway gọi Kaggle qua tunnel. Nếu Kaggle unavailable hoặc request timeout, API Gateway trả local fallback response thay vì crash. Khi real tunnel hoạt động, output có `fallback_used: False`; khi tunnel lỗi, output chuyển sang fallback mode. Đây là graceful degradation.

### 3. Kafka giúp decouple components như thế nào?

Kafka là event bus giữa ingestion và downstream processing. Producer chỉ publish events vào `data.raw`; Prefect, feature store, vector store hoặc các consumer tương lai có thể xử lý độc lập mà không cần sửa producer. Cách này giúp replay events và mở rộng pipeline dễ hơn.

### 4. Observability được implement như thế nào?

API Gateway expose `/metrics`, Prometheus scrape metrics, Grafana visualize. LangSmith trace chat pipeline để xem latency, fallback usage và LLM call. Docker logs và script logs thể hiện trạng thái từng integration step như Kafka consumed records, Redis features stored, Qdrant vectors stored và MLflow model registered.

### 5. Nếu service crash thì xử lý thế nào?

Nếu Kaggle/vLLM down, API Gateway dùng fallback response. Nếu Qdrant, Redis hoặc Kafka down, readiness/production check báo lỗi dependency để operator xử lý. Core API và health endpoint được tách khỏi batch pipeline nên một lỗi downstream không làm toàn bộ platform mất kiểm soát.

---

## 9. Link nộp

```text
https://github.com/Lemin9802/Day28-Lab_2A202600783_Thai-Thi-Yen-Nhi
```
