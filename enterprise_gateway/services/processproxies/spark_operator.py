"""A spark operator process proxy."""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from __future__ import annotations

from ..kernels.remotemanager import RemoteKernelManager
from .crd import CustomResourceProcessProxy


class SparkOperatorProcessProxy(CustomResourceProcessProxy):
    """Spark operator process proxy."""

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.group = "sparkoperator.k8s.io"
        self.version = "v1beta2"
        self.plural = "sparkapplications"

    @staticmethod
    def get_k8s_object_type() -> str:
        """Returns the object type managed by this process-proxy"""
        return "sparkapplication"
