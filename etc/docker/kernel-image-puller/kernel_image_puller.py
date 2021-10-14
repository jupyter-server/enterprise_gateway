import logging
import os
import queue
import requests
import time

from docker.client import DockerClient
from docker.errors import NotFound
from subprocess import run
from subprocess import CalledProcessError
from threading import Thread
from typing import List
from typing import Optional

gateway_host = os.getenv("KIP_GATEWAY_HOST", "http://localhost:8888")
num_pullers = int(os.getenv("KIP_NUM_PULLERS", "2"))
num_retries = int(os.getenv("KIP_NUM_RETRIES", "3"))
interval = int(os.getenv("KIP_INTERVAL", "300"))
log_level = os.getenv("KIP_LOG_LEVEL", "INFO")

# Add authentication token support to KIP
auth_token = os.getenv("KIP_AUTH_TOKEN", None)

POLICY_IF_NOT_PRESENT = "IfNotPresent"
POLICY_ALYWAYS = "Always"
policies = (POLICY_IF_NOT_PRESENT, POLICY_ALYWAYS)

policy = os.getenv("KIP_PULL_POLICY", POLICY_IF_NOT_PRESENT)

runtime_endpoint = os.getenv("KIP_CRI_ENDPOINT", "unix:///run/containerd/containerd.sock")
default_container_registry = os.getenv("KIP_DEFAULT_CONTAINER_REGISTRY", "docker.io")
DOCKER_CLIENT = "docker"
CONTAINERD_CLIENT = "containerd"
supported_container_runtimes = (DOCKER_CLIENT, CONTAINERD_CLIENT)

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s %(name)s.%(threadName)s] %(message)s')


def get_kernelspecs():
    """Fetches the set of kernelspecs from the gateway, returning a dict of configured kernel specs"""
    end_point = f"{gateway_host}/api/kernelspecs"
    logger.info(f"Fetching kernelspecs from '{end_point}' ...")
    if auth_token:
        end_point += f"?token={auth_token}"
    resp = requests.get(end_point)
    if not resp.ok:
        raise requests.exceptions.HTTPError(f"Gateway server response: {resp.status_code}")
    return resp.json()


def fetch_image_names():
    """Fetches the image names by hitting the /api/kernelspecs endpoint of the Gateway.

    For process-proxy kernelspecs, the image names are contained in the config stanza - which
    resides in the process-proxy stanza located in the metadata.
    """

    kspecs = None
    try:
        kspecs_response = get_kernelspecs()
        kspecs = kspecs_response.get('kernelspecs')
    except Exception as ex:
        logger.error(f"Got exception attempting to retrieve kernelspecs - retrying. Exception was: {ex}")
    finally:
        if kspecs is None:
            return False

    # Locate the configured images within the kernelspecs and add to set for duplicate management
    images = set()
    for key in kspecs.keys():
        metadata = kspecs.get(key).get('spec').get('metadata')
        if metadata is not None:
            process_proxy = metadata.get('process_proxy')
            if process_proxy is not None:
                config = process_proxy.get('config')
                if config is not None:
                    image_name = config.get('image_name')
                    if image_name is not None:
                        images.add(image_name)
                    executor_image_name = config.get('executor_image_name')
                    if executor_image_name is not None:
                        images.add(executor_image_name)

    if not images:
        return False

    # Add the image names to the name queue to be pulled
    for image_name in images:
        name_queue.put_nowait(image_name)
    return True


def pull_image(image_name):
    """Pulls the image.

    If the policy is `IfNotPresent` the set of pulled image names is
    checked and, if present, the method returns.  Otherwise, the pull attempt is made
    and the set of pulled images is updated, when successful.
    """
    if policy == POLICY_IF_NOT_PRESENT:
        if image_name in pulled_images:
            # Image has been pulled, but make sure it still exists.  If it doesn't exist
            # let this drop through to actual pull
            logger.info(f"Image '{image_name}' already pulled and policy is '{policy}'.  Checking existence.")
            if image_exists(image_name):
                return
            pulled_images.remove(image_name)
            logger.warning(f"Previously pulled image '{image_name}' was not found - attempting pull...")

    logger.info(f"Pulling image '{image_name}'...")
    if download_image(image_name):
        pulled_images.add(image_name)
    else:
        logger.warning(f"Image '{image_name}' was not downloaded!")


def get_absolute_image_name(image_name: str) -> str:
    """Ensures the image name is prefixed with a "registry". """
    # We will check for the form 'registry/repo/image:tag' if the 'registry/' prefix
    # is missing (based on the absence of two slashes), then we'll prefix the image
    # name with the KIP_DEFAULT_CONTAINER_REGISTRY env value.
    image_pieces = image_name.split('/')
    if len(image_pieces) < 3:  # we're missing a registry specifier, use env
        return f"{default_container_registry}/{image_name}"
    return image_name  # take our chances


