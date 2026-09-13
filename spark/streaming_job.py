# spark/streaming_job.py
import os
import statistics
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, LongType,
    BooleanType, TimestampType, ArrayType
)
from pyspark.sql.streaming.state import GroupStateTimeout, GroupState

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "binance_trades"

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "cryptosentinel")
PG_USER = os.getenv("PG_USER", "csuser")
PG_PASSWORD = os.getenv("PG_PASSWORD", "cspass")
JDBC_URL = f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"

BUCKET_MS = 60_000       # 1-minute buckets, matches original Feature 1/4 window
HISTORY_MAX = 30         # keep last 30 closed buckets (~30 min) for z-score baseline
TIMEOUT_SLACK_MS = 120_000  # force-close an open bucket after ~2 min of silence

# Schema of the "data" payload nested inside {"stream": ..., "data": {...}}
trade_data_schema = StructType([
    StructField("e", StringType()),
    StructField("E", LongType()),
    StructField("s", StringType()),
    StructField("t", LongType()),
    StructField("p", StringType()),
    StructField("q", StringType()),
    StructField("T", LongType()),
    StructField("m", BooleanType()),
    StructField("M", BooleanType()),
])

envelope_schema = StructType([
    StructField("stream", StringType()),
    StructField("data", trade_data_schema),
])

# Output row schema — matches feature_store's writable columns
output_schema = StructType([
    StructField("symbol", StringType()),
    StructField("window_start", TimestampType()),
    StructField("window_end", TimestampType()),
    StructField("price_velocity", DoubleType()),
    StructField("volume_surge_z", DoubleType()),
    StructField("trade_frequency", LongType()),
    StructField("spread_anomaly_score", DoubleType()),
])

# Per-symbol state carried between micro-batches
state_schema = StructType([
    StructField("bucket_start_ms", LongType()),
    StructField("first_price", DoubleType()),
    StructField("last_price", DoubleType()),
    StructField("volume_sum", DoubleType()),
    StructField("trade_count", LongType()),
    StructField("maker_sum", DoubleType()),
    StructField("hist_volumes", ArrayType(DoubleType())),
    StructField("hist_maker_ratios", ArrayType(DoubleType())),
])


