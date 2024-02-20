"""image name fetcher abstract class and concrete implementation"""

import abc
import importlib
import os

import requests
import yaml
from kubernetes import client, config
from kubernetes.client import ApiException


class ImageNameFetcher(metaclass=abc.ABCMeta):
    """
    abstract class to extend for fetch image names
    """

    @abc.abstractmethod
    def fetch_image_names(self) -> set[str]:
        """
        Abstract method to fetch image names.

        :return: A set of image names.
        """
        pass


class KernelSpecsFetcher(ImageNameFetcher):
    """Fetches the image names by hitting the /api/kernelspecs endpoint of the Gateway.

    For process-proxy kernelspecs, the image names are contained in the config stanza - which
    resides in the process-proxy stanza located in the metadata.
    """

    def __init__(self, logger):
        """
        KIP_AUTH_TOKEN: enterprise-gateway auth token
        KIP_GATEWAY_HOST: enterprise-gateway host
        KIP_VALIDATE_CERT: validate cert or not
        """
        self.logger = logger
        self.auth_token = os.getenv("KIP_AUTH_TOKEN", None)
        self.gateway_host = os.getenv("KIP_GATEWAY_HOST", "http://localhost:18888")
        self.validate_cert = os.getenv("KIP_VALIDATE_CERT", "False").lower() == "true"

    def get_kernel_specs(self):
        """Fetches the set of kernelspecs from the gateway, returning a dict of configured kernel specs"""
        end_point = f"{self.gateway_host}/api/kernelspecs"
        self.logger.info(f"Fetching kernelspecs from '{end_point}' ...")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            end_point += f"?token={self.auth_token}"
            headers.update({"Authorization": f"token {self.auth_token}"})
        resp = requests.get(end_point, headers=headers, verify=self.validate_cert, timeout=60)
        if not resp.ok:
            msg = f"Gateway server response: {resp.status_code}"
            raise requests.exceptions.HTTPError(msg)
        return resp.json()

    def fetch_image_names(self) -> set[str]:
        """
        fetch image names from enterprise gateway kernelspecs
        """
        k_specs = None
        try:
            k_specs_response = self.get_kernel_specs()
            k_specs = k_specs_response.get("kernelspecs")
        except Exception as ex:
            self.logger.error(
                f"Got exception attempting to retrieve kernelspecs - retrying. Exception was: {ex}"
            )

        if k_specs is None:
            return None

        # Locate the configured images within the kernel_specs and add to set for duplicate management
        images = set()
        for key in k_specs:
            metadata = k_specs.get(key).get("spec").get("metadata")
            if metadata is not None:
                config_parent = metadata.get("process_proxy")
                if config_parent is None:  # See if this is a provisioner
                    config_parent = metadata.get("kernel_provisioner")
                if config_parent is not None:
                    config = config_parent.get("config")
                    if config is not None:
                        image_name = config.get("image_name")
                        if image_name is not None:
                            images.add(image_name)
                        executor_image_name = config.get("executor_image_name")
                        if executor_image_name is not None:
                            images.add(executor_image_name)
        return images


class StaticListFetcher(ImageNameFetcher):
    """
    A class for fetching image names from a static list of images provided by an environment variable.

    Inherits from `ImageNameFetcher`, which defines a `fetch_images()` method that must be implemented.

    This class reads the `KIP_IMAGES` environment variable, which should be a comma-separated list of image names.
    It then splits the list into individual image names and returns them as a set.

    Attributes:
        logger (logging.Logger): The logger to use for logging messages.

    Methods:
        fetch_images(): Fetches image names from the `KIP_IMAGES` environment variable and returns them as a set.
    """

    def __init__(self, logger) -> None:
        """
        init method
        """
        self.logger = logger

    def fetch_image_names(self) -> set[str]:
        """
        KIP_IMAGES: comma seperated list of image names
        """
        images = os.getenv("KIP_IMAGES", "").split(",")
        return set(images)


class ConfigMapImagesFetcher(ImageNameFetcher):
    """
    A class for fetching image names from a Kubernetes ConfigMap.

    Inherits from `ImageNameFetcher`, which defines a `fetch_images()` method that must be implemented.

    This class reads the `KIP_CM_NAMESPACE`, `KIP_CM_NAME`, and `KIP_CM_KEY_NAME` environment variables to determine
    the namespace, name, and key name of the ConfigMap containing the image names. It then reads the specified
    ConfigMap and extracts the image names from the specified key, which should be a YAML list of image names.

    Attributes:
        logger (logging.Logger): The logger to use for logging messages.
        namespace (str): The namespace containing the ConfigMap.
        name (str): The name of the ConfigMap.
        key_name (str): The name of the key containing the YAML list of image names.

    Methods:
        fetch_images(): Fetches image names from the specified ConfigMap and key and returns them as a set.
    """

    def __init__(self, logger) -> None:
        """
        Initializes a new instance of the class with the specified logger and environment variables.
        KIP_CM_NAMESPACE: namespace the configmap is in
        KIP_CM_NAME: the name of the config map
        KIP_CM_KEY_NAME: the key name
        """
        self.logger = logger
        self.namespace = os.getenv("KIP_CM_NAMESPACE", "enterprise-gateway")
        self.name = os.getenv("KIP_CM_NAME", "kernel-images")
        self.key_name = os.getenv("KIP_CM_KEY_NAME", "image-names")

    def fetch_image_names(self) -> set[str]:
        """
        fetch image names by parsing the configmap
        this will load the in-cluster context, your service account of the pod should have access to get configmap
        """
        config.load_incluster_config()
        v1 = client.CoreV1Api()
        config_map = None
        try:
            config_map = v1.read_namespaced_config_map(name=self.name, namespace=self.namespace)
        except ApiException as e:
            if e.status == 404:
                self.logger.error(f"ConfigMap {self.name} not found in namespace {self.namespace}")
            else:
                # Handle other ApiException errors
                self.logger.error(f"Error retrieving ConfigMap: {e}")
        if config_map and self.key_name in config_map.data:
            images = config_map.data[self.key_name]
            image_list = []
            try:
                image_list = yaml.safe_load(images)
            except yaml.YAMLError as e:
                self.logger("Error parsing YAML:", e)
            return image_list
        return []


class CombinedImagesFetcher(ImageNameFetcher):
    """
    A class for fetching image names from multiple fetchers.
    Inherits from `ImageNameFetcher`, which defines a `fetch_images()` method that must be implemented.

    This class initializes a list of fetchers based on the `KIP_INTERNAL_FETCHERS` environment variable, which should
    be a comma-separated list of fetcher class names. It then calls the `fetch_images()` method on each fetcher and
    combines the results into a set of unique image names.

    Attributes:
        logger (logging.Logger): The logger to use for logging messages.
        fetchers (list): A list of fetchers to use for fetching image names.

    Methods:
        fetch_images(): Fetches image names from all fetchers and returns them as a set.
    """

    def __init__(self, logger):
        """
        KIP_INTERNAL_FETCHERS: fetchers used internally to get image names
        """
        self.logger = logger
        fetcher_names = os.getenv("KIP_INTERNAL_FETCHERS", "KernelSpecsFetcher").split(',')
        self.fetchers = []
        module = importlib.import_module("image_fetcher")
        args = (logger,)
        for f in fetcher_names:
            fetcher = getattr(module, f)(*args)
            self.fetchers.append(fetcher)

    def fetch_image_names(self) -> set[str]:
        """
        fetch image names from internal fetchers
        """
        images = set()
        for f in self.fetchers:
            images.update(f.fetch_image_names())
        return images
