#!/usr/bin/env python

import sys
from IPython import embed_kernel
from pyspark.sql import SparkSession

if __name__ == "__main__":
    """
        Usage: spark-submit launch_ipykernel [connection_file]
    """
    # create a Spark session
    spark = SparkSession.builder.getOrCreate()

    # setup Spark session variables
    sc = spark.sparkContext
    sql = spark.sql

    # setup Spark legacy variables for compatibility
    sqlContext = spark._wrapped
    sqlCtx = sqlContext

    # we may have a connection file
    connection_file = sys.argv[1] if len(sys.argv) > 1 else ""

    # prevent kernel from using the loop-back IP (127.0.0.1)
    ip = "0.0.0.0"

    # launch the IPython kernel instance
    embed_kernel(connection_file=connection_file, ip=ip)

    # stop the SparkContext after the kernel is stopped/killed
    spark.stop()