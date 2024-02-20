"""Code related to managing kernels running based on k8s custom resource."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import re
from contextlib import suppress
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
    ) -> CustomResourceProcessProxy:
        """Launch the process for a kernel."""
        self.kernel_resource_name = self._determine_kernel_pod_name(**kwargs)
        kwargs["env"]["KERNEL_RESOURCE_NAME"] = self.kernel_resource_name
        kwargs["env"]["KERNEL_CRD_GROUP"] = self.group
        kwargs["env"]["KERNEL_CRD_VERSION"] = self.version
        kwargs["env"]["KERNEL_CRD_PLURAL"] = self.plural

        await super().launch_process(kernel_cmd, **kwargs)
        return self

    def get_container_status(self, iteration: int | None) -> str:
        """Determines submitted CRD application status

        Submitting a new kernel application CRD will take a while to
        reach the Running state and the submission can also fail due
        to malformation or other issues which will prevent the application
        pod to reach the desired Running state.

        This function check the CRD submission state and in case of
        success it then delegates to parent to check if the application
        pod is running.

        Returns
        -------
        Empty string if the container cannot be found otherwise.
        The pod application status in case of success on Spark Operator side
        Or the retrieved spark operator submission status in other cases (e.g. Failed)
        """

        application_state = ""

        with suppress(Exception):
            custom_resource = client.CustomObjectsApi().get_namespaced_custom_object(
                self.group,
                self.version,
                self.kernel_namespace,
                self.plural,
                self.kernel_resource_name,
            )

            if custom_resource:
                application_state = custom_resource['status']['applicationState']['state'].lower()

                if application_state in self.get_error_states():
                    exception_text = self._get_exception_text(
                        custom_resource['status']['applicationState']['errorMessage']
                    )
                    error_message = (
                        f"CRD submission for kernel {self.kernel_id} failed: {exception_text}"
                    )
                    self.log.debug(error_message)
                elif application_state == "running" and not self.assigned_host:
                    super().get_container_status(iteration)

        # only log if iteration is not None (otherwise poll() is too noisy)
        # check for running state to avoid double logging with superclass
        if iteration and application_state != "running":
            self.log.debug(
                f"{iteration}: Waiting from CRD status from resource manager {self.object_kind.lower()} in "
                f"namespace '{self.kernel_namespace}'. Name: '{self.kernel_resource_name}', "
                f"Status: '{application_state}', KernelID: '{self.kernel_id}'"
            )

        return application_state

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

    def get_initial_states(self) -> set:
        """Return list of states in lowercase indicating container is starting (includes running)."""
        return ["submitted", "pending", "running"]

    def _get_exception_text(self, error_message):
        match = re.search(r'Exception\s*:\s*(.*)', error_message, re.MULTILINE)

        if match:
            error_message = match.group(1)

        return error_message
