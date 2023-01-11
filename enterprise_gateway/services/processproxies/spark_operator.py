"""A spark operator process proxy."""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from __future__ import annotations

import os

from ..kernels.remotemanager import RemoteKernelManager
from .crd import CustomResourceProcessProxy, client

enterprise_gateway_namespace = os.environ.get("EG_NAMESPACE", "default")


class SparkOperatorProcessProxy(CustomResourceProcessProxy):
    """Spark operator process proxy."""

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = "sparkoperator.k8s.io"
        self.version = "v1beta2"
        self.plural = "sparkapplications"

    def get_container_status(self, iteration: int) -> str:
        """Get the container status for a given iteration."""
        pod_status = pod_info = None

        try:
            custom_resource = client.CustomObjectsApi().get_namespaced_custom_object(
                self.group,
                self.version,
                self.kernel_namespace,
                self.plural,
                self.kernel_resource_name,
            )

            if custom_resource:
                if iteration:
                    self.log.debug(f"CRD.get_namespaced_custom_object returns: {custom_resource}")
                self.container_name = custom_resource["status"]["driverInfo"]["podName"]
                pod_info = client.CoreV1Api().read_namespaced_pod(
                    self.container_name, self.kernel_namespace
                )
                if iteration:
                    self.log.debug(f"CRD.read_namespaced_pod returns: {pod_info}")
        except Exception as ex:
            self.log.warning(
                f"Failure occurred obtaining status of Spark Operator '{self.container_name}', ex: {ex}"
            )
            pass

        if pod_info and pod_info.status:
            pod_status = pod_info.status.phase
            if pod_status == "Running" and self.assigned_host == "":
                self.assigned_ip = pod_info.status.pod_ip
                self.assigned_host = pod_info.metadata.name
                self.assigned_node_ip = pod_info.status.host_ip

        return pod_status
