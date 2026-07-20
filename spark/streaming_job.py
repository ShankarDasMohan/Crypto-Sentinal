# spark/streaming_job.py
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, first, last, avg, stddev, count, expr, lit
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, BooleanType

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "binance_trades"

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "cryptosentinel")
PG_USER = os.getenv("PG_USER", "csuser")
PG_PASSWORD = os.getenv("PG_PASSWORD", "cspass")
JDBC_URL = f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"

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


def write_batch_to_postgres(batch_df, batch_id):
    if batch_df.rdd.isEmpty():
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
        ) \
        .withWatermark("trade_time", "2 minutes")

    # ---- Feature 1: price velocity, 1-min tumbling window ----
    price_velocity_df = parsed.groupBy(
        col("symbol"),
        window(col("trade_time"), "1 minute")
    ).agg(
        first("price").alias("first_price"),
        last("price").alias("last_price")
    ).withColumn(
        "price_velocity",
        (col("last_price") - col("first_price")) / 60.0
    ).select(
        col("symbol"),
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        col("price_velocity")
    )

    # Day 4 scope: write Feature 1 (price velocity) to feature_store.
    # Feature 2 (volume surge z-score) is computed and unit-tested in features.py;
    # full Spark port + join into this job happens Day 5 per the schedule.
    output_df = price_velocity_df.withColumn("volume_surge_z", lit(None).cast(DoubleType()))

    query = output_df.writeStream \
        .foreachBatch(write_batch_to_postgres) \
        .outputMode("append") \
        .trigger(processingTime="30 seconds") \
        .start()

    query.awaitTermination()


if __name__ == "__main__":
    main()