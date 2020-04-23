import argparse
import base64
import json
import logging
import os
import socket
import tempfile
import uuid
from future.utils import raise_from
from multiprocessing import Process
from random import random
from threading import Thread

from Cryptodome.Cipher import AES
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file


# Minimum port range size and max retries
min_port_range_size = int(os.getenv('EG_MIN_PORT_RANGE_SIZE', '1000'))
max_port_range_retries = int(os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5'))
log_level = int(os.getenv('EG_LOG_LEVEL', '10'))

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s] %(message)s')

logger = logging.getLogger('launch_ipykernel')
logger.setLevel(log_level)


class ExceptionThread(Thread):
    # Wrap thread to handle the exception
    def __init__(self, target):
        self.target = target
        self.exc = None
        Thread.__init__(self)

    def run(self):
        try:
            self.target()
        except Exception as exc:
            self.exc = exc


def initialize_namespace(namespace, cluster_type='spark'):
    """Initialize the kernel namespace.

    Parameters
    ----------
    cluster_type : {'spark', 'dask', 'none'}
        The cluster type to initialize. ``'none'`` results in no variables in
        the initial namespace.
    """
    if cluster_type == 'spark':
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            logger.info("A spark context was desired but the pyspark distribution is not present.  "
                        "Spark context creation will not occur.")
            return {}

        def initialize_spark_session():
            import atexit

            """Initialize Spark session and replace global variable
            placeholders with real Spark session object references."""
            spark = SparkSession.builder.getOrCreate()
            sc = spark.sparkContext
            sql = spark.sql
            sqlContext = spark._wrapped
            sqlCtx = sqlContext

            # Stop the spark session on exit
            atexit.register(lambda: spark.stop())

            namespace.update({'spark': spark,
                              'sc': spark.sparkContext,
                              'sql': spark.sql,
                              'sqlContext': spark._wrapped,
                              'sqlCtx': spark._wrapped})

        init_thread = ExceptionThread(target=initialize_spark_session)
        spark = WaitingForSparkSessionToBeInitialized('spark', init_thread, namespace)
        sc = WaitingForSparkSessionToBeInitialized('sc', init_thread, namespace)
        sqlContext = WaitingForSparkSessionToBeInitialized('sqlContext', init_thread, namespace)

        def sql(query):
            """Placeholder function. When called will wait for Spark session to be
            initialized and call ``spark.sql(query)``"""
            return spark.sql(query)

        namespace.update({'spark': spark,
                 'sc': sc,
                 'sql': sql,
                 'sqlContext': sqlContext,
                 'sqlCtx': sqlContext})

        init_thread.start()

    elif cluster_type == 'dask':
        import dask_yarn
        cluster = dask_yarn.YarnCluster.from_current()
        namespace.update({'cluster': cluster})
    elif cluster_type != 'none':
        raise RuntimeError("Unknown cluster_type: %r" % cluster_type)


class WaitingForSparkSessionToBeInitialized(object):
    """Wrapper object for SparkContext and other Spark session variables while the real Spark session is being
    initialized in a background thread. The class name is intentionally worded verbosely explicit as it will show up
    when executing a cell that contains only a Spark session variable like ``sc`` or ``sqlContext``.
    """

    # private and public attributes that show up for tab completion,
    # to indicate pending initialization of Spark session
    _WAITING_FOR_SPARK_SESSION_TO_BE_INITIALIZED = 'Spark Session not yet initialized ...'
    WAITING_FOR_SPARK_SESSION_TO_BE_INITIALIZED = 'Spark Session not yet initialized ...'

    # the same wrapper class is used for all Spark session variables, so we need to record the name of the variable
    def __init__(self, global_variable_name, init_thread, namespace):
        self._spark_session_variable = global_variable_name
        self._init_thread = init_thread
        self._namespace = namespace

    # we intercept all method and attribute references on our temporary Spark session variable,
    # wait for the thread to complete initializing the Spark sessions and then we forward the
    # call to the real Spark objects
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
            self._init_thread.join(timeout=None)
            exc = self._init_thread.exc
            if exc:
                raise_from(RuntimeError("Variable: {} was not initialized properly.".format(self._spark_session_variable)), exc)
            # now return attribute/function reference from actual Spark object
            return getattr(self._namespace[self._spark_session_variable], name)


