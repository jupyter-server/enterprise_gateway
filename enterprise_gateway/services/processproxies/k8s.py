"""Code related to managing kernels running in Kubernetes clusters."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import logging
import os
import re
from typing import Any

import urllib3
from jinja2 import BaseLoader, Environment
from kubernetes import client, config

from ..kernels.remotemanager import RemoteKernelManager
from ..sessions.kernelsessionmanager import KernelSessionManager
from .container import ContainerProcessProxy

urllib3.disable_warnings()

# Default logging level of kubernetes produces too much noise - raise to warning only.
logging.getLogger("kubernetes").setLevel(os.environ.get("EG_KUBERNETES_LOG_LEVEL", logging.WARNING))

enterprise_gateway_namespace = os.environ.get("EG_NAMESPACE", "default")
default_kernel_service_account_name = os.environ.get(
    "EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME", "default"
)
kernel_cluster_role = os.environ.get("EG_KERNEL_CLUSTER_ROLE", "cluster-admin")
share_gateway_namespace = bool(os.environ.get("EG_SHARED_NAMESPACE", "False").lower() == "true")
kpt_dir = os.environ.get("EG_POD_TEMPLATE_DIR", "/tmp")  # noqa

config.load_incluster_config()


class KubernetesProcessProxy(ContainerProcessProxy):
    """
    Kernel lifecycle management for Kubernetes kernels.
    """

    # Identifies the kind of object being managed by this process proxy.
    # For these values we will prefer the values found in the 'kind' field
    # of the object's metadata.  This attribute is strictly used to provide
    # context to log messages.
    object_kind = "Pod"

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)

        self.kernel_pod_name = None
        self.kernel_namespace = None
        self.delete_kernel_namespace = False

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> KubernetesProcessProxy:
        """Launches the specified process within a Kubernetes environment."""
        # Set env before superclass call, so we can see these in the debug output

        # Kubernetes relies on internal env variables to determine its configuration.  When
        # running within a K8s cluster, these start with KUBERNETES_SERVICE, otherwise look
        # for envs prefixed with KUBECONFIG.
        for key in os.environ:
            if key.startswith("KUBECONFIG") or key.startswith("KUBERNETES_SERVICE"):
                kwargs["env"][key] = os.environ[key]

        # Determine pod name and namespace - creating the latter if necessary
        self.kernel_pod_name = self._determine_kernel_pod_name(**kwargs)
        self.kernel_namespace = self._determine_kernel_namespace(**kwargs)

        await super().launch_process(kernel_cmd, **kwargs)
        return self

    def get_initial_states(self) -> set:
        """Return list of states in lowercase indicating container is starting (includes running)."""
        return ["pending", "running"]

    def get_error_states(self) -> set:
        """Return list of states in lowercase indicating container failed ."""
        return ["failed"]

    def get_container_status(self, iteration: int | None) -> str:
        """Return current container state."""
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.
        pod_status = ""
        kernel_label_selector = "kernel_id=" + self.kernel_id + ",component=kernel"
        ret = client.CoreV1Api().list_namespaced_pod(
            namespace=self.kernel_namespace, label_selector=kernel_label_selector
        )
        if ret and ret.items:
            pod_info = ret.items[0]
            self.container_name = pod_info.metadata.name
            if pod_info.status:
                pod_status = pod_info.status.phase.lower()
                if pod_status == "running" and not self.assigned_host:
                    # Pod is running, capture IP
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_host = self.container_name
                    self.assigned_node_ip = pod_info.status.host_ip

        if iteration:  # only log if iteration is not None (otherwise poll() is too noisy)
            self.log.debug(
                f"{iteration}: Waiting to connect to k8s {self.object_kind.lower()} in "
                f"namespace '{self.kernel_namespace}'. Name: '{self.container_name}', "
                f"Status: '{pod_status}', Pod IP: '{self.assigned_ip}', KernelID: '{self.kernel_id}'"
            )

        return pod_status

    def delete_managed_object(self, termination_stati: list[str]) -> bool:
        """Deletes the object managed by this process-proxy

        A return value of True indicates the object is considered deleted,
        otherwise a False or None value is returned.

        Note: the caller is responsible for handling exceptions.
        """
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy="Background")

        # Deleting a Pod will return a v1.Pod if found and its status will be a PodStatus containing
        # a phase string property
        # https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.21/#podstatus-v1-core
        v1_pod = client.CoreV1Api().delete_namespaced_pod(
            namespace=self.kernel_namespace, body=body, name=self.container_name
        )
        status = None
        if v1_pod and v1_pod.status:
            status = v1_pod.status.phase

        result = status in termination_stati

        return result

    def terminate_container_resources(self) -> bool | None:
        """Terminate any artifacts created on behalf of the container's lifetime."""
        # Kubernetes objects don't go away on their own - so we need to tear down the namespace
        # and/or pod associated with the kernel.  We'll always target the pod first so that shutdown
        # is perceived as happening more rapidly.  Then, if we created the namespace, and we're not
        # in the process of restarting the kernel, we'll delete the namespace.
        # After deleting the pod we check the container status, rather than the status returned
        # from the pod deletion API, since it's not necessarily reflective of the actual status.

        result = False
        termination_stati = ["Succeeded", "Failed", "Terminating", "Success"]

        # Delete the managed object then, if applicable, the namespace
        object_type = self.object_kind
        try:
            result = self.delete_managed_object(termination_stati)
            if not result:
                # If the status indicates the object is not terminated, capture its current status.
                # If None, update the result to True, else issue warning that it is not YET deleted
                # since we still have the hard termination sequence to occur.
                cur_status = self.get_container_status(None)
                if cur_status is None:
                    result = True
                else:
                    self.log.warning(
                        f"{object_type} '{self.kernel_namespace}.{self.container_name}'"
                        f" is not yet deleted.  Current status is '{cur_status}'."
                    )

            if self.delete_kernel_namespace and not self.kernel_manager.restarting:
                object_type = "Namespace"
                # Status is a return value for calls that don't return other objects.
                # https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.21/#status-v1-meta
                body = client.V1DeleteOptions(
                    grace_period_seconds=0, propagation_policy="Background"
                )
                v1_status = client.CoreV1Api().delete_namespace(
                    name=self.kernel_namespace, body=body
                )
                status = None
                if v1_status:
                    status = v1_status.status

                if status and any(s in status for s in termination_stati):
                    result = True

                if not result:
                    self.log.warning(
                        f"Namespace {self.kernel_namespace} is not yet deleted.  "
                        f"Current status is '{status}'."
                    )

        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                result = True  # okay if it's not found
            else:
                self.log.warning(f"Error occurred deleting {object_type.lower()}: {err}")

        if result:
            self.log.debug(
                f"KubernetesProcessProxy.terminate_container_resources, "
                f"{self.object_kind}: {self.kernel_namespace}.{self.container_name}, "
                f"kernel ID: {self.kernel_id} has been terminated."
            )
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning(
                "KubernetesProcessProxy.terminate_container_resources, "
                f"{self.object_kind}: {self.kernel_namespace}.{self.container_name}, "
                f"kernel ID: {self.kernel_id} has not been terminated."
            )

        # Check if there's a kernel pod template file for this kernel and silently delete it.
        kpt_file = kpt_dir + "/kpt_" + self.kernel_id
        try:
            os.remove(kpt_file)
        except OSError:
            pass

        return result

    def _determine_kernel_pod_name(self, **kwargs: dict[str, Any] | None) -> str:
        pod_name = kwargs["env"].get("KERNEL_POD_NAME")

        if pod_name is None:
            pod_name = KernelSessionManager.get_kernel_username(**kwargs) + "-" + self.kernel_id
        else:
            self.log.debug(f"Processing KERNEL_POD_NAME based on env var => {pod_name}")
            if "{{" in pod_name and "}}" in pod_name:
                self.log.debug("Processing KERNEL_POD_NAME as jinja template")
                # Create Jinja2 environment
                keywords = {}
                for name, value in kwargs["env"].items():
                    if name.startswith("KERNEL_"):
                        keywords[name.lower()] = value
                keywords["kernel_id"] = self.kernel_id
                self.log.debug("Processing pod_name jinja template")
                env = Environment(loader=BaseLoader(), autoescape=True)
                pod_name = env.from_string(pod_name).render(**keywords)

        # Rewrite pod_name to be compatible with DNS name convention
        # And put back into env since kernel needs this
        pod_name = re.sub("[^0-9a-z]+", "-", pod_name.lower())
        while pod_name.startswith("-"):
            pod_name = pod_name[1:]
        while pod_name.endswith("-"):
            pod_name = pod_name[:-1]
        kwargs["env"]["KERNEL_POD_NAME"] = pod_name

        return pod_name

    def _determine_kernel_namespace(self, **kwargs: dict[str, Any] | None) -> str:
        # Since we need the service account name regardless of whether we're creating the namespace or not,
        # get it now.
        service_account_name = KubernetesProcessProxy._determine_kernel_service_account_name(
            **kwargs
        )

        # If KERNEL_NAMESPACE was provided, then we assume it already exists.  If not provided, then we'll
        # create the namespace and record that we'll want to delete it as well.
        namespace = kwargs["env"].get("KERNEL_NAMESPACE")
        if namespace is None:
            # check if share gateway namespace is configured...
            if share_gateway_namespace:  # if so, set to EG namespace
                namespace = enterprise_gateway_namespace
                self.log.warning(
                    "Shared namespace has been configured.  All kernels will reside in EG namespace: {}".format(
                        namespace
                    )
                )
            else:
                namespace = self._create_kernel_namespace(service_account_name)
            kwargs["env"]["KERNEL_NAMESPACE"] = namespace  # record in env since kernel needs this
        else:
            self.log.info(f"KERNEL_NAMESPACE provided by client: {namespace}")

        return namespace

    @staticmethod
    def _determine_kernel_service_account_name(**kwargs: dict[str, Any] | None) -> str:
        # Check if an account name was provided.  If not, set to the default name (which can be set
        # from the EG env as well).  Finally, ensure the env value is set.
        service_account_name = kwargs["env"].get(
            "KERNEL_SERVICE_ACCOUNT_NAME", default_kernel_service_account_name
        )
        kwargs["env"]["KERNEL_SERVICE_ACCOUNT_NAME"] = service_account_name
        return service_account_name

    def _create_kernel_namespace(self, service_account_name: str) -> str:
        # Creates the namespace for the kernel based on the kernel username and kernel id.  Since we're creating
        # the namespace, we'll also note that it should be deleted as well.  In addition, the kernel pod may need
        # to list/create other pods (true for spark-on-k8s), so we'll also create a RoleBinding associated with
        # the namespace's default ServiceAccount.  Since this is always done when creating a namespace, we can
        # delete the RoleBinding when deleting the namespace (no need to record that via another member variable).

        namespace = self.kernel_pod_name

        # create the namespace ...
        labels = {"app": "enterprise-gateway", "component": "kernel", "kernel_id": self.kernel_id}
        namespace_metadata = client.V1ObjectMeta(name=namespace, labels=labels)
        body = client.V1Namespace(metadata=namespace_metadata)

        # create the namespace
        try:
            client.CoreV1Api().create_namespace(body=body)
            self.delete_kernel_namespace = True
            self.log.info(f"Created kernel namespace: {namespace}")

            # Now create a RoleBinding for this namespace for the default ServiceAccount.  We'll reference
            # the ClusterRole, but that will only be applied for this namespace.  This prevents the need for
            # creating a role each time.
            self._create_role_binding(namespace, service_account_name)
        except Exception as err:
            if (
                isinstance(err, client.rest.ApiException)
                and err.status == 409
                and self.kernel_manager.restarting
            ):
                self.delete_kernel_namespace = (
                    True  # okay if ns already exists and restarting, still mark for delete
                )
                self.log.info(f"Re-using kernel namespace: {namespace}")
            else:
                if self.delete_kernel_namespace:
                    reason = "Error occurred creating role binding for namespace '{}': {}".format(
                        namespace, err
                    )
                    # delete the namespace since we'll be using the EG namespace...
                    body = client.V1DeleteOptions(
                        grace_period_seconds=0, propagation_policy="Background"
                    )
                    client.CoreV1Api().delete_namespace(name=namespace, body=body)
                    self.log.warning(f"Deleted kernel namespace: {namespace}")
                else:
                    reason = f"Error occurred creating namespace '{namespace}': {err}"
                self.log_and_raise(http_status_code=500, reason=reason)

        return namespace

    def _create_role_binding(self, namespace: str, service_account_name: str) -> None:
        # Creates RoleBinding instance for the given namespace.  The role used will be the ClusterRole named by
        # EG_KERNEL_CLUSTER_ROLE.
        # Note that roles referenced in RoleBindings are scoped to the namespace so re-using the cluster role prevents
        # the need for creating a new role with each kernel.
        # The ClusterRole will be bound to the kernel service user identified by KERNEL_SERVICE_ACCOUNT_NAME then
        # EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME, respectively.
        # We will not use a try/except clause here since _create_kernel_namespace will handle exceptions.

        role_binding_name = kernel_cluster_role  # use same name for binding as cluster role
        labels = {"app": "enterprise-gateway", "component": "kernel", "kernel_id": self.kernel_id}
        binding_metadata = client.V1ObjectMeta(name=role_binding_name, labels=labels)
        binding_role_ref = client.V1RoleRef(
            api_group="", kind="ClusterRole", name=kernel_cluster_role
        )
        binding_subjects = client.V1Subject(
            api_group="", kind="ServiceAccount", name=service_account_name, namespace=namespace
        )

        body = client.V1RoleBinding(
            kind="RoleBinding",
            metadata=binding_metadata,
            role_ref=binding_role_ref,
            subjects=[binding_subjects],
        )

        client.RbacAuthorizationV1Api().create_namespaced_role_binding(
            namespace=namespace, body=body
        )
        self.log.info(
            "Created kernel role-binding '{}' in namespace: {} for service account: {}".format(
                role_binding_name, namespace, service_account_name
            )
        )

    def get_process_info(self) -> dict[str, Any]:
        """Captures the base information necessary for kernel persistence relative to kubernetes."""
        process_info = super().get_process_info()
        process_info.update(
            {"kernel_ns": self.kernel_namespace, "delete_ns": self.delete_kernel_namespace}
        )
        return process_info

    def load_process_info(self, process_info: dict[str, Any]) -> None:
        """Loads the base information necessary for kernel persistence relative to kubernetes."""
        super().load_process_info(process_info)
        self.kernel_namespace = process_info["kernel_ns"]
        self.delete_kernel_namespace = process_info["delete_ns"]
