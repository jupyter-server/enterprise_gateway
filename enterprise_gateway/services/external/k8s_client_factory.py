"""Contains factory to create kubernetes api client instances using a single confguration"""
import os

from kubernetes import client, config
from traitlets.config import SingletonConfigurable


class KubernetesClientFactory(SingletonConfigurable):
    """Manages kubernetes client creation from environment variables"""
    def __init__(self) -> None:
        """Maintain a single configuration object and populate based on environment"""
        super().__init__()

    def get_kubernetes_client(self, get_remote_client: bool = True) -> client.ApiClient:
        """Get kubernetes api client with appropriate configuration

        Args:
            get_remote_client (bool): Return a client for the remote cluster if configured. Else, return incluster config. Defaults to True.

        Returns:
            ApiClient: Kubernetes API client for appropriate cluster
        """
        kubernetes_config: client.Configuration = client.Configuration()
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            # Running inside cluster
            if os.getenv('EG_USE_REMOTE_CLUSTER') and get_remote_client:
                kubeconfig_path = os.getenv('EG_REMOTE_CLUSTER_KUBECONFIG_PATH', '/etc/kube/config/')
                context = os.getenv('EG_REMOTE_CLUSTER_CONTEXT', None)
                config.load_kube_config(client_configuration=kubernetes_config, config_file=kubeconfig_path, context=context)
            else:
                config.load_incluster_config(client_configuration=kubernetes_config)
        else:
            config.load_kube_config(client_configuration=kubernetes_config)

        self.log.debug(
            f"Created kubernetes client for host {kubernetes_config.host}"
        )
        return client.ApiClient(kubernetes_config)
