"""Launches a containerized kernel."""

import argparse
import os
import sys

import urllib3
from docker.client import DockerClient
from docker.types import EndpointSpec, RestartPolicy

urllib3.disable_warnings()

# Set env to False if the container should be left around for debug purposes, etc.
remove_container = bool(
    os.getenv("REMOVE_CONTAINER", os.getenv("EG_REMOVE_CONTAINER", "True")).lower() == "true"
)
swarm_mode = bool(os.getenv("DOCKER_MODE", os.getenv("EG_DOCKER_MODE", "swarm")).lower() == "swarm")


def launch_docker_kernel(
    kernel_id, port_range, response_addr, public_key, spark_context_init_mode, kernel_class_name
):
    """Launches a containerized kernel."""

    # Can't proceed if no image was specified.
    image_name = os.environ.get("KERNEL_IMAGE", None)
    if image_name is None:
        sys.exit("ERROR - KERNEL_IMAGE not found in environment - kernel launch terminating!")

    # Container name is composed of KERNEL_USERNAME and KERNEL_ID
    container_name = os.environ.get("KERNEL_USERNAME", "") + "-" + kernel_id

    # Determine network. If EG_DOCKER_NETWORK has not been propagated, fall back to 'bridge'...
    docker_network = os.environ.get("DOCKER_NETWORK", os.environ.get("EG_DOCKER_NETWORK", "bridge"))

    # Build labels - these will be modelled similar to kubernetes: kernel_id, component, app, ...
    labels = {}
    labels["kernel_id"] = kernel_id
    labels["component"] = "kernel"
    labels["app"] = "enterprise-gateway"

    # Capture env parameters...
    param_env = {}
    param_env["PORT_RANGE"] = port_range
    param_env["PUBLIC_KEY"] = public_key
    param_env["RESPONSE_ADDRESS"] = response_addr
    param_env["KERNEL_SPARK_CONTEXT_INIT_MODE"] = spark_context_init_mode
    if kernel_class_name:
        param_env["KERNEL_CLASS_NAME"] = kernel_class_name

    # Since the environment is specific to the kernel (per env stanza of kernelspec, KERNEL_ and EG_CLIENT_ENVS)
    # just add the env here.
    param_env.update(os.environ)
    param_env.pop(
        "PATH"
    )  # Let the image PATH be used.  Since this is relative to images, we're probably safe.

    user = param_env.get("KERNEL_UID")
    group = param_env.get("KERNEL_GID")

    # setup common args
    kwargs = {}
    kwargs["name"] = container_name
    kwargs["hostname"] = container_name
    kwargs["user"] = user
    kwargs["labels"] = labels

    client = DockerClient.from_env()
    if swarm_mode:
        networks = []
        networks.append(docker_network)
        # mounts = list()  # Enable if necessary
        # mounts.append("/usr/local/share/jupyter/kernels:/usr/local/share/jupyter/kernels:ro")
        endpoint_spec = EndpointSpec(mode="dnsrr")
        restart_policy = RestartPolicy(condition="none")

        # finish args setup
        kwargs["env"] = param_env
        kwargs["endpoint_spec"] = endpoint_spec
        kwargs["restart_policy"] = restart_policy
        kwargs["container_labels"] = labels
        kwargs["networks"] = networks
        kwargs["groups"] = [group, "100"]
        if param_env.get("KERNEL_WORKING_DIR"):
            kwargs["workdir"] = param_env.get("KERNEL_WORKING_DIR")
        # kwargs['mounts'] = mounts   # Enable if necessary
        # print("service args: {}".format(kwargs))  # useful for debug
        client.services.create(image_name, **kwargs)
    else:
        # volumes = {  # Enable if necessary
        #     "/usr/local/share/jupyter/kernels": {
        #         "bind": "/usr/local/share/jupyter/kernels",
        #         "mode": "ro",
        #     }
        # }

        # finish args setup
        kwargs["environment"] = param_env
        kwargs["remove"] = remove_container
        kwargs["network"] = docker_network
        kwargs["group_add"] = [group, "100"]
        kwargs["detach"] = True
        if param_env.get("KERNEL_WORKING_DIR"):
            kwargs["working_dir"] = param_env.get("KERNEL_WORKING_DIR")
        # kwargs['volumes'] = volumes   # Enable if necessary
        # print("container args: {}".format(kwargs))  # useful for debug
        client.containers.run(image_name, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kernel-id",
        dest="kernel_id",
        nargs="?",
        help="Indicates the id associated with the launched kernel.",
    )
    parser.add_argument(
        "--port-range",
        dest="port_range",
        nargs="?",
        metavar="<lowerPort>..<upperPort>",
        help="Port range to impose for kernel ports",
    )
    parser.add_argument(
        "--response-address",
        dest="response_address",
        nargs="?",
        metavar="<ip>:<port>",
        help="Connection address (<ip>:<port>) for returning connection file",
    )
    parser.add_argument(
        "--public-key",
        dest="public_key",
        nargs="?",
        help="Public key used to encrypt connection information",
    )
    parser.add_argument(
        "--spark-context-initialization-mode",
        dest="spark_context_init_mode",
        nargs="?",
        help="Indicates whether or how a spark context should be created",
    )
    parser.add_argument(
        "--kernel-class-name",
        dest="kernel_class_name",
        nargs="?",
        help="Indicates the name of the kernel class to use.  Must be a subclass of 'ipykernel.kernelbase.Kernel'.",
    )

    # The following arguments are deprecated and will be used only if their mirroring arguments have no value.
    # This means that the default value for --spark-context-initialization-mode (none) will need to come from
    # the mirrored args' default until deprecated item has been removed.
    parser.add_argument(
        "--RemoteProcessProxy.kernel-id",
        dest="rpp_kernel_id",
        nargs="?",
        help="Indicates the id associated with the launched kernel. (deprecated)",
    )
    parser.add_argument(
        "--RemoteProcessProxy.port-range",
        dest="rpp_port_range",
        nargs="?",
        metavar="<lowerPort>..<upperPort>",
        help="Port range to impose for kernel ports (deprecated)",
    )
    parser.add_argument(
        "--RemoteProcessProxy.response-address",
        dest="rpp_response_address",
        nargs="?",
        metavar="<ip>:<port>",
        help="Connection address (<ip>:<port>) for returning connection file (deprecated)",
    )
    parser.add_argument(
        "--RemoteProcessProxy.public-key",
        dest="rpp_public_key",
        nargs="?",
        help="Public key used to encrypt connection information (deprecated)",
    )
    parser.add_argument(
        "--RemoteProcessProxy.spark-context-initialization-mode",
        dest="rpp_spark_context_init_mode",
        nargs="?",
        help="Indicates whether or how a spark context should be created (deprecated)",
        default="none",
    )

    arguments = vars(parser.parse_args())
    kernel_id = arguments["kernel_id"] or arguments["rpp_kernel_id"]
    port_range = arguments["port_range"] or arguments["rpp_port_range"]
    response_addr = arguments["response_address"] or arguments["rpp_response_address"]
    public_key = arguments["public_key"] or arguments["rpp_public_key"]
    spark_context_init_mode = (
        arguments["spark_context_init_mode"] or arguments["rpp_spark_context_init_mode"]
    )
    kernel_class_name = arguments["kernel_class_name"]

    launch_docker_kernel(
        kernel_id, port_range, response_addr, public_key, spark_context_init_mode, kernel_class_name
    )
