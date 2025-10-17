"""A Ray operator process proxy."""

# Internal implementation at Apple
from __future__ import annotations

from typing import Any

from kubernetes import client

from ..kernels.remotemanager import RemoteKernelManager
from .k8s import KubernetesProcessProxy


class RayOperatorProcessProxy(KubernetesProcessProxy):
    """Ray operator process proxy."""

    object_kind = "RayCluster"

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = "ray.io"
        self.version = "v1alpha1"
        self.plural = "rayclusters"

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> RayOperatorProcessProxy:
        """Launch the process for a kernel."""
        self.kernel_resource_name = self._determine_kernel_pod_name(**kwargs)
        kwargs["env"]["KERNEL_RESOURCE_NAME"] = self.kernel_resource_name
        kwargs["env"]["KERNEL_CRD_GROUP"] = self.group
        kwargs["env"]["KERNEL_CRD_VERSION"] = self.version
        kwargs["env"]["KERNEL_CRD_PLURAL"] = self.plural

        await super().launch_process(kernel_cmd, **kwargs)
        return self

    def get_container_status(self, iteration: int | None) -> str:
        """Determines submitted Ray application status and returns unified pod state.

        This method returns the pod status (not CRD status) to maintain compatibility
        with the base class lifecycle management. The RayCluster CRD state is checked
        first to ensure the cluster is healthy, but we return pod states that the
        base class understands: 'pending', 'running', 'failed', etc.
        """
        application_state = None
        head_pod_status = None
        application_state = self._get_application_state()
        if application_state:
            self.log.debug(
                f">>> ray_operator.get_container_status: application_state {application_state}"
            )

        # Check for CRD-level errors first
        if application_state in self.get_error_states():
            error_message = (
                f"CRD submission for kernel {self.kernel_id} failed with state: {application_state}"
            )
            self.log.error(error_message)
            return "failed"  # Return pod state, not CRD state

        # If CRD is not ready yet, return "pending" to indicate still launching
        if application_state != "ready":
            self.log.debug(
                f">>> ray_operator.get_container_status: CRD not ready yet, state={application_state}"
            )
            return "pending"

        # CRD is ready, now check the actual pod status
        kernel_label_selector = "kernel_id=" + self.kernel_id + ",component=kernel"
        ret = None
        try:
            ret = client.CoreV1Api().list_namespaced_pod(
                namespace=self.kernel_namespace, label_selector=kernel_label_selector
            )
        except client.rest.ApiException as e:
            if e.status == 404:
                self.log.debug("Resetting cluster connection info as cluster deleted")
                self._reset_connection_info()
            return None

        if ret and ret.items:
            pod_info = ret.items[0]
            self.log.debug(
                f"Cluster status {application_state}, pod status {pod_info.status.phase.lower()}"
            )
            if pod_info.status:
                head_pod_status = pod_info.status.phase.lower()
                self.log.debug(
                    f">>> ray_operator.get_container_status: pod_status {head_pod_status}"
                )
                if head_pod_status == "running":
                    self.log.debug(
                        f"Pod Info name:{pod_info.metadata.name}, pod ip {pod_info.status.pod_ip}, host {self.container_name}"
                    )
                    self.container_name = pod_info.metadata.name
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_host = self.container_name
                    self.assigned_node_ip = pod_info.status.host_ip

        # only log if iteration is not None (otherwise poll() is too noisy)
        # check for running state to avoid double logging with superclass
        if iteration and head_pod_status != 'running':
            self.log.debug(
                f"{iteration}: Waiting from CRD status from resource manager {self.object_kind.lower()} in "
                f"namespace '{self.kernel_namespace}'. Name: '{self.kernel_resource_name}', "
                f"Status: CRD='{application_state}', Pod='{head_pod_status}', KernelID: '{self.kernel_id}'"
            )

        # KEY FIX: Return pod status (not CRD state) so base class poll() works correctly
        final_status = head_pod_status if head_pod_status else "pending"
        self.log.debug(
            f">>> ray_operator.get_container_status: returning pod_status={final_status} "
            f"(CRD state was {application_state})"
        )
        return final_status

    def delete_managed_object(self, termination_stati: list[str]) -> bool:
        """Deletes the object managed by this process-proxy

        A return value of True indicates the object is considered deleted,
        otherwise a False or None value is returned.

        Note: the caller is responsible for handling exceptions.
        """
        delete_status = client.CustomObjectsApi().delete_namespaced_custom_object(
            self.group,
            self.version,
            self.kernel_namespace,
            self.plural,
            self.kernel_resource_name,
            grace_period_seconds=0,
            propagation_policy="Background",
        )

        result = delete_status and delete_status.get("status", None) in termination_stati
        if result:
            self._reset_connection_info()
        return result

    def get_initial_states(self) -> set:
        """Return list of states indicating container is starting (includes running).

        Note: We return pod states (not CRD states) to maintain compatibility
        with the base class poll() implementation, which checks if the status
        returned by get_container_status() is in this set.
        """
        return ["pending", "running"]

    def get_error_states(self) -> set:
        """Return list of states indicating RayCluster has failed."""
        # Ray doesn't typically use "failed" state, but we'll include common error states
        return {"failed", "error", "unhealthy"}

    def _get_ray_cluster_status(self) -> dict:
        try:
            return client.CustomObjectsApi().get_namespaced_custom_object(
                self.group,
                self.version,
                self.kernel_namespace,
                self.plural,
                self.kernel_resource_name,
            )
        except client.rest.ApiException as e:
            if e.status == 404:
                self.log.debug("Resetting cluster connection info as cluster deleted")
                self._reset_connection_info()
            return None

    def _get_application_state(self):
        custom_resource = self._get_ray_cluster_status()

        if custom_resource is None:
            return None

        if 'status' not in custom_resource or 'state' not in custom_resource['status']:
            return None

        return custom_resource['status']['state'].lower()

    def _get_pod_status(self) -> str:
        """Get the current status of the kernel pod.
        Returns
        -------
        str
            The pod status in lowercase (e.g., 'pending', 'running', 'failed', 'unknown').
        """
        pod_status = "unknown"
        kernel_label_selector = "kernel_id=" + self.kernel_id + ",component=kernel"
        ret = client.CoreV1Api().list_namespaced_pod(
            namespace=self.kernel_namespace, label_selector=kernel_label_selector
        )
        if ret and ret.items:
            pod_info = ret.items[0]
            self.container_name = pod_info.metadata.name
            if pod_info.status:
                pod_status = pod_info.status.phase.lower()
                self.log.debug(f">>> k8s._get_pod_status: {pod_status}")

        return pod_status

    def _reset_connection_info(self):
        """Reset all connection-related attributes to their initial state.
        This is typically called when a cluster is deleted or connection is lost.
        """

        self.assigned_host = None
        self.container_name = ""
        self.assigned_node_ip = None
        self.assigned_ip = None
