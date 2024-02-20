"""A kernel image puller."""

import importlib
import logging
import os
import queue
import time
from subprocess import CalledProcessError, run
from threading import Thread
from typing import List, Optional

from docker.client import DockerClient
from docker.errors import NotFound

# initialize root logger
logging.basicConfig(format="[%(levelname)1.1s %(asctime)s %(name)s.%(threadName)s] %(message)s")
log_level = os.getenv("KIP_LOG_LEVEL", "INFO")


class KernelImagePuller:
    """A kernel image puller."""

    POLICY_IF_NOT_PRESENT = "IfNotPresent"
    POLICY_ALWAYS = "Always"
    policies = (POLICY_IF_NOT_PRESENT, POLICY_ALWAYS)

    DOCKER_CLIENT = "docker"
    CONTAINERD_CLIENT = "containerd"
    supported_container_runtimes = (DOCKER_CLIENT, CONTAINERD_CLIENT)

    def __init__(self, kip_logger, image_fetcher):
        """Initialize the puller."""
        self.interval = None
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
        self.image_fetcher = image_fetcher
        self.load_static_env_values()

    def load_static_env_values(self):
        """Load the static environment values."""
        self.num_pullers = int(os.getenv("KIP_NUM_PULLERS", "2"))
        self.num_retries = int(os.getenv("KIP_NUM_RETRIES", "3"))
        self.policy = os.getenv("KIP_PULL_POLICY", KernelImagePuller.POLICY_IF_NOT_PRESENT)
        self.default_container_registry = os.getenv("KIP_DEFAULT_CONTAINER_REGISTRY", "")
        self.runtime_endpoint = os.getenv(
            "KIP_CRI_ENDPOINT", "unix:///run/containerd/containerd.sock"
        )
        self.container_runtime = self.get_container_runtime()
        # Add authentication token support to KIP
        self.interval = int(os.getenv("KIP_INTERVAL", "300"))

        if self.policy not in KernelImagePuller.policies:
            logger.warning(
                f"Invalid pull policy detected in KIP_PULL_POLICY: '{self.policy}'.  "
                f"Using policy '{KernelImagePuller.POLICY_IF_NOT_PRESENT}'."
            )
            self.policy = KernelImagePuller.POLICY_IF_NOT_PRESENT

        logger.info("Starting Kernel Image Puller with the following parameters:")
        logger.info(f"KIP_INTERVAL: {self.interval} secs")
        logger.info(f"KIP_NUM_PULLERS: {self.num_pullers}")
        logger.info(f"KIP_NUM_RETRIES: {self.num_retries}")
        logger.info(f"KIP_PULL_POLICY: {self.policy}")
        logger.info(f"KIP_LOG_LEVEL: {log_level}")
        # logger.info(f"KIP_AUTH_TOKEN: {self.auth_token}")  # Do not print
        logger.info(f"KIP_DEFAULT_CONTAINER_REGISTRY: '{self.default_container_registry}'")
        logger.info(f"KIP_CRI_ENDPOINT: {self.runtime_endpoint}")

        if self.is_runtime_endpoint_recognized():
            logger.info(f"Detected container runtime: {self.container_runtime}")
        else:
            logger.warning(
                f"This node's container runtime interface could not be detected from "
                f"endpoint: {self.runtime_endpoint}, proceeding with {self.container_runtime} client..."
            )

    def start(self):
        """Start the puller."""
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
        """Initialize the workers."""
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
        """Check if the runtime endpoint is recognized."""
        return (
            KernelImagePuller.DOCKER_CLIENT in self.runtime_endpoint
            or KernelImagePuller.CONTAINERD_CLIENT in self.runtime_endpoint
        )

    def fetch_image_names(self):
        """
        Fetches image names and adds them to a worker queue for processing.
        Returns:
            bool: True if at least one image name was found and added to the worker queue, False otherwise.
        """
        # Locate the configured image_names within the kernel_specs and add to set for duplicate management
        image_names = self.image_fetcher.fetch_image_names()

        if not image_names:
            return False

        # Add the image names to the name queue to be pulled
        for image_name in image_names:
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
                policy = self.policy
                logger.info(
                    f"Image '{image_name}' has not been pulled but exists, and policy is '{policy}'. Skipping pull."
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
        # we're missing a registry specifier, use default if present
        if len(image_pieces) < 3 and self.default_container_registry:
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
    fetcher_class_name = os.getenv('KIP_IMAGE_FETCHER', 'KernelSpecsFetcher')
    args = (logger,)
    module = importlib.import_module("image_fetcher")
    fetcher = getattr(module, fetcher_class_name)(*args)
    kip = KernelImagePuller(logger, fetcher)
    kip.start()