def prepare_gateway_socket(lower_port, upper_port):
    sock = _select_socket(lower_port, upper_port)
    logger.info("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
    sock.listen(1)
    sock.settimeout(5)
    return sock


def _encrypt(connection_info, conn_file):
    # Block size for cipher obj can be 16, 24, or 32. 16 matches 128 bit.
    BLOCK_SIZE = 16

    # Ensure that the length of the data that will be encrypted is a
    # multiple of BLOCK_SIZE by padding with '%' on the right.
    PADDING = '%'
    pad = lambda s: s.decode("utf-8") + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING

    # Encrypt connection_info whose length is a multiple of BLOCK_SIZE using
    # AES cipher and then encode the resulting byte array using Base64.
    encryptAES = lambda c, s: base64.b64encode(c.encrypt(pad(s).encode('utf-8')))

    # Create a key using first 16 chars of the kernel-id that is burnt in
    # the name of the connection file.
    bn = os.path.basename(conn_file)
    if (bn.find("kernel-") == -1):
        logger.error("Invalid connection file name '{}'".format(conn_file))
        raise RuntimeError("Invalid connection file name '{}'".format(conn_file))

    tokens = bn.split("kernel-")
    kernel_id = tokens[1]
    key = kernel_id[0:16]
    # print("AES Encryption Key '{}'".format(key))

    # Creates the cipher obj using the key.
    cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
    payload = encryptAES(cipher, connection_info)
    return payload


def return_connection_info(connection_file, response_addr, lower_port, upper_port):
    response_parts = response_addr.split(":")
    if len(response_parts) != 2:
        logger.error("Invalid format for response address '{}'. "
                     "Assuming 'pull' mode...".format(response_addr))
        return

    response_ip = response_parts[0]
    try:
        response_port = int(response_parts[1])
    except ValueError:
        logger.error("Invalid port component found in response address '{}'. "
                     "Assuming 'pull' mode...".format(response_addr))
        return

    with open(connection_file) as fp:
        cf_json = json.load(fp)
        fp.close()

    # add process and process group ids into connection info
    pid = os.getpid()
    cf_json['pid'] = str(pid)
    cf_json['pgid'] = str(os.getpgid(pid))

    # prepare socket address for handling signals
    gateway_sock = prepare_gateway_socket(lower_port, upper_port)
    cf_json['comm_port'] = gateway_sock.getsockname()[1]

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((response_ip, response_port))
        json_content = json.dumps(cf_json).encode(encoding='utf-8')
        logger.debug("JSON Payload '{}".format(json_content))
        payload = _encrypt(json_content, connection_file)
        logger.debug("Encrypted Payload '{}".format(payload))
        s.send(payload)
    finally:
        s.close()

    return gateway_sock


def determine_connection_file(conn_file, kid):
    # If the directory exists, use the original file, else create a temporary file.
    if conn_file is None or not os.path.exists(os.path.dirname(conn_file)):
        if kid is not None:
            basename = 'kernel-' + kid
        else:
            basename = os.path.splitext(os.path.basename(conn_file))[0]
        fd, conn_file = tempfile.mkstemp(suffix=".json", prefix=basename + "_")
        os.close(fd)
        logger.debug("Using connection file '{}'.".format(conn_file))

    return conn_file


def _select_ports(count, lower_port, upper_port):
    """Select and return n random ports that are available and adhere to the given port range, if applicable."""
    ports = []
    sockets = []
    for i in range(count):
        sock = _select_socket(lower_port, upper_port)
        ports.append(sock.getsockname()[1])
        sockets.append(sock)
    for sock in sockets:
        sock.close()
    return ports


def _select_socket(lower_port, upper_port):
    """Create and return a socket whose port is available and adheres to the given port range, if applicable."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    found_port = False
    retries = 0
    while not found_port:
        try:
            sock.bind(('0.0.0.0', _get_candidate_port(lower_port, upper_port)))
            found_port = True
        except Exception:
            retries = retries + 1
            if retries > max_port_range_retries:
                raise RuntimeError(
                    "Failed to locate port within range {}..{} after {} retries!".
                    format(lower_port, upper_port, max_port_range_retries))
    return sock


def _get_candidate_port(lower_port, upper_port):
    range_size = upper_port - lower_port
    if range_size == 0:
        return 0
    return random.randint(lower_port, upper_port)


def _validate_port_range(port_range):
    # if no argument was provided, return a range of 0
    if not port_range:
        return 0, 0

    try:
        port_ranges = port_range.split("..")
        lower_port = int(port_ranges[0])
        upper_port = int(port_ranges[1])

        port_range_size = upper_port - lower_port
        if port_range_size != 0:
            if port_range_size < min_port_range_size:
                raise RuntimeError(
                    "Port range validation failed for range: '{}'.  Range size must be at least {} as specified by"
                    " env EG_MIN_PORT_RANGE_SIZE".format(port_range, min_port_range_size))
    except ValueError as ve:
        raise RuntimeError("Port range validation failed for range: '{}'.  Error was: {}".format(port_range, ve))
    except IndexError as ie:
        raise RuntimeError("Port range validation failed for range: '{}'.  Error was: {}".format(port_range, ie))

    return lower_port, upper_port


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
        if type(e) is not socket.timeout:
            raise e
    finally:
        if conn:
            conn.close()

    return request_info


def gateway_listener(sock, parent_pid):
    shutdown = False
    while not shutdown:
        request = get_gateway_request(sock)
        if request:
            signum = -1  # prevent logging poll requests since that occurs every 3 seconds
            if request.get('signum') is not None:
                signum = int(request.get('signum'))
                os.kill(parent_pid, signum)
            if request.get('shutdown') is not None:
                shutdown = bool(request.get('shutdown'))
            if signum != 0:
                logger.info("gateway_listener got request: {}".format(request))


def start_ipython(namespace, cluster_type="spark", **kwargs):
    from IPython import embed_kernel

    # create an initial list of variables to clear
    # we do this without deleting to preserve the locals so that
    # initialize_namespace isn't affected by this mutation
    to_delete = [k for k in namespace if not k.startswith('__')]

    # initialize the namespace with the proper variables
    initialize_namespace(namespace, cluster_type=cluster_type)

    # delete the extraneous variables
    for k in to_delete:
        del namespace[k]

    # Start the kernel
    embed_kernel(local_ns=namespace, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', nargs='?', help='Connection file to write connection info')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--RemoteProcessProxy.kernel-id', dest='kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel.')
    parser.add_argument('--RemoteProcessProxy.port-range', dest='port_range', nargs='?',
                        metavar='<lowerPort>..<upperPort>', help='Port range to impose for kernel ports')
    parser.add_argument('--RemoteProcessProxy.spark-context-initialization-mode', dest='init_mode', nargs='?',
                        default='none', help='the initialization mode of the spark context: lazy, eager or none')
    parser.add_argument('--RemoteProcessProxy.cluster-type', dest='cluster_type', nargs='?',
                        default='spark', help='the kind of cluster to initialize: spark, dask, or none')

    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address']
    kernel_id = arguments['kernel_id']
    lower_port, upper_port = _validate_port_range(arguments['port_range'])
    spark_init_mode = arguments['init_mode']
    cluster_type = arguments['cluster_type']
    ip = "0.0.0.0"

    if connection_file is None and kernel_id is None:
        raise RuntimeError("At least one of the parameters: 'connection_file' or "
                           "'--RemoteProcessProxy.kernel-id' must be provided!")

    # If the connection file doesn't exist, then create it.
    if (connection_file and not os.path.isfile(connection_file)) or kernel_id is not None:
        key = str_to_bytes(str(uuid.uuid4()))
        connection_file = determine_connection_file(connection_file, kernel_id)

        ports = _select_ports(5, lower_port, upper_port)

        write_connection_file(fname=connection_file, ip=ip, key=key, shell_port=ports[0], iopub_port=ports[1],
                              stdin_port=ports[2], hb_port=ports[3], control_port=ports[4])
        if response_addr:
            gateway_socket = return_connection_info(connection_file, response_addr, lower_port, upper_port)
            if gateway_socket:  # socket in use, start gateway listener thread
                gateway_listener_process = Process(target=gateway_listener, args=(gateway_socket, os.getpid(),))
                gateway_listener_process.start()

    # Initialize the kernel namespace for the given cluster type
    if cluster_type == 'spark' and spark_init_mode == 'none':
        cluster_type = 'none'

    # launch the IPython kernel instance
    start_ipython(locals(), cluster_type=cluster_type, connection_file=connection_file, ip=ip)

    try:
        os.remove(connection_file)
    except Exception:
        pass
