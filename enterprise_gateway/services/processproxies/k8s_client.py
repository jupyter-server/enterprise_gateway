"""Instantiates a static global factory and a single atomic client"""
from enterprise_gateway.services.processproxies.k8s_client_factory import KubernetesClientFactory

KUBERNETES_CLIENT_FACTORY = KubernetesClientFactory()
kubernetes_client = KUBERNETES_CLIENT_FACTORY.get_kubernetes_client()