def update_features_state(key, pdf_iterator, state: GroupState):
    """
    Per-symbol stateful bucket builder. Replaces the self-join approach:
    each trade updates in-memory accumulators directly, no windowed
    aggregation joined against another windowed aggregation.
    """
    (symbol,) = key

    if state.exists:
        s = state.get
        cur_bucket_start_ms = s[0]
        first_price = s[1]
        last_price = s[2]
        volume_sum = s[3]
        trade_count = s[4]
        maker_sum = s[5]
        hist_volumes = list(s[6]) if s[6] is not None else []
        hist_maker_ratios = list(s[7]) if s[7] is not None else []
    else:
        cur_bucket_start_ms = None
        first_price = None
        last_price = None
        volume_sum = 0.0
        trade_count = 0
        maker_sum = 0.0
        hist_volumes = []
        hist_maker_ratios = []

    output_rows = []

    def finalize_bucket(bucket_start_ms):
        nonlocal trade_count, volume_sum, maker_sum, first_price, last_price
        nonlocal hist_volumes, hist_maker_ratios
        if trade_count == 0:
            return
        window_start = pd.Timestamp(bucket_start_ms, unit="ms", tz="UTC")
        window_end = pd.Timestamp(bucket_start_ms + BUCKET_MS, unit="ms", tz="UTC")
        price_velocity = (last_price - first_price) / 60.0 if trade_count >= 2 else 0.0
        maker_ratio = maker_sum / trade_count

        if len(hist_volumes) >= 2 and statistics.stdev(hist_volumes) != 0:
            volume_surge_z = (volume_sum - statistics.mean(hist_volumes)) / statistics.stdev(hist_volumes)
        else:
            volume_surge_z = None

        if len(hist_maker_ratios) >= 2 and statistics.stdev(hist_maker_ratios) != 0:
            spread_anomaly_score = (maker_ratio - statistics.mean(hist_maker_ratios)) / statistics.stdev(hist_maker_ratios)
        else:
            spread_anomaly_score = None

        output_rows.append({
            "symbol": symbol,
            "window_start": window_start,
            "window_end": window_end,
            "price_velocity": price_velocity,
            "volume_surge_z": volume_surge_z,
            "trade_frequency": trade_count,
            "spread_anomaly_score": spread_anomaly_score,
        })

        hist_volumes.append(volume_sum)
        hist_maker_ratios.append(maker_ratio)
        if len(hist_volumes) > HISTORY_MAX:
            hist_volumes.pop(0)
        if len(hist_maker_ratios) > HISTORY_MAX:
            hist_maker_ratios.pop(0)

    if state.hasTimedOut:
        # Symbol went quiet — force-close whatever bucket was open.
        if cur_bucket_start_ms is not None:
            finalize_bucket(cur_bucket_start_ms)
        cur_bucket_start_ms = None
        first_price = None
        last_price = None
        volume_sum = 0.0
        trade_count = 0
        maker_sum = 0.0
    else:
        for pdf in pdf_iterator:
            pdf = pdf.sort_values("trade_time")
            for _, row in pdf.iterrows():
                t_ms = int(row["trade_time"].value // 10**6)
                bucket_start_ms = (t_ms // BUCKET_MS) * BUCKET_MS
                price = float(row["price"])
                qty = float(row["quantity"])
                maker = float(row["is_buyer_maker"])

                if cur_bucket_start_ms is None:
                    cur_bucket_start_ms = bucket_start_ms
                    first_price = price
                    last_price = price
                    volume_sum = qty
                    trade_count = 1
                    maker_sum = maker
                elif bucket_start_ms == cur_bucket_start_ms:
                    last_price = price
                    volume_sum += qty
                    trade_count += 1
                    maker_sum += maker
                elif bucket_start_ms > cur_bucket_start_ms:
                    finalize_bucket(cur_bucket_start_ms)
                    cur_bucket_start_ms = bucket_start_ms
                    first_price = price
                    last_price = price
                    volume_sum = qty
                    trade_count = 1
                    maker_sum = maker
                else:
                    # [Inference] late trade for an already-closed bucket — dropped,
                    # not re-aggregated. Acceptable for near-real-time trade data.
                    pass

    if cur_bucket_start_ms is not None:
        state.update((
            cur_bucket_start_ms, first_price, last_price,
            volume_sum, trade_count, maker_sum,
            hist_volumes, hist_maker_ratios
        ))
        state.setTimeoutTimestamp(cur_bucket_start_ms + BUCKET_MS + TIMEOUT_SLACK_MS)
    else:
        state.update((
            None, None, None, 0.0, 0, 0.0, hist_volumes, hist_maker_ratios
        ))

    if output_rows:
        yield pd.DataFrame(output_rows)
    else:
        yield pd.DataFrame(columns=[f.name for f in output_schema.fields])


def write_batch_to_postgres(batch_df, batch_id):
    row_count = batch_df.count()
    print(f"[batch {batch_id}] rows: {row_count}")
    if row_count == 0:
        return
    batch_df.write.format("jdbc").option("url", JDBC_URL) \
        .option("dbtable", "feature_store") \
        .option("user", PG_USER) \
        .option("password", PG_PASSWORD) \
        .option("driver", "org.postgresql.Driver") \
        .mode("append").save()


def main():
    spark = SparkSession.builder \
        .appName("CryptoSentinelFeatures") \
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.3") \
        .config("spark.sql.caseSensitive", "true") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    raw = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()

    parsed = raw.selectExpr("CAST(value AS STRING) AS json_str") \
        .select(from_json(col("json_str"), envelope_schema).alias("envelope")) \
        .select(
            col("envelope.data.s").alias("symbol"),
            col("envelope.data.p").cast(DoubleType()).alias("price"),
            col("envelope.data.q").cast(DoubleType()).alias("quantity"),
            (col("envelope.data.T") / 1000).cast("timestamp").alias("trade_time"),
            col("envelope.data.m").cast(DoubleType()).alias("is_buyer_maker"),
        ) \
        .withWatermark("trade_time", "2 minutes")

    output_df = parsed.groupBy("symbol").applyInPandasWithState(
        func=update_features_state,
        outputStructType=output_schema,
        stateStructType=state_schema,
        outputMode="append",
        timeoutConf=GroupStateTimeout.EventTimeTimeout
    )
    query = output_df.writeStream \
    .foreachBatch(write_batch_to_postgres) \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/cryptosentinel_checkpoints/streaming_job") \
    .trigger(processingTime="30 seconds") \
    .start()

    query.awaitTermination()


if __name__ == "__main__":
    main()