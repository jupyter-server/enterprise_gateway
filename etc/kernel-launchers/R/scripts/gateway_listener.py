import os
import tempfile
import json
import uuid
import signal
import random
import logging
from socket import *
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from threading import Thread

max_port_range_retries = int(os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5'))
log_level = int(os.getenv('EG_LOG_LEVEL', '10'))

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s] %(message)s')

logger = logging.getLogger('gateway_listener for R launcher')
logger.setLevel(log_level)


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


def prepare_gateway_socket(lower_port, upper_port):
    sock = _select_socket(lower_port, upper_port)
    logger.info("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
    sock.listen(1)
    sock.settimeout(5)
    return sock


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
            # fabricate shutdown.
            logger.error("Listener encountered error '{}', shutting down...".format(e))
            shutdown = dict() 
            shutdown['shutdown'] = 1
            request_info = shutdown
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
                os.kill(int(parent_pid), signum)
            if request.get('shutdown') is not None:
                shutdown = bool(request.get('shutdown'))
            if signum != 0:
                logger.debug("gateway_listener got request: {}".format(request))
        else:  # check parent
            try:
                os.kill(int(parent_pid), 0)
            except OSError as e:
                shutdown = True
                logger.info("Listener detected parent has been shutdown.")


def setup_gateway_listener(fname, parent_pid, lower_port, upper_port):
    ip = "0.0.0.0"
    key = str_to_bytes(str(uuid.uuid4()))

    gateway_socket = prepare_gateway_socket(lower_port, upper_port)

    gateway_listener_thread = Thread(target=gateway_listener, args=(gateway_socket,parent_pid,))
    gateway_listener_thread.start()

    basename = os.path.splitext(os.path.basename(fname))[0]
    fd, conn_file = tempfile.mkstemp(suffix=".json", prefix=basename + "_")
    os.close(fd)

    ports = _select_ports(5, lower_port, upper_port)

    conn_file, config = write_connection_file(fname=conn_file, ip=ip, key=key, shell_port=ports[0], iopub_port=ports[1],
                          stdin_port=ports[2], hb_port=ports[3], control_port=ports[4])
    try:
        os.remove(conn_file)
    except:
        pass

    # Add in the gateway_socket and parent_pid fields...
    config['comm_port'] = gateway_socket.getsockname()[1]
    config['pid'] = parent_pid
    
    with open(fname, 'w') as f:
        f.write(json.dumps(config, indent=2))
    return

__all__ = [
    'setup_gateway_listener',
]
