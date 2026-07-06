# prefect/flows/kafka_to_delta.py
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from kafka import KafkaConsumer
from prefect import flow, task


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "data.raw")
DELTA_LAKE_PATH = Path(os.getenv("DELTA_LAKE_PATH", "/opt/delta-lake/raw"))


@task(retries=3, retry_delay_seconds=5)
def consume_and_process() -> list[dict]:
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=f"lab28-prefect-{int(time.time())}",
        consumer_timeout_ms=5000,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    records = [msg.value for msg in consumer]
    print(f"Consumed {len(records)} records from Kafka topic {KAFKA_TOPIC}")
    return records


@task
def save_to_delta(records: list[dict]) -> str | None:
    if not records:
        print("No records to save")
        return None

    DELTA_LAKE_PATH.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    output_path = DELTA_LAKE_PATH / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} records to Delta Lake path {output_path}")
    return str(output_path)


@flow(name="Kafka to Delta Pipeline")
def kafka_to_delta_flow() -> str | None:
    records = consume_and_process()
    return save_to_delta(records)


if __name__ == "__main__":
    mode = os.getenv("PREFECT_MODE", "run")
    if mode == "serve":
        kafka_to_delta_flow.serve(name="kafka-to-delta", interval=300)
    else:
        kafka_to_delta_flow()
