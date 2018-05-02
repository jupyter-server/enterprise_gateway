import os
import tempfile
import json
import uuid
import argparse
import base64
import random
from socket import *
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from IPython import embed_kernel
from threading import Thread
from Crypto.Cipher import AES

# Determine if pyspark is present.  If not, then treat the initialization-mode
# as if 'none' was used.
can_create_spark_context = True
try:
    from pyspark.sql import SparkSession
except ImportError:
    can_create_spark_context = False

# Minimum port range size and max retries
min_port_range_size = int(os.getenv('EG_MIN_PORT_RANGE_SIZE', '1000'))
max_port_range_retries = int(os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5'))


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


def prepare_gateway_socket(lower_port, upper_port):
    sock = _select_socket(lower_port, upper_port)
    print("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
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
    encryptAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))

    # Create a key using first 16 chars of the kernel-id that is burnt in
    # the name of the connection file.
    bn = os.path.basename(conn_file)
    if (bn.find("kernel-") == -1):
        print("Invalid connection file name '{}'".format(conn_file))
        raise RuntimeError("Invalid connection file name '{}'".format(conn_file))

    tokens = bn.split("kernel-")
    kernel_id = tokens[1]
    key = kernel_id[0:16]
    # print("AES Encryption Key '{}'".format(key))

    # Creates the cipher obj using the key.
    cipher = AES.new(key)

    payload = encryptAES(cipher, connection_info)
    return payload

def return_connection_info(connection_file, response_addr, disable_gateway_socket, lower_port, upper_port):
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

    # add process and process group ids into connection info.
    pid = os.getpid()
    cf_json['pid'] = str(pid)
    cf_json['pgid'] = str(os.getpgid(pid))

    # prepare socket address for handling signals
    if not disable_gateway_socket:
        gateway_sock = prepare_gateway_socket(lower_port, upper_port)
        cf_json['comm_port'] = gateway_sock.getsockname()[1]

    s = socket(AF_INET, SOCK_STREAM)
    try:
        s.connect((response_ip, response_port))
        json_content = json.dumps(cf_json).encode(encoding='utf-8')
        print("JSON Payload '{}".format(json_content))
        payload = _encrypt(json_content, connection_file)
        print("Encrypted Payload '{}".format(payload))
        s.send(payload)
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
    sock = socket(AF_INET, SOCK_STREAM)
    found_port = False
    retries = 0
    while not found_port:
        try:
            sock.bind(('0.0.0.0', _get_candidate_port(lower_port, upper_port)))
            found_port = True
        except Exception as e:
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
        Usage: spark-submit launch_ipykernel [connection_file]
            [--RemoteProcessProxy.response-address <response_addr>]
            [--RemoteProcessProxy.disable-gateway-socket]
            [--RemoteProcessProxy.port-range <lowerPort>..<upperPort>]
            [--RemoteProcessProxy.spark-context-initialization-mode {lazy|eager|none}]
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', help='Connection file to write connection info')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--RemoteProcessProxy.disable-gateway-socket', dest='disable_gateway_socket',
                        action='store_true', help='Disable use of gateway socket for extended communications',
                        default=False)
    parser.add_argument('--RemoteProcessProxy.port-range', dest='port_range',
                        metavar='<lowerPort>..<upperPort>', help='Port range to impose for kernel ports')
    parser.add_argument('--RemoteProcessProxy.spark-context-initialization-mode', dest='init_mode', default='lazy',
                        help='the initialization mode of the spark context: lazy, eager or none')

    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address']
    disable_gateway_socket = arguments['disable_gateway_socket']
    lower_port, upper_port = _validate_port_range(arguments['port_range'])
    init_mode = arguments['init_mode']
    ip = "0.0.0.0"

    # if a spark context is desired, but pyspark is not present, we should probably
    # let it be known (as best we can) that they won't be getting a spark context.
    if not can_create_spark_context and init_mode != 'none':
        print("A spark context was desired but the pyspark distribution is not present.  "
              "Spark context creation will not occur.")

    # since 'lazy' and 'eager' behave the same, just check if not none
    create_spark_context = can_create_spark_context and init_mode != 'none'

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

        ports = _select_ports(5, lower_port, upper_port)

        write_connection_file(fname=connection_file, ip=ip, key=key, shell_port=ports[0], iopub_port=ports[1],
                              stdin_port=ports[2], hb_port=ports[3], control_port=ports[4])
        if response_addr:
            gateway_socket = return_connection_info(connection_file, response_addr, disable_gateway_socket,
                                                    lower_port, upper_port)
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
