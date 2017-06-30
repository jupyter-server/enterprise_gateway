import os.path
import socket
import json
import uuid
import argparse
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from IPython import embed_kernel
from pyspark.sql import SparkSession


def return_connection_info(connection_file, ip, response_addr):
    response_parts = response_addr.split(":")
    if len(response_parts) != 2:
        print("Invalid format for response address '{}'.  Assuming 'pull' mode...".format(response_addr))
        return

    response_ip = response_parts[0]
    try:
        response_port = int(response_parts[1])
    except ValueError:
        print("Invalid port component found in response address '{}'.  Assuming 'pull' mode...".format(response_addr))
        return

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

    # If the connection file doesn't exist, then we're using 'pull' or 'socket' mode - otherwise 'push' mode.
    # If 'pull' or 'socket', create the file, then return it to server (if response address provided, i.e., 'socket')
    if not os.path.isfile(connection_file):
        key = str_to_bytes(str(uuid.uuid4()))
        write_connection_file(fname=connection_file, ip=ip, key=key)

        if response_addr:
            return_connection_info(connection_file, ip, response_addr)

    # launch the IPython kernel instance
    embed_kernel(connection_file=connection_file, ip=ip)

    # stop the SparkContext after the kernel is stopped/killed
    spark.stop()
