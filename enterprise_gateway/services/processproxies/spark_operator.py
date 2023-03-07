"""A spark operator process proxy."""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from __future__ import annotations

import os
import re
from contextlib import suppress

from ..kernels.remotemanager import RemoteKernelManager
from .crd import CustomResourceProcessProxy, client

enterprise_gateway_namespace = os.environ.get('EG_NAMESPACE', 'default')


class SparkOperatorProcessProxy(CustomResourceProcessProxy):
    """Spark operator process proxy."""

    # Identifies the kind of object being managed by this process proxy.
    # For these values we will prefer the values found in the 'kind' field
    # of the object's metadata.  This attribute is strictly used to provide
    # context to log messages.
    object_kind = "SparkApplication"

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = "sparkoperator.k8s.io"
        self.version = "v1beta2"
        self.plural = "sparkapplications"

    def get_initial_states(self) -> set:
        """Return list of states in lowercase indicating container is starting (includes running)."""
        return ["submitted", "pending", "running"]

    def get_container_status(self, iteration: int | None) -> str:
        """Determines if container is still active.

        Submitting a new kernel application to the spark operator
        will take a while to be Running and can also fail before it
        can actually start any pods. So we will validate that the
        application succeeds on the Spark Operator side and then
        delegate to parent to check if the application pod is running.

        Returns
        -------
        Empty string if the container cannot be found otherwise.
        The pod application status in case of success on Spark Operator side
        Or the retrieved spark operator submission status in other cases (e.g. Failed)
        """
        with suppress(Exception):
            custom_resource = client.CustomObjectsApi().get_namespaced_custom_object(
                self.group,
                self.version,
                self.kernel_namespace,
                self.plural,
                self.kernel_resource_name,
            )

            if not custom_resource:
                return ""

            application_state = custom_resource['status']['applicationState']['state'].lower()

            self.log.debug(f"Checking CRD status: {application_state}")

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

            return application_state

        return ""

    def _get_exception_text(self, error_message):
        match = re.search(r'Exception\s*:\s*(.*)', error_message, re.MULTILINE)

        if match:
            error_message = match.group(1)

        return error_message
