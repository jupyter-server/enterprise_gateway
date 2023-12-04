"""Contains factory to create kubernetes api client instances using a single confguration"""
import os

from kubernetes import client, config
from traitlets.config import SingletonConfigurable

from enterprise_gateway.services.utils.envutils import is_env_true


class KubernetesClientFactory(SingletonConfigurable):
    """Manages kubernetes client creation from environment variables"""

    def get_kubernetes_client(self) -> client.ApiClient:
        """Get kubernetes api client with appropriate configuration
        Returns:
            ApiClient: Kubernetes API client for appropriate cluster
        """
        kubernetes_config: client.Configuration = client.Configuration()
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            # Running inside cluster
            if is_env_true('EG_USE_REMOTE_CLUSTER') and not is_env_true('EG_SHARED_NAMESPACE'):
                kubeconfig_path = os.getenv(
                    'EG_REMOTE_CLUSTER_KUBECONFIG_PATH', '/etc/kube/config/kubeconfig'
                )
                context = os.getenv('EG_REMOTE_CLUSTER_CONTEXT', None)
                config.load_kube_config(
                    client_configuration=kubernetes_config,
                    config_file=kubeconfig_path,
                    context=context,
                )
            else:
                if is_env_true('EG_USE_REMOTE_CLUSTER'):
                    self.log.warning(
                        "Cannot use EG_USE_REMOTE_CLUSTER and EG_SHARED_NAMESPACE at the same time. Using local cluster...."
                    )

                config.load_incluster_config(client_configuration=kubernetes_config)
        else:
            config.load_kube_config(client_configuration=kubernetes_config)

        self.log.debug(f"Created kubernetes client for host {kubernetes_config.host}")
        return client.ApiClient(kubernetes_config)
