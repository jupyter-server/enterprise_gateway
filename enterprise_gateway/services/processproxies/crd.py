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

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = self.version = self.plural = None
        self.custom_resource_template_name = None
        self.kernel_resource_name = None

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> "CustomResourceProcessProxy":
        """Launch the process for a kernel."""
        kwargs["env"][
            "KERNEL_RESOURCE_NAME"
        ] = self.kernel_resource_name = self._determine_kernel_pod_name(**kwargs)
        kwargs["env"]["KERNEL_CRD_GROUP"] = self.group
        kwargs["env"]["KERNEL_CRD_VERSION"] = self.version
        kwargs["env"]["KERNEL_CRD_PLURAL"] = self.plural

        await super().launch_process(kernel_cmd, **kwargs)
        return self

    def terminate_container_resources(self) -> bool | None:
        """Terminate the resources for the container."""
        result = None

        if self.kernel_resource_name:
            try:
                object_name = "crd"
                delete_status = client.CustomObjectsApi().delete_namespaced_custom_object(
                    self.group,
                    self.version,
                    self.kernel_namespace,
                    self.plural,
                    self.kernel_resource_name,
                    grace_period_seconds=0,
                    propagation_policy="Background",
                )
                self.log.info(f"CRD delete_status: {delete_status}")

                result = delete_status and delete_status.get("status", None) == "Success"
                if not result:
                    # If the status indicates the CRD is not terminated, capture its current status.
                    # If None, update the result to True, else issue warning that it is not YET deleted
                    # since we still have the hard termination sequence to occur.
                    cur_status = self.get_container_status(None)
                    if cur_status is None:
                        result = True
                    else:
                        self.log.warning(
                            f"CRD {self.kernel_namespace}.{self.kernel_resource_name} is not yet deleted.  "
                            f"Current status is '{cur_status}'."
                        )

                if self.delete_kernel_namespace and not self.kernel_manager.restarting:
                    object_name = "namespace"
                    body = client.V1DeleteOptions(
                        grace_period_seconds=0, propagation_policy="Background"
                    )
                    v1_status = client.CoreV1Api().delete_namespace(
                        name=self.kernel_namespace, body=body
                    )

                    if v1_status and v1_status.status:
                        termination_status = ["Succeeded", "Failed", "Terminating"]
                        if any(status in v1_status.status for status in termination_status):
                            result = True

            except Exception as err:
                self.log.debug(f"Error occurred deleting {object_name}: {err}")
                if isinstance(err, client.rest.ApiException) and err.status == 404:
                    result = True  # okay if it's not found
                else:
                    self.log.warning(f"Error occurred deleting {object_name}: {err}")

        if result:
            self.log.debug(
                f"CustomResourceProcessProxy.terminate_container_resources, "
                f"crd: {self.kernel_namespace}.{self.kernel_resource_name}, "
                f"kernel ID: {self.kernel_id} has been terminated."
            )
            self.kernel_resource_name = None
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning(
                "CustomResourceProcessProxy.terminate_container_resources, "
                f"crd: {self.kernel_namespace}.{self.kernel_resource_name}, "
                f"kernel ID: {self.kernel_id} has not been terminated."
            )

        return result
