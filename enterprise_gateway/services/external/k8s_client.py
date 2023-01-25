"""Instantiates a static global factory and a single atomic client"""
import os
from enterprise_gateway.services.external.k8s_client_factory import KubernetesClientFactory

KUBERNETES_CLIENT_FACTORY = KubernetesClientFactory()
kubernetes_client = KUBERNETES_CLIENT_FACTORY.get_kubernetes_client()
