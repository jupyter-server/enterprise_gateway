import os
import tempfile
import json
import uuid
import argparse
from socket import *
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from IPython import embed_kernel
from threading import Thread
import pkg_resources

can_create_spark_context = True
try:
    pkg_resources.get_distribution('pyspark')
except pkg_resources.DistributionNotFound:
    can_create_spark_context = False
else:
    from pyspark.sql import SparkSession


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


def prepare_gateway_socket():
    sock = socket(AF_INET, SOCK_STREAM)
    sock.bind(('0.0.0.0', 0))
    print("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
    sock.listen(1)
    sock.settimeout(5)
    return sock


def return_connection_info(connection_file, ip, response_addr, disable_gateway_socket):
    gateway_sock = None
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

    # add process and process group ids into connection info
    pid = os.getpid()
    cf_json['pid'] = str(pid)
    cf_json['pgid'] = str(os.getpgid(pid))

    # prepare socket address for handling signals
    if not disable_gateway_socket:
        gateway_sock = prepare_gateway_socket()
        cf_json['comm_port'] = gateway_sock.getsockname()[1]

    s = socket(AF_INET, SOCK_STREAM)
    try:
        s.connect((response_ip, response_port))
        s.send(json.dumps(cf_json).encode(encoding='utf-8'))
    finally:
        s.close()

    return gateway_sock


def determine_connection_file(conn_file):
    # If the directory exists, use the original file, else create a temporary file.
    if not os.path.exists(os.path.dirname(conn_file)):
        prev_connection_file = conn_file
        basename = os.path.splitext(os.path.basename(conn_file))[0]
        fd, conn_file = tempfile.mkstemp(suffix=".json", prefix=basename + "_")
        os.close(fd)
        print("Using connection file '{}' instead of '{}'".format(conn_file, prev_connection_file))

    return conn_file


def get_gateway_request(sock):
    conn = None
    data = ''
    request_info = None
    try:
        conn, addr = sock.accept()
        while True:
            buffer = conn.recv(1024).decode('utf-8')
            if not buffer:  # send is complete
                request_info = json.loads(data)
                break
            data = data + buffer  # append what we received until we get no more...
    except Exception as e:
        if type(e) is not timeout:
            raise e
    finally:
        if conn:
            conn.close()

    return request_info


def gateway_listener(sock):
    shutdown = False
    while not shutdown:
        request = get_gateway_request(sock)
        if request:
            if request.get('signum'):
                signum = int(request.get('signum'))
                os.kill(os.getpid(), signum)
            elif request.get('shutdown'):
                shutdown = bool(request.get('shutdown'))

if __name__ == "__main__":
    """
        Usage: spark-submit launch_ipykernel [connection_file] [--RemoteProcessProxy.response-address <response_addr>]
            [--RemoteProcessProxy.disable-gateway-socket] [--RemoteProcessProxy.no-spark-context]
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', help='Connection file to write connection info')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--RemoteProcessProxy.disable-gateway-socket', dest='disable_gateway_socket',
                        action='store_true', help='Disable use of gateway socket for extended communications',
                        default=False)
    parser.add_argument('--RemoteProcessProxy.no-spark-context', dest='no_spark_context',
                        action='store_true', help='Indicates that no spark context should be created',
                        default=False)

    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address']
    disable_gateway_socket = arguments['disable_gateway_socket']
    create_spark_context = can_create_spark_context and not arguments['no_spark_context']
    ip = "0.0.0.0"

    # placeholder objects for Spark session variables which are initialized in a background thread
    if create_spark_context:
        spark = WaitingForSparkSessionToBeInitialized(global_variable_name='spark')
        sc = WaitingForSparkSessionToBeInitialized(global_variable_name='sc')
        sqlContext = WaitingForSparkSessionToBeInitialized(global_variable_name='sqlContext')
        sqlCtx = WaitingForSparkSessionToBeInitialized(global_variable_name='sqlCtx')

        thread_to_initialize_spark_session = Thread(target=initialize_spark_session)

    # If the connection file doesn't exist, then create it.
    if not os.path.isfile(connection_file):
        key = str_to_bytes(str(uuid.uuid4()))
        connection_file = determine_connection_file(connection_file)
        write_connection_file(fname=connection_file, ip=ip, key=key)

    if response_addr:
        gateway_socket = return_connection_info(connection_file, ip, response_addr, disable_gateway_socket)
        if gateway_socket:  # socket in use, start gateway listener thread
            gateway_listener_thread = Thread(target=gateway_listener, args=(gateway_socket,))
            gateway_listener_thread.start()

    # start to initialize the Spark session in the background
    if create_spark_context:
        thread_to_initialize_spark_session.start()

    # launch the IPython kernel instance
    embed_kernel(connection_file=connection_file, ip=ip)

    try:
        os.remove(connection_file)
    except:
        pass

    # stop the SparkContext after the kernel is stopped/killed
    if create_spark_context:
        spark.stop()