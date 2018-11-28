import os
import sys
import argparse
from docker.client import DockerClient
from docker.types import EndpointSpec, RestartPolicy
import urllib3

urllib3.disable_warnings()

# Set env to False if the container should be left around for debug purposes, etc.
remove_container = bool(os.getenv('EG_REMOVE_CONTAINER', 'True').lower() == 'true')
swarm_mode = bool(os.getenv('EG_DOCKER_MODE', 'swarm').lower() == 'swarm')


def launch_docker_kernel(kernel_id, response_addr, spark_context_init_mode):
    # Launches a containerized kernel.

    # Can't proceed if no image was specified.
    image_name = os.environ.get('KERNEL_IMAGE', None)
    if image_name is None:
        sys.exit("ERROR - KERNEL_IMAGE not found in environment - kernel launch terminating!")

    # Container name is composed of KERNEL_USERNAME and KERNEL_ID
    container_name = os.environ.get('KERNEL_USERNAME', '') + '-' + kernel_id

    # Determine network. If EG_DOCKER_NETWORK has not been propagated, fall back to 'bridge'...
    docker_network = os.environ.get('EG_DOCKER_NETWORK', 'bridge')

    # Build labels - these will be modelled similar to kubernetes: kernel_id, component, app, ...
    labels = dict()
    labels['kernel_id'] = kernel_id
    labels['component'] = 'kernel'
    labels['app'] = 'enterprise-gateway'

    # Capture env parameters - including the parameters to the actual kernel launcher in the image...
    param_env = dict()
    # Since jupyter lower cases the kernel directory as the kernel-name, we need to capture its case-sensitive
    # value since this is used to locate the kernel launch script within the image.
    param_env['KERNEL_NAME'] = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    param_env['EG_RESPONSE_ADDRESS'] = response_addr
    param_env['KERNEL_SPARK_CONTEXT_INIT_MODE'] = spark_context_init_mode

    # Since the environment is specific to the kernel (per env stanza of kernelspec, KERNEL_ and ENV_WHITELIST)
    # just add the env here.
    param_env.update(os.environ)
    param_env.pop('PATH')  # Let the image PATH be used.  Since this is relative to images, we're probably safe.

    client = DockerClient.from_env()
    if swarm_mode:
        networks = list()
        networks.append(docker_network)
        mounts = list()
        mounts.append("/usr/local/share/jupyter/kernels:/usr/local/share/jupyter/kernels:ro")
        endpoint_spec = EndpointSpec(mode='dnsrr')
        restart_policy = RestartPolicy(condition='none')
        kernel_service = client.services.create(image_name,
                                               command='/usr/local/bin/bootstrap-kernel.sh',
                                               name=container_name,
                                               endpoint_spec=endpoint_spec,
                                               restart_policy=restart_policy,
                                               env=param_env,
                                               container_labels=labels,
                                               labels=labels,
                                               #mounts=mounts,   # Enable if necessary
                                               networks=networks)
    else:
        volumes = {'/usr/local/share/jupyter/kernels': {'bind': '/usr/local/share/jupyter/kernels', 'mode': 'ro'}}
        kernel_container = client.containers.run(image_name,
                                                 command='/usr/local/bin/bootstrap-kernel.sh',
                                                 name=container_name,
                                                 hostname=container_name,
                                                 environment=param_env,
                                                 labels=labels,
                                                 remove=remove_container,
                                                 network=docker_network,
                                                 #volumes=volumes,  # Enable if necessary
                                                 detach=True)


if __name__ == '__main__':
    """
        Usage: launch_docker_kernel 
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
                        default='lazy')

    arguments = vars(parser.parse_args())
    kernel_id = arguments['kernel_id']
    response_addr = arguments['response_address']
    spark_context_init_mode = arguments['spark_context_init_mode']

    launch_docker_kernel(kernel_id, response_addr, spark_context_init_mode)
