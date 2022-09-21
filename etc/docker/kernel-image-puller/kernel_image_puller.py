import logging
import os
import queue
import time
from subprocess import CalledProcessError, run
from threading import Thread
from typing import List, Optional

import requests
from docker.client import DockerClient
from docker.errors import NotFound

# initialize root logger
logging.basicConfig(format="[%(levelname)1.1s %(asctime)s %(name)s.%(threadName)s] %(message)s")
log_level = os.getenv("KIP_LOG_LEVEL", "INFO")


class KernelImagePuller:

    POLICY_IF_NOT_PRESENT = "IfNotPresent"
    POLICY_ALWAYS = "Always"
    policies = (POLICY_IF_NOT_PRESENT, POLICY_ALWAYS)

    DOCKER_CLIENT = "docker"
    CONTAINERD_CLIENT = "containerd"
    supported_container_runtimes = (DOCKER_CLIENT, CONTAINERD_CLIENT)

    def __init__(self, kip_logger):
        self.interval = None
        self.auth_token = None
        self.gateway_host = None
        self.container_runtime = None
        self.runtime_endpoint = None
        self.default_container_registry = None
        self.log = kip_logger
        self.worker_queue = None
        self.threads = []
        self.pulled_images = set()
        self.num_pullers = None
        self.num_retries = None
        self.policy = None
        self.validate_cert = None
        self.load_static_env_values()

    def load_static_env_values(self):
        self.num_pullers = int(os.getenv("KIP_NUM_PULLERS", "2"))
        self.num_retries = int(os.getenv("KIP_NUM_RETRIES", "3"))
        self.policy = os.getenv("KIP_PULL_POLICY", KernelImagePuller.POLICY_IF_NOT_PRESENT)
        self.default_container_registry = os.getenv("KIP_DEFAULT_CONTAINER_REGISTRY", "")
        self.runtime_endpoint = os.getenv(
            "KIP_CRI_ENDPOINT", "unix:///run/containerd/containerd.sock"
        )
        self.container_runtime = self.get_container_runtime()
        self.gateway_host = os.getenv("KIP_GATEWAY_HOST", "http://localhost:18888")
        # Add authentication token support to KIP
        self.auth_token = os.getenv("KIP_AUTH_TOKEN", None)
        self.interval = int(os.getenv("KIP_INTERVAL", "300"))
        self.validate_cert = os.getenv("KIP_VALIDATE_CERT", "False").lower() == "true"

        if self.policy not in KernelImagePuller.policies:
            logger.warning(
                f"Invalid pull policy detected in KIP_PULL_POLICY: '{self.policy}'.  "
                f"Using policy '{KernelImagePuller.POLICY_IF_NOT_PRESENT}'."
            )
            self.policy = KernelImagePuller.POLICY_IF_NOT_PRESENT

        logger.info("Starting Kernel Image Puller with the following parameters:")
        logger.info(f"KIP_GATEWAY_HOST: {self.gateway_host}")
        logger.info(f"KIP_INTERVAL: {self.interval} secs")
        logger.info(f"KIP_NUM_PULLERS: {self.num_pullers}")
        logger.info(f"KIP_NUM_RETRIES: {self.num_retries}")
        logger.info(f"KIP_PULL_POLICY: {self.policy}")
        logger.info(f"KIP_LOG_LEVEL: {log_level}")
        # logger.info(f"KIP_AUTH_TOKEN: {self.auth_token}")  # Do not print
        logger.info(f"KIP_DEFAULT_CONTAINER_REGISTRY: '{self.default_container_registry}'")
        logger.info(f"KIP_CRI_ENDPOINT: {self.runtime_endpoint}")
        logger.info(f"KIP_VALIDATE_CERT: {self.validate_cert}")

        if self.is_runtime_endpoint_recognized():
            logger.info(f"Detected container runtime: {self.container_runtime}")
        else:
            logger.warning(
                f"This node's container runtime interface could not be detected from "
                f"endpoint: {self.runtime_endpoint}, proceeding with {self.container_runtime} client..."
            )

    def start(self):
        self.log.info("Starting Kernel Image Puller process.")
        self.initialize_workers()
        wait_interval = 5  # Start with 5 seconds to ensure EG service gets started...
        time.sleep(wait_interval)
        # Fetch the image names, then wait for name queue to drain.  Once drained, or if there were issues
        # fetching the image names, wait the interval number of seconds and perform the operation again.
        while True:
            fetched = self.fetch_image_names()
            if fetched:
                # Once we have fetched kernelspecs, update wait_interval
                wait_interval = self.interval
                self.worker_queue.join()
            elif not self.is_runtime_endpoint_recognized():
                # Increase the interval since we shouldn't pound the service for kernelspecs
                wait_interval = self.interval

            logger.info(f"Sleeping {wait_interval} seconds to fetch image names...\n")
            time.sleep(wait_interval)

    def initialize_workers(self):
        self.worker_queue = queue.Queue()
        for i in range(self.num_pullers):
            t = Thread(target=self.image_puller, name=f"t{(i + 1)}")
            t.start()
            self.threads.append(t)

    def get_container_runtime(self) -> Optional[str]:
        """Determine the container runtime from the KIP_CRI_ENDPOINT env."""

        if KernelImagePuller.DOCKER_CLIENT in self.runtime_endpoint:
            return KernelImagePuller.DOCKER_CLIENT

        # This will essentially be the default to use in case we don't recognized the endpoint.
        return KernelImagePuller.CONTAINERD_CLIENT

    def is_runtime_endpoint_recognized(self) -> bool:
        return (
            KernelImagePuller.DOCKER_CLIENT in self.runtime_endpoint
            or KernelImagePuller.CONTAINERD_CLIENT in self.runtime_endpoint
        )

    def get_kernel_specs(self):
        """Fetches the set of kernelspecs from the gateway, returning a dict of configured kernel specs"""
        end_point = f"{self.gateway_host}/api/kernelspecs"
        logger.info(f"Fetching kernelspecs from '{end_point}' ...")
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            end_point += f"?token={self.auth_token}"
            headers.update({"Authorization": f"token {self.auth_token}"})
        resp = requests.get(end_point, headers=headers, verify=self.validate_cert)
        if not resp.ok:
            raise requests.exceptions.HTTPError(f"Gateway server response: {resp.status_code}")
        return resp.json()

    def fetch_image_names(self):
        """Fetches the image names by hitting the /api/kernelspecs endpoint of the Gateway.

        For process-proxy kernelspecs, the image names are contained in the config stanza - which
        resides in the process-proxy stanza located in the metadata.
        """

        k_specs = None
        try:
            k_specs_response = self.get_kernel_specs()
            k_specs = k_specs_response.get("kernelspecs")
        except Exception as ex:
            logger.error(
                f"Got exception attempting to retrieve kernelspecs - retrying. Exception was: {ex}"
            )

        if k_specs is None:
            return False

        # Locate the configured images within the kernel_specs and add to set for duplicate management
        images = set()
        for key in k_specs.keys():
            metadata = k_specs.get(key).get("spec").get("metadata")
            if metadata is not None:
                process_proxy = metadata.get("process_proxy")
                if process_proxy is not None:
                    config = process_proxy.get("config")
                    if config is not None:
                        image_name = config.get("image_name")
                        if image_name is not None:
                            images.add(image_name)
                        executor_image_name = config.get("executor_image_name")
                        if executor_image_name is not None:
                            images.add(executor_image_name)

        if not images:
            return False

        # Add the image names to the name queue to be pulled
        for image_name in images:
            self.worker_queue.put_nowait(image_name)
        return True

    def image_puller(self):
        """Thread-based puller.

        Gets image name from the queue and attempts to pull the image. Any issues, except
        for NotFound, are retried up to num_retries times. Once the image has been pulled, it's not found or the
        retries have been exceeded, the queue task is marked as done.
        """
        while True:
            logger.debug("Waiting for new image to pull")
            image_name = self.worker_queue.get()
            self.log.info(f"Task received to pull image: {image_name}")
            if image_name is None:
                break
            i = 0
            while i < self.num_retries:
                try:
                    self.pull_image(image_name)
                    break
                except Exception as ex:
                    i += 1
                    if i < self.num_retries:
                        logger.warning(
                            f"Attempt {i} to pull image '{image_name}' encountered exception - retrying.  "
                            f"Exception was: {ex}."
                        )
                    else:
                        logger.error(
                            f"Attempt {i} to pull image '{image_name}' failed with exception: {ex}"
                        )
            self.worker_queue.task_done()

    def pull_image(self, image_name):
        """Pulls the image.

        If the policy is `IfNotPresent` the set of pulled image names is
        checked and, if present, the method returns.  Otherwise, the pull attempt is made
        and the set of pulled images is updated, when successful.
        """
        if self.policy == KernelImagePuller.POLICY_IF_NOT_PRESENT:
            if image_name in self.pulled_images:
                # Image has been pulled, but make sure it still exists.  If it doesn't exist
                # let this drop through to actual pull
                logger.info(
                    f"Image '{image_name}' already pulled and policy is '{self.policy}'.  Checking existence."
                )
                if self.image_exists(image_name):
                    return
                self.pulled_images.remove(image_name)
                logger.warning(
                    f"Previously pulled image '{image_name}' was not found - attempting pull..."
                )
            elif self.image_exists(image_name):  # Yet to be pulled, consider pulled if exists
                logger.info(
                    f"Image '{image_name}' has not been pulled but exists, and policy is '{self.policy}'. Skipping pull."
                )
                self.pulled_images.add(image_name)
                return

        logger.info(f"Pulling image '{image_name}'...")
        if self.download_image(image_name):
            self.pulled_images.add(image_name)
        else:
            logger.warning(f"Image '{image_name}' was not downloaded!")

    def get_absolute_image_name(self, image_name: str) -> str:
        """Ensures the image name is prefixed with a "registry"."""
        # We will check for the form 'registry/repo/image:tag' if the 'registry/' prefix
        # is missing (based on the absence of two slashes), then we'll prefix the image
        # name with the KIP_DEFAULT_CONTAINER_REGISTRY env value.
        image_pieces = image_name.split("/")
        if len(image_pieces) < 3:  # we're missing a registry specifier, use default if present
            if self.default_container_registry:
                return f"{self.default_container_registry}/{image_name}"
        return image_name  # take our chances

    def image_exists(self, image_name: str) -> bool:
        """Checks for the existence of the named image using the configured container runtime."""
        result = True
        absolute_image_name = self.get_absolute_image_name(image_name)
        t0 = time.time()
        if self.container_runtime == KernelImagePuller.DOCKER_CLIENT:
            try:
                DockerClient.from_env().images.get(absolute_image_name)
            except NotFound:
                result = False
        elif self.container_runtime == KernelImagePuller.CONTAINERD_CLIENT:
            argv = ["crictl", "-r", self.runtime_endpoint, "inspecti", "-q", absolute_image_name]
            result = self.execute_cmd(argv)
        else:  # invalid container runtime
            logger.error(f"Invalid container runtime detected: '{self.container_runtime}'!")
            result = False
        t1 = time.time()
        logger.debug(
            f"Checked existence of image '{image_name}' in {(t1 - t0):.3f} secs.  exists = {result}"
        )
        return result

    def download_image(self, image_name: str) -> bool:
        """Downloads (pulls) the named image using the configured container runtime."""
        result = True
        absolute_image_name = self.get_absolute_image_name(image_name)
        t0 = time.time()
        if self.container_runtime == KernelImagePuller.DOCKER_CLIENT:
            try:
                DockerClient.from_env().images.pull(absolute_image_name)
            except NotFound:
                result = False
        elif self.container_runtime == KernelImagePuller.CONTAINERD_CLIENT:
            argv = ["crictl", "-r", self.runtime_endpoint, "pull", absolute_image_name]
            result = self.execute_cmd(argv)
        else:  # invalid container runtime
            logger.error(f"Invalid container runtime detected: '{self.container_runtime}'!")
            result = False
        t1 = time.time()
        if result is True:
            logger.info(f"Pulled image '{image_name}' in {(t1 - t0):.3f} secs.")
        return result

    def execute_cmd(self, argv: List[str]) -> bool:
        """Execute the given command expressed in 'argv'. If expected_output is provided it

        will be checked against the command's stdout after stripping off the '\n' character.
        """
        result = True
        try:
            run(argv, capture_output=True, text=True, check=True)
        except CalledProcessError as cpe:
            error_msg = cpe.stderr[:-1]  # strip off trailing newline
            logger.error(f"Error executing {' '.join(argv)}: {error_msg}")
            result = False
        except Exception as ex:
            logger.error(f"Error executing {' '.join(argv)}: {ex}")
            result = False
        return result


if __name__ == "__main__":
    logger = logging.getLogger("kernel_image_puller")
    logger.setLevel(log_level)
    logger.info("Loading KernelImagePuller...")
    kip = KernelImagePuller(logger)
    kip.start()
