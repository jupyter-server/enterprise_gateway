import os.path
import socket
import json
import uuid
import argparse
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from IPython import embed_kernel
from pyspark.sql import SparkSession
from threading import Thread


class WaitingForSparkSessionToBeInitialized(object):
    """Wrapper object for SparkContext and other Spark session variables while the real Spark session is being
    initialized in a background thread. The class name is intentionally worded verbosely explicit as it will show up
    when executing a cell that contains only a Spark session variable like ``sc`` or ``sqlContext``.
    """

    # private and public attributes that show up for tab completion, to indicate pending initialization of Spark session
    _WAITING_FOR_SPARK_SESSION_TO_BE_INITIALIZED = 'Spark Session not yet initialized ...'
    WAITING_FOR_SPARK_SESSION_TO_BE_INITIALIZED = 'Spark Session not yet initialized ...'

    # the same wrapper class is used for all Spark session variables, so we need to record the name of the variable
    def __init__(self, global_variable_name):
        self._spark_session_variable = global_variable_name

    # we intercept all method and attribute references on our temporary Spark session variable, wait for the thread to
    # complete initializing the Spark sessions and then we forward the call to the real Spark objects
    def __getattr__(self, name):
        # ignore tab-completion request for __members__ or __methods__ and ignore meta property requests
        if name.startswith("__"):
            pass
        elif name.startswith("_ipython_"):
            pass
        elif name.startswith("_repr_"):
            pass
        else:
            # wait on thread to initialize the Spark session variables in global variable scope
            thread_to_initialize_spark_session.join(timeout=None)
            # now return attribute/function reference from actual Spark object
            return getattr(globals()[self._spark_session_variable], name)


def initialize_spark_session():
    """Initialize Spark session and replace global variable placeholders with real Spark session object references."""
    global spark, sc, sql, sqlContext, sqlCtx
    spark = SparkSession.builder.getOrCreate()
    sc = spark.sparkContext
    sql = spark.sql
    sqlContext = spark._wrapped
    sqlCtx = sqlContext


def sql(query):
    """Placeholder function. When called will wait for Spark session to be initialized and call ``spark.sql(query)``"""
    return spark.sql(query)


# placeholder objects for Spark session variables which are initialized in a background thread
spark = WaitingForSparkSessionToBeInitialized(global_variable_name='spark')
sc = WaitingForSparkSessionToBeInitialized(global_variable_name='sc')
sqlContext = WaitingForSparkSessionToBeInitialized(global_variable_name='sqlContext')
sqlCtx = WaitingForSparkSessionToBeInitialized(global_variable_name='sqlCtx')

thread_to_initialize_spark_session = Thread(target=initialize_spark_session)


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
    ip = "0.0.0.0"

    # If the connection file doesn't exist, then we're using 'pull' or 'socket' mode - otherwise 'push' mode.
    # If 'pull' or 'socket', create the file, then return it to server (if response address provided, i.e., 'socket')
    if not os.path.isfile(connection_file):
        key = str_to_bytes(str(uuid.uuid4()))
        write_connection_file(fname=connection_file, ip=ip, key=key)

        if response_addr:
            return_connection_info(connection_file, ip, response_addr)

    # start to initialize the Spark session in the background
    thread_to_initialize_spark_session.start()

    # launch the IPython kernel instance
    embed_kernel(connection_file=connection_file, ip=ip)

    # stop the SparkContext after the kernel is stopped/killed
    spark.stop()
