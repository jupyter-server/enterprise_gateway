import os
import yaml
import argparse
from kubernetes import client, config
from string import Template
import urllib3

urllib3.disable_warnings()


def launch_kubernetes_kernel(connection_file, response_addr, no_spark_context):
    # Launches a containerized kernel as a kubernetes pod.

    config.load_incluster_config()

    keywords = dict()
    keywords['kernel_id'] = os.environ.get('KERNEL_ID')
    keywords['kernel_username'] = os.environ.get('KERNEL_USERNAME')
    keywords['language'] = os.environ.get('KERNEL_LANGUAGE')
    keywords['namespace'] = os.environ.get('EG_KUBERNETES_NAMESPACE')
    keywords['docker_image'] = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE')
    keywords['response_address'] = response_addr
    keywords['connection_filename'] = connection_file
    keywords['no_spark_context'] = "--RemoteProcessProxy.no-spark-context" if no_spark_context else ""

    with open(os.path.join(os.path.dirname(__file__), "kernel-pod.yaml")) as f:
        yaml_template = f.read()
        f.close()
        job = yaml.load(Template(yaml_template).substitute(keywords))
        client.CoreV1Api(client.ApiClient()).create_namespaced_pod(body=job, namespace=keywords['namespace'])

if __name__ == '__main__':
    """
        Usage: launch_kubernetes_kernel [connection_file] [--RemoteProcessProxy.response-address <response_addr>]
                    [--RemoteProcessProxy.no-spark-context]
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('connection_file', help='Connection file to write connection info')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--RemoteProcessProxy.no-spark-context', dest='no_spark_context',
                        action='store_true', help='Indicates that no spark context should be created',
                        default=False)

    arguments = vars(parser.parse_args())
    connection_file = arguments['connection_file']
    response_addr = arguments['response_address']
    no_spark_context = arguments['no_spark_context']

    launch_kubernetes_kernel(connection_file, response_addr, no_spark_context)
