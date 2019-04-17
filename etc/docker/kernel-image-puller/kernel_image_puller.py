import os
import logging
import time
import queue
import requests
from threading import Thread
from docker.client import DockerClient
from docker.errors import NotFound, APIError

gateway_host = os.getenv("KIP_GATEWAY_HOST", "http://localhost:8888")
num_pullers = int(os.getenv("KIP_NUM_PULLERS", "2"))
num_retries = int(os.getenv("KIP_NUM_RETRIES", "3"))
interval = int(os.getenv("KIP_INTERVAL", "300"))
log_level = os.getenv("KIP_LOG_LEVEL", "INFO")

POLICY_IF_NOT_PRESENT = "IfNotPresent"
POLICY_ALYWAYS = "Always"
policies = (POLICY_IF_NOT_PRESENT, POLICY_ALYWAYS)

policy = os.getenv("KIP_PULL_POLICY", POLICY_IF_NOT_PRESENT)

docker_client = DockerClient.from_env()

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s %(name)s.%(threadName)s] %(message)s')


def get_kernelspecs():
    """Fetches the set of kernelspecs from the gateway, returning a dict of configured kernel specs"""
    end_point = '{}/api/kernelspecs'.format(gateway_host)
    logger.info("Fetching kernelspecs from '{}' ...".format(end_point))
    resp = requests.get(end_point)
    if not resp.ok:
        raise requests.exceptions.HTTPError('Gateway server response: {}'.format(resp.status_code))
    return resp.json()


def fetch_image_names():
    """
    Fetches the image names by hitting the /api/kernelspecs endpoing of the Gateway.

    For process-proxy kernelspecs, the image names are contained in the config stanza - which
    resides in the process-proxy stanza located in the metadata.
    """

    kspecs = None
    try:
        kspecs_response = get_kernelspecs()
        kspecs = kspecs_response.get('kernelspecs')
    except Exception as ex:
        logger.error("Got exception attempting to retrieve kernelspecs - retrying. Exception was: {}".format(ex))
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

    # Add the image names to the name queue
    for image_name in images:
        name_queue.put_nowait(image_name)

    return True


def pull_image(image_name):
    """
    Pulls the image.  If the policy is `IfNotPresent` the set of pulled image names is
    checked and, if present, the method returns.  Otherwise, the pull attempt is made
    and the set of pulled images is updated, when successful.

    Since NotFound exceptions are tolerated, we trap for only that exception and let
    the caller handle others.
    """
    if policy == POLICY_IF_NOT_PRESENT:
        if image_name in pulled_images:
            logger.info("Image '{}' already pulled and policy is '{}'.".format(image_name, policy))
            return

    logger.debug("Pulling image '{}'...".format(image_name))
    try:
        t1 = time.time()
        docker_client.images.pull(image_name)
        t2 = time.time()
        pulled_images.add(image_name)
        logger.info("Pulled image '{}' in {:.3f} secs.".format(image_name, t2-t1))
    except NotFound:
        logger.warning("Image '{}' was not found!".format(image_name))


def puller():
    """
    Thread-based puller.  Gets image name from the queue and attempts to pull the image.
    Any issues, except for NotFound, are retried up to num_retries times.
    Once the image has been pulled, it's not found or the retries have been exceeded,
    the queue task is marked as done.
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
            except APIError as ex:
                i += 1
                if i < num_retries:
                    logger.warning("Attempt {} to pull image '{}' encountered exception - retrying.  Exception was: {}".
                                 format(i, image_name, ex))
                else:
                    logger.error("Attempt {} to pull image '{}' failed with exception: {}".
                                 format(i, image_name, ex))
        name_queue.task_done()


if __name__ == "__main__":

    logger = logging.getLogger('kernel_image_puller')
    logger.setLevel(log_level)

    # Determine pull policy.
    pulled_images = set()
    if policy not in policies:
        logger.warning("Invalid pull policy detected in KIP_PULL_POLICY: '{}'.  Using policy '{}'.".
                       format(policy, POLICY_IF_NOT_PRESENT))
        policy = POLICY_IF_NOT_PRESENT

    logger.info("Starting Kernel Image Puller with the following parameters:")
    logger.info("KIP_GATEWAY_HOST: {}".format(gateway_host))
    logger.info("KIP_INTERVAL: {} secs".format(interval))
    logger.info("KIP_NUM_PULLERS: {}".format(num_pullers))
    logger.info("KIP_NUM_RETRIES: {}".format(num_retries))
    logger.info("KIP_PULL_POLICY: {}".format(policy))
    logger.info("KIP_LOG_LEVEL: {}\n".format(log_level))

    # Create an empty queue and start the puller threads.  The number of puller threads is configurable.
    name_queue = queue.Queue()
    threads = []
    for i in range(num_pullers):
        t = Thread(target=puller, name="t{}".format(i+1))
        t.start()
        threads.append(t)

    # Fetch the image names, then wait for name queue to drain.  Once drained, or if there were issues
    # fetching the image names, wait the interval number of seconds and perform the operation again.
    while True:
        fetched = fetch_image_names()
        if fetched:
            name_queue.join()
            logger.info("Images pulled.  Sleeping {} seconds...\n".format(interval))
        else:
            logger.info("Sleeping {} seconds to fetch image names...\n".format(interval))
        time.sleep(interval)
