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

    def get_container_status(self, iteration):
        """Determines if container is still active.

        Submitting a new kernel application to the spark operator
        will take a while to be Running and can also fail before it
        can actually start any pods. So we will validate that the
        application succeeds on the Spark Operator side and then
        delegate to parent to check if the application pod is running.

        Returns
        -------
        None if the container cannot be found otherwise.
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
                return None

            application_state = custom_resource['status']['applicationState']['state']

            self.log.debug(
                f"Checking CRD status: {custom_resource['status']['applicationState']['state']}"
            )
            if application_state.lower() in self.get_error_states():
                exception_text = self._get_exception_text(
                    custom_resource['status']['applicationState']['errorMessage']
                )
                error_message = (
                    f"CRD submission for kernel {self.kernel_id} failed: {exception_text}"
                )

                self.log.debug(error_message)

            if application_state.lower() in self.get_initial_states():
                # retrieve the actual pod application status
                return super.get_container_status()
            else:
                return application_state

            # should raise error to flow the fail details?
            # if application_state == "FAILED":
            #     application_status_message = custom_resource['status']['applicationState'][
            #         'errorMessage'
            #     ]
            #     error_message = (
            #         f"Error starting kernel: {application_status_message.splitlines}"
            #     )
            #     raise RuntimeError(error_message)

        return None
