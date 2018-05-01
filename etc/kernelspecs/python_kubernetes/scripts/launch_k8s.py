import os
import argparse
import yaml
from kubernetes import client, config
from string import Template
import urllib3

urllib3.disable_warnings()

# FIXME - these should be variable...
DOCKER_IMAGE = 'elyra/k8s-kernel:dev'
COMM_PORT = '32456'
STDIN_PORT = '48691'
CONTROL_PORT = '40544'
HB_PORT = '43462'
SHELL_PORT = '44808'
IOPUB_PORT = '49691'


def main():
    # Configs can be set in Configuration class directly or using helper
    # utility. If no argument provided, the config will be loaded from
    # default location.
    config.load_kube_config(os.environ.get('EG_KUBERNETES_CONFIG'))

    kwds = dict()
    kwds['kernel_id'] = os.environ.get('KERNEL_ID')
    kwds['language'] = os.environ.get('KERNEL_LANGUAGE')
    kwds['namespace'] = os.environ.get('EG_KUBERNETES_NAMESPACE')
    kwds['response_address'] = response_addr
    kwds['docker_image'] = DOCKER_IMAGE
    kwds['comm_port'] = COMM_PORT
    kwds['stdin_port'] = STDIN_PORT
    kwds['control_port'] = CONTROL_PORT
    kwds['hb_port'] = HB_PORT
    kwds['shell_port'] = SHELL_PORT
    kwds['iopub_port'] = IOPUB_PORT

    with open(os.path.join(os.path.dirname(__file__), "kernel-service.yaml")) as f:
        yaml_template = f.read()
        f.close()
        svc = yaml.load(Template(yaml_template).substitute(kwds))
        k8s_svc_cli = client.CoreV1Api()
        resp = k8s_svc_cli.create_namespaced_service(body=svc, namespace=kwds['namespace'])
    '''
    with open(os.path.join(os.path.dirname(__file__), "kernel-deploy.yaml")) as f:
        yaml_template = f.read()
        f.close()
        dep = yaml.load(Template(yaml_template).substitute(kwds))
        k8s_dep_cli = client.AppsV1beta2Api()
        resp = k8s_dep_cli.create_namespaced_deployment(body=dep, namespace=kwds['namespace'])
    '''
    with open(os.path.join(os.path.dirname(__file__), "kernel-job.yaml")) as f:
        yaml_template = f.read()
        f.close()
        job = yaml.load(Template(yaml_template).substitute(kwds))
        k8s_job_cli = client.BatchV1Api()
        resp = k8s_job_cli.create_namespaced_job(body=job, namespace=kwds['namespace'])


if __name__ == '__main__':
    """
        Usage: launch_k8s --RemoteProcessProxy.response-address <response_addr>
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('--RemoteProcessProxy.response-address', dest='response_address', nargs='?',
                        metavar='<ip>:<port>', help='Connection address (<ip>:<port>) for returning connection file')

    arguments = vars(parser.parse_args())
    response_addr = arguments['response_address']

    main()
