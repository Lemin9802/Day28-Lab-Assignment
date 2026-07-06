# Lab28 - Hướng dẫn setup

Folder này là package chính để chạy Lab 28.

## 1. Chuẩn bị

- Docker Desktop
- Python 3.10+
- Git

## 2. Chạy platform

```bash
cd lab28
cp .env.example .env
docker compose up -d --build
```

## 3. Kiểm tra platform

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Kết quả mong muốn:

```text
status: ok
status: ready
```

## 4. Chạy pipeline

```bash
python scripts/01_ingest_to_kafka.py
python prefect/flows/kafka_to_delta.py
python scripts/03_delta_to_feast.py
python scripts/05_embed_to_qdrant.py
python scripts/06_register_model_mlflow.py
```

## 5. Chạy test

```bash
pytest smoke-tests/ -v
python scripts/production_readiness_check.py
python scripts/09_verify_observability.py
```

Kết quả đã verify:

```text
8 passed, 1 warning
Production Readiness Score: 14/14 = 100%
Integration 9 OK
Integration 10 OK
```

## 6. Dashboard

| Tool | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| Prefect UI | http://localhost:4200 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## 7. Evidence nộp bài

```text
screenshots/prefect_ui.png
screenshots/api_gateway.png
screenshots/grafana_dashboard.png
smoke_tests_results.png
production_readiness.png
```
