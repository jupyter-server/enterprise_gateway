#!/opt/conda/bin/python
import os
import sys
import yaml
import argparse
from kubernetes import client, config
import urllib3

from jinja2 import FileSystemLoader, Environment

urllib3.disable_warnings()

KERNEL_POD_TEMPLATE_PATH = '/kernel-pod.yaml.j2'


def generate_kernel_pod_yaml(keywords):
    """Return the kubernetes pod spec as a yaml string.

    - load jinja2 template from this file directory.
    - substitute template variables with keywords items.
    """
    j_env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)), trim_blocks=True, lstrip_blocks=True)
    # jinja2 template substitutes template variables with None though keywords doesn't
    # contain corresponding item. Therefore, no need to check if any are left unsubstituted.
    # Kubernetes API server will validate the pod spec instead.
    k8s_yaml = j_env.get_template(KERNEL_POD_TEMPLATE_PATH).render(**keywords)

    return k8s_yaml


def launch_kubernetes_kernel(kernel_id, port_range, response_addr, public_key, spark_context_init_mode):
    # Launches a containerized kernel as a kubernetes pod.

    config.load_incluster_config()

    # Capture keywords and their values.
    keywords = dict()

    # Factory values...
    # Since jupyter lower cases the kernel directory as the kernel-name, we need to capture its case-sensitive
    # value since this is used to locate the kernel launch script within the image.
    keywords['port_range'] = port_range
    keywords['public_key'] = public_key
    keywords['response_address'] = response_addr
    keywords['kernel_id'] = kernel_id
    keywords['kernel_name'] = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    keywords['kernel_spark_context_init_mode'] = spark_context_init_mode

    # Walk env variables looking for names prefixed with KERNEL_.  When found, set corresponding keyword value
    # with name in lower case.
    for name, value in os.environ.items():
        if name.startswith('KERNEL_'):
            keywords[name.lower()] = yaml.safe_load(value)

    # Substitute all template variable (wrapped with {{ }}) and generate `yaml` string.
    k8s_yaml = generate_kernel_pod_yaml(keywords)

    # For each k8s object (kind), call the appropriate API method.  Too bad there isn't a method
    # that can take a set of objects.
    #
    # Creation for additional kinds of k8s objects can be added below.  Refer to
    # https://github.com/kubernetes-client/python for API signatures.  Other examples can be found in
    # https://github.com/jupyter-incubator/enterprise_gateway/blob/master/enterprise_gateway/services/processproxies/k8s.py
    #
    kernel_namespace = keywords['kernel_namespace']
    k8s_objs = yaml.safe_load_all(k8s_yaml)
    for k8s_obj in k8s_objs:
        if k8s_obj.get('kind'):
            if k8s_obj['kind'] == 'Pod':
                #  print("{}".format(k8s_obj))  # useful for debug
                client.CoreV1Api(client.ApiClient()).create_namespaced_pod(body=k8s_obj, namespace=kernel_namespace)
            elif k8s_obj['kind'] == 'Secret':
                client.CoreV1Api(client.ApiClient()).create_namespaced_secret(body=k8s_obj, namespace=kernel_namespace)
            elif k8s_obj['kind'] == 'PersistentVolumeClaim':
                client.CoreV1Api(client.ApiClient()).create_namespaced_persistent_volume_claim(
                    body=k8s_obj, namespace=kernel_namespace)
            elif k8s_obj['kind'] == 'PersistentVolume':
                client.CoreV1Api(client.ApiClient()).create_persistent_volume(body=k8s_obj)
            else:
                sys.exit("ERROR - Unhandled Kubernetes object kind '{}' found in yaml file - kernel launch terminating!".
                      format(k8s_obj['kind']))
        else:
            sys.exit("ERROR - Unknown Kubernetes object '{}' found in yaml file - kernel launch terminating!".
                      format(k8s_obj))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel-id', dest='kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel.')
    parser.add_argument('--port-range', dest='port_range', nargs='?',
                        metavar='<lowerPort>..<upperPort>', help='Port range to impose for kernel ports')
    parser.add_argument('--response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--public-key', dest='public_key', nargs='?',
                        help='Public key used to encrypt connection information')
    parser.add_argument('--spark-context-initialization-mode', dest='spark_context_init_mode',
                        nargs='?', help='Indicates whether or how a spark context should be created')

    # The following arguments are deprecated and will be used only if their mirroring arguments have no value.
    # This means that the default value for --spark-context-initialization-mode (none) will need to come from
    # the mirrored args' default until deprecated item has been removed.
    parser.add_argument('--RemoteProcessProxy.kernel-id', dest='rpp_kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel. (deprecated)')
    parser.add_argument('--RemoteProcessProxy.port-range', dest='rpp_port_range', nargs='?',
                        metavar='<lowerPort>..<upperPort>', help='Port range to impose for kernel ports (deprecated)')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='rpp_response_address', nargs='?',
                        metavar='<ip>:<port>',
                        help='Connection address (<ip>:<port>) for returning connection file (deprecated)')
    parser.add_argument('--RemoteProcessProxy.public-key', dest='rpp_public_key', nargs='?',
                        help='Public key used to encrypt connection information (deprecated)')
    parser.add_argument('--RemoteProcessProxy.spark-context-initialization-mode', dest='rpp_spark_context_init_mode',
                        nargs='?', help='Indicates whether or how a spark context should be created (deprecated)',
                        default='none')

    arguments = vars(parser.parse_args())
    kernel_id = arguments['kernel_id'] or arguments['rpp_kernel_id']
    port_range = arguments['port_range'] or arguments['rpp_port_range']
    response_addr = arguments['response_address'] or arguments['rpp_response_address']
    public_key = arguments['public_key'] or arguments['rpp_public_key']
    spark_context_init_mode = arguments['spark_context_init_mode'] or arguments['rpp_spark_context_init_mode']

    launch_kubernetes_kernel(kernel_id, port_range, response_addr, public_key, spark_context_init_mode)
