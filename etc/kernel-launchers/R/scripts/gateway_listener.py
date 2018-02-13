import os
import tempfile
import json
import uuid
import signal
from socket import *
from ipython_genutils.py3compat import str_to_bytes
from jupyter_client.connect import write_connection_file
from threading import Thread

def prepare_gateway_socket():
    sock = socket(AF_INET, SOCK_STREAM)
    sock.bind(('0.0.0.0', 0))
    print("Signal socket bound to host: {}, port: {}".format(sock.getsockname()[0], sock.getsockname()[1]))
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
            print("Listener encountered error '{}', shutting down...".format(e))
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
            print("Received request {}".format(request))
            if request.get('signum'):
                signum = int(request.get('signum'))
                os.kill(int(parent_pid), signum)
            elif request.get('shutdown'):
                shutdown = bool(request.get('shutdown'))
                if shutdown:
                    print("Listener received shutdown request, terminating parent (pid: {}).".format(parent_pid))
                    os.kill(int(parent_pid), signal.SIGTERM)
        else:  # check parent
            try:
                os.kill(int(parent_pid), 0)
            except OSError as e:
                shutdown = True
                print("Listener detected parent has been shutdown.")


def setup_gateway_listener(fname, parent_pid):
    ip = "0.0.0.0"
    key = str_to_bytes(str(uuid.uuid4()))

    gateway_socket = prepare_gateway_socket()

    gateway_listener_thread = Thread(target=gateway_listener, args=(gateway_socket,parent_pid,))
    gateway_listener_thread.start()

    prev_connection_file = fname
    basename = os.path.splitext(os.path.basename(fname))[0]
    fd, conn_file = tempfile.mkstemp(suffix=".json", prefix=basename + "_")
    os.close(fd)
    conn_file, config = write_connection_file(conn_file, ip=ip, key=key)
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
