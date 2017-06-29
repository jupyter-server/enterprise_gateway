import sys
import socket
import json
import uuid
import argparse
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from IPython import embed_kernel
from pyspark.sql import SparkSession


def return_connection_info(connection_file, ip, reponse_addr):
    response_parts = response_addr.split(":")
    response_ip = response_parts[0]
    response_port = int(response_parts[1])

    key = str_to_bytes(str(uuid.uuid4()))

    write_connection_file(fname=connection_file, ip=ip, key=key)

    with open(connection_file) as fp:
        cf_json = json.load(fp)
        fp.close()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((response_ip, response_port))
        s.send(json.dumps(cf_json).encode(encoding='utf-8'))
    finally:
        s.close()

if __name__ == "__main__":
    """
        Usage: spark-submit launch_ipykernel [connection_file] [--response-address <response_addr>]
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', help='Connection file to write connection info')
    parser.add_argument('--response-address', nargs='?', metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address']  # Although argument uses dash, argparse converts to underscore.

    # create a Spark session
    spark = SparkSession.builder.getOrCreate()

    # setup Spark session variables
    sc = spark.sparkContext
    sql = spark.sql

    # setup Spark legacy variables for compatibility
    sqlContext = spark._wrapped
    sqlCtx = sqlContext

    ip = "0.0.0.0"

    if response_addr:
        return_connection_info(connection_file, ip, response_addr)

    # launch the IPython kernel instance
    embed_kernel(connection_file=connection_file, ip=ip)

    # stop the SparkContext after the kernel is stopped/killed
    spark.stop()
