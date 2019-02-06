import os
import sys
import yaml
import argparse
from kubernetes import client, config
from string import Template, Formatter
import urllib3

urllib3.disable_warnings()


def launch_kubernetes_kernel(kernel_id, response_addr, spark_context_init_mode):
    # Launches a containerized kernel as a kubernetes pod.

    config.load_incluster_config()

    # Capture keywords and their values.
    keywords = dict()

    # Factory values...
    # Since jupyter lower cases the kernel directory as the kernel-name, we need to capture its case-sensitive
    # value since this is used to locate the kernel launch script within the image.
    keywords['kernel_name'] = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    keywords['kernel_id'] = kernel_id
    keywords['eg_response_address'] = response_addr
    keywords['kernel_spark_context_init_mode'] = spark_context_init_mode

    # Walk env variables looking for names prefixed with KERNEL_.  When found, set corresponding keyword value
    # with name in lower case.
    for name, value in os.environ.items():
        if name.startswith('KERNEL_'):
            keywords[name.lower()] = value

    # Read the kernel-pod yaml file, stripping off any commented lines.  This allows instances of the
    # yaml file to comment out substitution parameters since we want to fail the launch if any are left
    # unsubstituted.  Otherwise, commented out parameters could fail the launch if they had no substitutions.
    #
    yaml_template = ''
    with open(os.path.join(os.path.dirname(__file__), "kernel-pod.yaml")) as f:
        for line in f:
            line = line.split('#', 1)[0]
            yaml_template = yaml_template + line
        f.close()

    # Perform substitutions, then verify all parameters have been replaced.  If any
    # parameters still exist, print their names and exit.  If all have been replaced,
    # iterate over each document, issue creation statements.
    #
    k8s_yaml = Template(yaml_template).safe_substitute(keywords)

    # Check for non-substituted parameters - exit if found.
    #
    missing_params = [param[1] for param in Formatter().parse(k8s_yaml) if param[1]]
    if len(missing_params) > 0:
        missing_params = ['${' + param[1] + '}' for param in Formatter().parse(k8s_yaml) if param[1]]
        if len(missing_params) > 0:
            sys.exit("ERROR - The following parameters were not substituted - kernel launch terminating! {}".
                     format(missing_params))

    # For each k8s object (kind), call the appropriate API method.  Too bad there isn't a method
    # that can take a set of objects.
    #
    # Creation for additional kinds of k8s objects can be added below.  Refer to
    # https://github.com/kubernetes-client/python for API signatures.  Other examples can be found in
    # https://github.com/jupyter-incubator/enterprise_gateway/blob/master/enterprise_gateway/services/processproxies/k8s.py
    #
    kernel_namespace = keywords['kernel_namespace']
    k8s_objs = yaml.load_all(k8s_yaml)
    for k8s_obj in k8s_objs:
        if k8s_obj.get('kind'):
            if k8s_obj['kind'] == 'Pod':
                #print("{}".format(k8s_obj))  # useful for debug
                # If workingDir is not in the yaml and kernel_working_dir exists, use that as the workingDir
                if 'workingDir' not in k8s_obj['spec']['containers'][0] and 'kernel_working_dir' in keywords:
                    k8s_obj['spec']['containers'][0]['workingDir'] = keywords['kernel_working_dir']

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
    """
        Usage: launch_kubernetes_kernel 
                    [--RemoteProcessProxy.kernel-id <kernel_id>]
                    [--RemoteProcessProxy.response-address <response_addr>]
                    [--RemoteProcessProxy.spark-context-initialization-mode <mode>]
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('--RemoteProcessProxy.kernel-id', dest='kernel_id', nargs='?',
                        help='Indicates the id associated with the launched kernel.')
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')
    parser.add_argument('--RemoteProcessProxy.spark-context-initialization-mode', dest='spark_context_init_mode',
                        nargs='?', help='Indicates whether or how a spark context should be created',
                        default='none')

    arguments = vars(parser.parse_args())
    kernel_id = arguments['kernel_id']
    response_addr = arguments['response_address']
    spark_context_init_mode = arguments['spark_context_init_mode']

    launch_kubernetes_kernel(kernel_id, response_addr, spark_context_init_mode)