def image_exists(image_name: str) -> bool:
    """Checks for the existence of the named image using the configured container runtime."""
    result = True
    absolute_image_name = get_absolute_image_name(image_name)
    t0 = time.time()
    if container_runtime == DOCKER_CLIENT:
        try:
            DockerClient.from_env().images.get(absolute_image_name)
        except NotFound:
            result = False
    elif container_runtime == CONTAINERD_CLIENT:
        argv = ['crictl', '-r', runtime_endpoint, 'inspecti', '-q', absolute_image_name]
        result = execute_cmd(argv)
    else:  # invalid container runtime
        logger.error(f"Invalid container runtime detected: '{container_runtime}'!")
        result = False
    t1 = time.time()
    logger.debug(f"Checked existence of image '{image_name}' in {(t1 - t0):.3f} secs.  exists = {result}")
    return result


def download_image(image_name: str) -> bool:
    """Downloads (pulls) the named image using the configured container runtime."""
    result = True
    absolute_image_name = get_absolute_image_name(image_name)
    t0 = time.time()
    if container_runtime == DOCKER_CLIENT:
        try:
            DockerClient.from_env().images.pull(absolute_image_name)
        except NotFound:
            result = False
    elif container_runtime == CONTAINERD_CLIENT:
        argv = ['crictl', '-r', runtime_endpoint, 'pull', absolute_image_name]
        result = execute_cmd(argv)
    else:  # invalid container runtime
        logger.error(f"Invalid container runtime detected: '{container_runtime}'!")
        result = False
    t1 = time.time()
    if result is True:
        logger.info(f"Pulled image '{image_name}' in {(t1 - t0):.3f} secs.")
    return result


def execute_cmd(argv: List[str]) -> bool:
    """Execute the given command expressed in 'argv'.  If expected_output is provided it

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


def puller():
    """Thread-based puller.

    Gets image name from the queue and attempts to pull the image. Any issues, except
    for NotFound, are retried up to num_retries times. Once the image has been pulled, it's not found or the
    retries have been exceeded, the queue task is marked as done.
    """
    while True:
        image_name = name_queue.get()
        if image_name is None:
            break

        i = 0
        while i < num_retries:
            try:
                pull_image(image_name)
                break
            except Exception as ex:
                i += 1
                if i < num_retries:
                    logger.warning(f"Attempt {i} to pull image '{image_name}' encountered exception - retrying.  "
                                   f"Exception was: {ex}.")
                else:
                    logger.error(f"Attempt {i} to pull image '{image_name}' failed with exception: {ex}")
        name_queue.task_done()


def is_runtime_endpoint_recognized() -> bool:
    return DOCKER_CLIENT in runtime_endpoint or CONTAINERD_CLIENT in runtime_endpoint


def get_container_runtime() -> Optional[str]:
    """Determine the container runtime from the KIP_CRI_ENDPOINT env."""

    if DOCKER_CLIENT in runtime_endpoint:
        return DOCKER_CLIENT

    # This will essentially be the default to use in case we don't recognized the endpoint.
    return CONTAINERD_CLIENT


if __name__ == "__main__":
    logger = logging.getLogger('kernel_image_puller')
    logger.setLevel(log_level)

    container_runtime = get_container_runtime()

    # Determine pull policy.
    pulled_images = set()
    if policy not in policies:
        logger.warning(f"Invalid pull policy detected in KIP_PULL_POLICY: '{policy}'.  "
                       f"Using policy '{POLICY_IF_NOT_PRESENT}'.")
        policy = POLICY_IF_NOT_PRESENT

    logger.info("Starting Kernel Image Puller with the following parameters:")
    logger.info(f"KIP_GATEWAY_HOST: {gateway_host}")
    logger.info(f"KIP_INTERVAL: {interval} secs")
    logger.info(f"KIP_NUM_PULLERS: {num_pullers}")
    logger.info(f"KIP_NUM_RETRIES: {num_retries}")
    logger.info(f"KIP_PULL_POLICY: {policy}")
    logger.info(f"KIP_LOG_LEVEL: {log_level}")
    logger.info(f"KIP_AUTH_TOKEN: {auth_token}")
    logger.info(f"KIP_DEFAULT_CONTAINER_REGISTRY: {default_container_registry}")
    logger.info(f"KIP_CRI_ENDPOINT: {runtime_endpoint}")
    if is_runtime_endpoint_recognized():
        logger.info(f"Detected container runtime: {container_runtime}")
    else:
        logger.warning(f"This node's container runtime interface could not be detected from "
                       f"endpoint: {runtime_endpoint}, proceeding with {container_runtime} client...")

    # Create an empty queue and start the puller threads.  The number of puller threads is configurable.
    name_queue = queue.Queue()
    threads = []
    for i in range(num_pullers):
        t = Thread(target=puller, name=f"t{(i + 1)}")
        t.start()
        threads.append(t)

    # Fetch the image names, then wait for name queue to drain.  Once drained, or if there were issues
    # fetching the image names, wait the interval number of seconds and perform the operation again.

    wait_interval = 5  # Start with 5 seconds to ensure EG service gets started...
    time.sleep(wait_interval)
    while True:
        fetched = fetch_image_names()
        if fetched:
            wait_interval = interval  # Once we have fetched kernelspecs, update wait_interval
            name_queue.join()
        elif not is_runtime_endpoint_recognized():
            wait_interval = interval  # Increase the interval since we shouldn't pound the service for kernelspecs

        logger.info(f"Sleeping {wait_interval} seconds to fetch image names...\n")
        time.sleep(wait_interval)
