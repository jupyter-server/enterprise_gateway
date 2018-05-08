import os
import yaml
from kubernetes import client, config
from string import Template
import urllib3

urllib3.disable_warnings()


def launch_kubernetes_kernel():
    # Launches a containerized kernel as a kubernetes pod.

    config.load_incluster_config()

    keywords = dict()
    keywords['kernel_id'] = os.environ.get('KERNEL_ID')
    keywords['language'] = os.environ.get('KERNEL_LANGUAGE')
    keywords['namespace'] = os.environ.get('EG_KUBERNETES_NAMESPACE')
    keywords['docker_image'] = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE')
    keywords['response_address'] = os.environ.get('EG_RESPONSE_ADDRESS')
    keywords['connection_filename'] = os.environ.get('KERNEL_CONNECTION_FILENAME')
    keywords['create_spark_context'] = os.environ.get('KERNEL_CREATE_SPARK_CONTEXT')

    with open(os.path.join(os.path.dirname(__file__), "kernel-pod.yaml")) as f:
        yaml_template = f.read()
        f.close()
        job = yaml.load(Template(yaml_template).substitute(keywords))
        client.CoreV1Api(client.ApiClient()).create_namespaced_pod(body=job, namespace=keywords['namespace'])

if __name__ == '__main__':
    launch_kubernetes_kernel()
