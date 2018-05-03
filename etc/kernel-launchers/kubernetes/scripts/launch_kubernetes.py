import os
import yaml
from kubernetes import client, config
from string import Template
import urllib3

urllib3.disable_warnings()

# FIXME - should these be configurable?
COMM_PORT = '32456'
STDIN_PORT = '48691'
CONTROL_PORT = '40544'
HB_PORT = '43462'
SHELL_PORT = '44808'
IOPUB_PORT = '49691'


def launch_kubernetes_kernel():
    # Launches a containerized kernel as a kubernetes Job, fronted by a service (to expose the ports).

    config.load_kube_config(os.environ.get('EG_KUBERNETES_CONFIG'))

    keywords = dict()
    keywords['kernel_id'] = os.environ.get('KERNEL_ID')
    keywords['language'] = os.environ.get('KERNEL_LANGUAGE')
    keywords['namespace'] = os.environ.get('EG_KUBERNETES_NAMESPACE')
    keywords['docker_image'] = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE')
    keywords['response_address'] = os.environ.get('EG_KERNEL_RESPONSE_ADDRESS')
    keywords['comm_port'] = COMM_PORT
    keywords['stdin_port'] = STDIN_PORT
    keywords['control_port'] = CONTROL_PORT
    keywords['hb_port'] = HB_PORT
    keywords['shell_port'] = SHELL_PORT
    keywords['iopub_port'] = IOPUB_PORT

    with open(os.path.join(os.path.dirname(__file__), "kernel-service.yaml")) as f:
        yaml_template = f.read()
        f.close()
        svc = yaml.load(Template(yaml_template).substitute(keywords))
        client.CoreV1Api(client.ApiClient()).create_namespaced_service(body=svc, namespace=keywords['namespace'])

    with open(os.path.join(os.path.dirname(__file__), "kernel-job.yaml")) as f:
        yaml_template = f.read()
        f.close()
        job = yaml.load(Template(yaml_template).substitute(keywords))
        client.BatchV1Api(client.ApiClient()).create_namespaced_job(body=job, namespace=keywords['namespace'])

if __name__ == '__main__':
    launch_kubernetes_kernel()
