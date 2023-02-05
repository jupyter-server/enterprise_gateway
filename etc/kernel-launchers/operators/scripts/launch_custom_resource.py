#!/opt/conda/bin/python
"""Launch a custom operator resource."""
import argparse
import os
import sys

import urllib3
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from kubernetes import client, config

urllib3.disable_warnings()


def generate_kernel_custom_resource_yaml(kernel_crd_template, keywords):
    """Generate the kernel custom resource yaml given a template."""
    j_env = Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape(
            disabled_extensions=(
                "j2",
                "yaml",
            ),
            default_for_string=True,
            default=True,
        ),
    )
    k8s_yaml = j_env.get_template("/" + kernel_crd_template + ".yaml.j2").render(**keywords)
    return k8s_yaml


def extend_operator_env(op_def: dict, sub_spec: str) -> dict:
    """Extends the op_def.spec.sub_spec.env stanza with current environment."""
    env_stanza = op_def["spec"][sub_spec].get("env") or []

    # Walk current set of template env entries and replace those found in the current
    # env with their values (and record those items).   Then add all others from the env
    # that were not already.
    processed_entries: list[str] = []
    for item in env_stanza:
        item_name = item.get("name")
        if item_name in os.environ:
            item["value"] = os.environ[item_name]
            processed_entries.append(item_name)

    for name, value in os.environ.items():
        if name not in processed_entries:
            env_stanza.append({"name": name, "value": value})

    op_def["spec"][sub_spec]["env"] = env_stanza
    return op_def


def launch_custom_resource_kernel(
    kernel_id, port_range, response_addr, public_key, spark_context_init_mode
):
    """Launch a custom resource kernel."""
    config.load_incluster_config()

    keywords = {}

    keywords["eg_port_range"] = port_range
    keywords["eg_public_key"] = public_key
    keywords["eg_response_address"] = response_addr
    keywords["kernel_id"] = kernel_id
    keywords["kernel_name"] = os.path.basename(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    keywords["spark_context_initialization_mode"] = spark_context_init_mode

    for name, value in os.environ.items():
        if name.startswith("KERNEL_"):
            keywords[name.lower()] = yaml.safe_load(value)

    kernel_crd_template = keywords["kernel_crd_group"] + "-" + keywords["kernel_crd_version"]
    custom_resource_yaml = generate_kernel_custom_resource_yaml(kernel_crd_template, keywords)

    kernel_namespace = keywords["kernel_namespace"]
    group = keywords["kernel_crd_group"]
    version = keywords["kernel_crd_version"]
    plural = keywords["kernel_crd_plural"]
    custom_resource_object = yaml.safe_load(custom_resource_yaml)
    if group == "sparkoperator.k8s.io":
        extend_operator_env(custom_resource_object, "driver")
        extend_operator_env(custom_resource_object, "executor")

    try:
        client.CustomObjectsApi().create_namespaced_custom_object(
            group, version, kernel_namespace, plural, custom_resource_object
        )
    except client.exceptions.ApiException as ex:
        if ex.status == 404:
            sys.exit(
                "\nERROR: The Kubernetes Operator for Apache Spark does not appear to be installed.  "
                "See 'https://github.com/GoogleCloudPlatform/spark-on-k8s-operator#installation' for "
                "instructions, then retry the operation.\n"
            )
        else:
            print("ERROR processing Kubernetes Operator CRD - kernel launch terminating!")
            print(custom_resource_yaml)
        raise ex


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kernel-id",
        "--RemoteProcessProxy.kernel-id",
        dest="kernel_id",
        nargs="?",
        help="Indicates the id associated with the launched kernel.",
    )
    parser.add_argument(
        "--port-range",
        "--RemoteProcessProxy.port-range",
        dest="port_range",
        nargs="?",
        metavar="<lowerPort>..<upperPort>",
        help="Port range to impose for kernel ports",
    )
    parser.add_argument(
        "--response-address",
        "--RemoteProcessProxy.response-address",
        dest="response_address",
        nargs="?",
        metavar="<ip>:<port>",
        help="Connection address (<ip>:<port>) for returning connection file",
    )
    parser.add_argument(
        "--public-key",
        "--RemoteProcessProxy.public-key",
        dest="public_key",
        nargs="?",
        help="Public key used to encrypt connection information",
    )
    parser.add_argument(
        "--spark-context-initialization-mode",
        "--RemoteProcessProxy.spark-context-initialization-mode",
        dest="spark_context_init_mode",
        nargs="?",
        help="Indicates whether or how a spark context should be created",
        default="none",
    )

    arguments = vars(parser.parse_args())
    kernel_id = arguments["kernel_id"]
    port_range = arguments["port_range"]
    response_addr = arguments["response_address"]
    public_key = arguments["public_key"]
    spark_context_init_mode = arguments["spark_context_init_mode"]

    launch_custom_resource_kernel(
        kernel_id, port_range, response_addr, public_key, spark_context_init_mode
    )
