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
import random
from threading import Thread

from Cryptodome.Cipher import PKCS1_v1_5, AES
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
from Cryptodome.Util.Padding import pad
from jupyter_client.connect import write_connection_file

LAUNCHER_VERSION = 1  # Indicate to server the version of this launcher (payloads may vary)

# Minimum port range size and max retries, let EG_ env values act as the default for b/c purposes
min_port_range_size = int(os.getenv('MIN_PORT_RANGE_SIZE', os.getenv('EG_MIN_PORT_RANGE_SIZE', '1000')))
max_port_range_retries = int(os.getenv('MAX_PORT_RANGE_RETRIES', os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5')))

log_level = os.getenv('LOG_LEVEL', os.getenv('EG_LOG_LEVEL', '10'))
log_level = int(log_level) if log_level.isdigit() else log_level

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


def _encrypt(connection_info_str, public_key):
    """Encrypt the connection information using a generated AES key that is then encrypted using
       the public key passed from the server.  Both are then returned in an encoded JSON payload.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
    aes_key = get_random_bytes(16)
    cipher = AES.new(aes_key, mode=AES.MODE_ECB)

    # Encrypt the connection info using the aes_key
    encrypted_connection_info = cipher.encrypt(pad(connection_info_str, 16))
    b64_connection_info = base64.b64encode(encrypted_connection_info)

    # Encrypt the aes_key using the server's public key
    imported_public_key = RSA.importKey(base64.b64decode(public_key.encode()))
    cipher = PKCS1_v1_5.new(key=imported_public_key)
    encrypted_key = base64.b64encode(cipher.encrypt(aes_key))

    # Compose the payload and Base64 encode it
    payload = {"version": LAUNCHER_VERSION, "key": encrypted_key.decode(), "conn_info": b64_connection_info.decode()}
    b64_payload = base64.b64encode(json.dumps(payload).encode(encoding='utf-8'))
    return b64_payload


def return_connection_info(connection_file, response_addr, lower_port, upper_port, kernel_id, public_key):
    """Returns the connection information corresponding to this kernel.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
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
    cf_json['pid'] = pid
    cf_json['pgid'] = os.getpgid(pid)

    # prepare socket address for handling signals
    comm_sock = prepare_comm_socket(lower_port, upper_port)
    cf_json['comm_port'] = comm_sock.getsockname()[1]
    cf_json['kernel_id'] = kernel_id

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((response_ip, response_port))
        json_content = json.dumps(cf_json).encode(encoding='utf-8')
        logger.debug("JSON Payload '{}".format(json_content))
        payload = _encrypt(json_content, public_key)
        logger.debug("Encrypted Payload '{}".format(payload))
        s.send(payload)
    finally:
        s.close()

    return comm_sock


def prepare_comm_socket(lower_port, upper_port):
    """Prepares the socket to which the server will send signal and shutdown requests.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
    sock = _select_socket(lower_port, upper_port)
    logger.info("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
    sock.listen(1)
    sock.settimeout(5)
    return sock


def _select_ports(count, lower_port, upper_port):
    """Select and return n random ports that are available and adhere to the given port range, if applicable.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
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
    """Create and return a socket whose port is available and adheres to the given port range, if applicable.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
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
    """Returns a port within the given range.  If the range is zero, the zero is returned.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
    range_size = upper_port - lower_port
    if range_size == 0:
        return 0
    return random.randint(lower_port, upper_port)


def get_server_request(sock):
    """Gets a request from the server and returns the corresponding dictionary.

       This code also exists in the R kernel-launcher's server_listener.py script.
    """
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


def server_listener(sock, parent_pid):
    """Waits for requests from the server and processes each when received.  Currently,
       these will be one of a sending a signal to the corresponding kernel process (signum) or
       stopping the listener and exiting the kernel (shutdown).

        This code also exists in the R kernel-launcher's server_listener.py script.
    """
    shutdown = False
    while not shutdown:
        request = get_server_request(sock)
        if request:
            signum = -1  # prevent logging poll requests since that occurs every 3 seconds
            if request.get('signum') is not None:
                signum = int(request.get('signum'))
                os.kill(parent_pid, signum)
            if request.get('shutdown') is not None:
                shutdown = bool(request.get('shutdown'))
            if signum != 0:
                logger.info("server_listener got request: {}".format(request))


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

    parser.add_argument('--response-address', dest='response_address', nargs='?', metavar='<ip>:<port>',
                        help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--kernel-id', dest='kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel.')
    parser.add_argument('--public-key', dest='public_key', nargs='?',
                        help='Public key used to encrypt connection information')
    parser.add_argument('--port-range', dest='port_range', nargs='?', metavar='<lowerPort>..<upperPort>',
                        help='Port range to impose for kernel ports')
    parser.add_argument('--spark-context-initialization-mode', dest='init_mode', nargs='?',
                        help='the initialization mode of the spark context: lazy, eager or none')
    parser.add_argument('--cluster-type', dest='cluster_type', nargs='?',
                        help='the kind of cluster to initialize: spark, dask, or none')
    # The following arguments are deprecated and will be used only if their mirroring arguments have no value.
    # This means that the default values for --spark-context-initialization-mode (none) and --cluster-type (spark)
    # will need to come from the mirrored args' default until deprecated items have been removed.
    parser.add_argument('connection_file', nargs='?', help='Connection file to write connection info (deprecated)')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='rpp_response_address', nargs='?',
                        metavar='<ip>:<port>',
                        help='Connection address (<ip>:<port>) for returning connection file (deprecated)')
    parser.add_argument('--RemoteProcessProxy.kernel-id', dest='rpp_kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel. (deprecated)')
    parser.add_argument('--RemoteProcessProxy.public-key', dest='rpp_public_key', nargs='?',
                        help='Public key used to encrypt connection information (deprecated)')
    parser.add_argument('--RemoteProcessProxy.port-range', dest='rpp_port_range', nargs='?',
                        metavar='<lowerPort>..<upperPort>', help='Port range to impose for kernel ports (deprecated)')
    parser.add_argument('--RemoteProcessProxy.spark-context-initialization-mode', dest='rpp_init_mode', nargs='?',
                        default='none',
                        help='the initialization mode of the spark context: lazy, eager or none (deprecated)')
    parser.add_argument('--RemoteProcessProxy.cluster-type', dest='rpp_cluster_type', nargs='?',
                        default='spark', help='the kind of cluster to initialize: spark, dask, or none (deprecated)')

    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address'] or arguments['rpp_response_address']
    kernel_id = arguments['kernel_id'] or arguments['rpp_kernel_id']
    public_key = arguments['public_key'] or arguments['rpp_public_key']
    lower_port, upper_port = _validate_port_range(arguments['port_range'] or arguments['rpp_port_range'])
    spark_init_mode = arguments['init_mode'] or arguments['rpp_init_mode']
    cluster_type = arguments['cluster_type'] or arguments['rpp_cluster_type']
    ip = "0.0.0.0"

    if connection_file is None and kernel_id is None:
        raise RuntimeError("At least one of the parameters: 'connection_file' or '--kernel-id' must be provided!")

    if kernel_id is None:
        raise RuntimeError("Parameter '--kernel-id' must be provided!")

    if public_key is None:
        raise RuntimeError("Parameter '--public-key' must be provided!")

    # If the connection file doesn't exist, then create it.
    if (connection_file and not os.path.isfile(connection_file)) or kernel_id is not None:
        key = str(uuid.uuid4()).encode()  # convert to bytes
        connection_file = determine_connection_file(connection_file, kernel_id)

        ports = _select_ports(5, lower_port, upper_port)

        write_connection_file(fname=connection_file, ip=ip, key=key, shell_port=ports[0], iopub_port=ports[1],
                              stdin_port=ports[2], hb_port=ports[3], control_port=ports[4])
        if response_addr:
            comm_socket = return_connection_info(connection_file, response_addr, lower_port, upper_port,
                                                 kernel_id, public_key)
            if comm_socket:  # socket in use, start server listener process
                server_listener_process = Process(target=server_listener, args=(comm_socket, os.getpid(),))
                server_listener_process.start()

    # Initialize the kernel namespace for the given cluster type
    if cluster_type == 'spark' and spark_init_mode == 'none':
        cluster_type = 'none'

    # launch the IPython kernel instance
    start_ipython(locals(), cluster_type=cluster_type, connection_file=connection_file, ip=ip)

    try:
        os.remove(connection_file)
    except Exception:
        pass
