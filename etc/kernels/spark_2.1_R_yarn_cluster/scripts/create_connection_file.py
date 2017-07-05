import argparse
from jupyter_client.connect import write_connection_file

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', help='Connection file to write connection info')
    parser.add_argument('ip', help='IP address of the local system')
    parser.add_argument('key', help='Generated UUID to be used as key to secure session')
    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    ip = arguments['ip']
    key = arguments['key']

    write_connection_file(fname=connection_file, ip=ip, key=key)
