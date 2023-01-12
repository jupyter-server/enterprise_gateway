"""Code related to managing kernels running based on k8s custom resource."""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

from typing import Any

from kubernetes import client

from ..kernels.remotemanager import RemoteKernelManager
from .k8s import KubernetesProcessProxy


class CustomResourceProcessProxy(KubernetesProcessProxy):
    """A custom resource process proxy."""

    # Identifies the kind of object being managed by this process proxy.
    # For these values we will prefer the values found in the 'kind' field
    # of the object's metadata.  This attribute is strictly used to provide
    # context to log messages.
    object_kind = "CustomResourceDefinition"

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = self.version = self.plural = None
        self.kernel_resource_name = None

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> "CustomResourceProcessProxy":
        """Launch the process for a kernel."""
        self.kernel_resource_name = self._determine_kernel_pod_name(**kwargs)
        kwargs["env"]["KERNEL_RESOURCE_NAME"] = self.kernel_resource_name
        kwargs["env"]["KERNEL_CRD_GROUP"] = self.group
        kwargs["env"]["KERNEL_CRD_VERSION"] = self.version
        kwargs["env"]["KERNEL_CRD_PLURAL"] = self.plural

        await super().launch_process(kernel_cmd, **kwargs)
        return self

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

        return result
