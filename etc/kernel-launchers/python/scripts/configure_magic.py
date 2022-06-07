import base64
import json
import logging
import os
import sys
import time

import requests
from IPython.core.magic import Magics, magics_class, cell_magic
from json import JSONDecodeError
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.name = "configure_magic"
logger.setLevel(logging.DEBUG)
logger.propagate = True

RESERVED_SPARK_CONFIGS = [
    "spark.kubernetes.container.image",
    "spark.kubernetes.driver.container.image",
    "spark.kubernetes.executor.container.image",
    "spark.kubernetes.namespace",
    "spark.kubernetes.driver.label.component",
    "spark.kubernetes.executor.label.component"
    "spark.kubernetes.driver.label.kernel_id",
    "spark.kubernetes.executor.label.kernel_id",
    "spark.kubernetes.driver.label.app",
    "spark.kubernetes.executor.label.app",
]


class InvalidPayloadException(Exception):
    pass


@magics_class
class ConfigureMagic(Magics):
    SUPPORTED_MAGIC_FIELDS = {
        "driverMemory": " --conf spark.driver.memory={} ",
        "driverCores": " --conf spark.driver.cores={} ",
        "executorMemory": " --conf spark.executor.memory={} ",
        "executorCores": " --conf spark.executor.cores={} ",
        "numExecutors": " --conf spark.executor.instances={} ",
        "conf": "--conf {}={} ",
        "launchTimeout": "{}"
    }
    MAX_LAUNCH_TIMEOUT = 500

    KERNEL_ID_NOT_FOUND = "We could not find any associated Kernel to apply the magic. Please restart Kernel."
    EMPTY_INVALID_MAGIC_PAYLOAD = "The magic payload is either empty or not in the correct format." \
                                  " Please recheck and execute."
    INVALID_JSON_PAYLOAD = "The magic payload could not be parsed into a valid JSON object. Please recheck and execute."
    SERVER_ERROR = "An error occurred while updating the kernel configuration: {}."
    UNKNOWN_ERROR = "An error occurred while processing payload."
    RESERVED_SPARK_CONFIGS_ERROR = "You are not allowed to override {} spark config as its reserved."
    MAX_LAUNCH_TIMEOUT_ERROR = "The allowed range for Kernel launchTimeout is (0, {}).".format(MAX_LAUNCH_TIMEOUT)
    INVALID_PAYLOAD_ERROR = "{} with error: {}"

    def __init__(self, shell=None, **kwargs):
        logger.info("New Initializing ConfigureMagic...")
        super().__init__(shell=None, **kwargs)
        self.shell = shell
        self.kernel_id = os.environ.get("KERNEL_ID", None)
        self.endpoint_ip = os.environ.get("ENDPOINT_IP", "").split(":")[0]
        self.endpoint_port = 9547
        self.protocol = "https"
        if self.endpoint_ip == "" or self.endpoint_ip is None:
            logger.info("Environment var: ENDPOINT_IP not set. Falling back to using localhost.")
            self.endpoint_ip = "localhost"
            self.endpoint_port = 18888
            self.protocol = "http"
        self.update_kernel_url = "{}://{}:{}/api/configure/{}".format(self.protocol, self.endpoint_ip, self.endpoint_port,
                                                                    self.kernel_id)
        logger.debug(f"Kernel Update URL set to: {self.update_kernel_url}")
        self.headers = {
            "Content-Type": "application/json",
        }
        logger.info("successfully loaded configure magic.")

    @cell_magic
    def configure(self, line, cell=""):
        if self.kernel_id is None:
            logger.error(ConfigureMagic.KERNEL_ID_NOT_FOUND)
            return ConfigureMagic.KERNEL_ID_NOT_FOUND
        logger.info(f"Magic cell payload received: {cell}")
        magic_payload = None
        try:
            cell_payload = json.loads(cell)
            magic_payload = self.convert_to_kernel_update_payload(cell_payload)
            if not magic_payload:
                logger.error(f"The payload is either empty or invalid. {magic_payload}")
                return ConfigureMagic.EMPTY_INVALID_MAGIC_PAYLOAD
        except ValueError as ve:
            logger.exception("Could not parse JSON object from input {}: error: {}.".format(cell, ve))
            return ConfigureMagic.INVALID_JSON_PAYLOAD
        except JSONDecodeError as jde:
            logger.exception("Could not parse JSON object from input: {}: error: {}.".format(cell, jde))
            return ConfigureMagic.INVALID_JSON_PAYLOAD
        except InvalidPayloadException as ipe:
            logger.exception(
                "InvalidPayloadException occurred while processing magic payload: {}: error: {}".format(cell, ipe))
            return ConfigureMagic.INVALID_PAYLOAD_ERROR.format(InvalidPayloadException.__name__, ipe)
        except Exception as ex:
            logger.exception("Exception occurred while processing magic payload: {}: error: {}".format(cell, ex))
            return ConfigureMagic.UNKNOWN_ERROR
        else:
            magic_payload["zmq_messages"] = self.prepare_zmq_messages()
            logger.debug(f"Payload to refresh: {magic_payload}")
            result = self.update_kernel(magic_payload)
            return result
        return "Done"

    def prepare_zmq_messages(self):
        messages = {}
        messages["idle_reply"] = self.prepare_iopub_idle_reply_payload()
        messages["exec_reply"] = self.prepare_shell_reply_payload()
        messages["stream_reply"] = self.prepare_iopub_stream_reply_payload()
        messages["error_reply"] = self.prepare_iopub_error_reply_payload()
        return messages

    def prepare_iopub_error_reply_payload(self):
        ipykernel = self.shell.kernel
        reply_content = {
            'ename': 'MagicExecutionError',
            'evalue': 'UnknownError',
            'traceback': []
        }
        parent_headers = self.shell.parent_header["header"].copy()
        metadata = {}  # ipykernel.init_metadata(parent_headers)
        error_payload = ipykernel.session.msg(msg_type="error", content=reply_content, parent=parent_headers,
                                             metadata=metadata)
        error_payload["channel"] = "iopub"
        error_payload["buffers"] = []
        return error_payload

    def prepare_iopub_idle_reply_payload(self):
        ipykernel = self.shell.kernel
        reply_content = {
            'execution_state': 'idle'
        }
        parent_headers = self.shell.parent_header["header"].copy()
        metadata = {}  # ipykernel.init_metadata(parent_headers)
        idle_payload = ipykernel.session.msg(msg_type="status", content=reply_content, parent=parent_headers,
                                             metadata=metadata)
        idle_payload["channel"] = "iopub"
        idle_payload["buffers"] = []
        return idle_payload

    def prepare_iopub_stream_reply_payload(self):
        ipykernel = self.shell.kernel
        reply_content = {
            'name': 'stdout',
            'text': ' '
        }
        parent_headers = self.shell.parent_header["header"].copy()
        metadata = ipykernel.init_metadata(parent_headers)
        idle_payload = ipykernel.session.msg(msg_type="stream", content=reply_content, parent=parent_headers,
                                             metadata=metadata)
        idle_payload["channel"] = "iopub"
        idle_payload["buffers"] = []
        return idle_payload

    def prepare_shell_reply_payload(self):
        ipykernel = self.shell.kernel
        reply_content = {
            'status': 'ok',
            'execution_count': ipykernel.execution_count,
            'user_expressions': {},
            'payload': []
        }
        parent_headers = self.shell.parent_header["header"].copy()
        metadata = ipykernel.init_metadata(parent_headers)
        metadata = ipykernel.finish_metadata(parent_headers, metadata, reply_content)
        shell_payload = ipykernel.session.msg(msg_type="execute_reply", content=reply_content, parent=parent_headers,
                                              metadata=metadata)
        shell_payload["channel"] = "shell"
        shell_payload["buffers"] = []
        return shell_payload

    def convert_to_kernel_update_payload(self, cell_payload={}):
        if not cell_payload or type(cell_payload) != dict:
            return None
        magic_payload = {}
        spark_overrides = ""
        for magic_key, spark_conf in ConfigureMagic.SUPPORTED_MAGIC_FIELDS.items():
            magic_prop = cell_payload.get(magic_key, None)
            if magic_prop is not None:
                if magic_key == "conf" and type(magic_prop) == dict:
                    conf_dict = magic_prop
                    conf = " "
                    for k, v in conf_dict.items():
                        if k in RESERVED_SPARK_CONFIGS:
                            raise InvalidPayloadException(ConfigureMagic.RESERVED_SPARK_CONFIGS_ERROR.format(k))
                        conf += spark_conf.format(k, v)
                    spark_overrides += conf
                elif magic_key == "launchTimeout":
                    if int(magic_prop) <= 0 or int(magic_prop) > ConfigureMagic.MAX_LAUNCH_TIMEOUT:
                        raise InvalidPayloadException(ConfigureMagic.MAX_LAUNCH_TIMEOUT_ERROR)
                    self.populate_env_in_payload(magic_payload, "KERNEL_LAUNCH_TIMEOUT", str(magic_prop))
                else:
                    spark_overrides += spark_conf.format(magic_prop)
        logger.debug(f"KERNEL_EXTRA_SPARK_OPTS: {spark_overrides}")
        if len(spark_overrides.strip()) != 0:
            # Do not strip spark_overrides while populating
            self.populate_env_in_payload(magic_payload, "KERNEL_EXTRA_SPARK_OPTS", spark_overrides)
        return magic_payload

    def populate_env_in_payload(self, payload, env_key, env_value):
        if not payload.get('env', None):
            payload['env'] = {}
        if env_key and env_value:
            payload['env'][env_key] = env_value
        else:
            logger.error(f"Either key or value is not defined. {env_key}, {env_value}")

    def update_kernel(self, payload_dict):
        try:
            logger.info(f"Sending request to update kernel. Please wait while the kernel will be refreshed.")
            # Flush output before sending the request.
            sys.stdout.flush()
            sys.stderr.flush()
            time.sleep(0.005)  # small delay
            response = requests.post(self.update_kernel_url, data=json.dumps(payload_dict, default=str),
                                     headers=self.headers,
                                     verify=False)
            response_body = response.json() if response is not None else {}
            # the below lines are executed only if the request was not successful or runaway kernel case.
            logger.debug(f"Response received for kernel update: {response.status_code}: body: {response_body}")
            if response.status_code != 200:
                error_message = response_body["message"] if response_body.get("message", None) else "Internal Error."
                logger.error("An error occurred while updating kernel: {}: {}".format(response.status_code,
                                                                                      error_message))
                return ConfigureMagic.SERVER_ERROR.format(error_message)
            else:
                # if we have hit this, we have a runaway kernel as this pod should have gone down.
                logger.error("Successfully updated kernel but with possible duplicate / runaway kernel scenario.")
                return "Status: {}. Possible kernel leak.".format(response)
        except Exception as ex:
            logger.exception("Runtime exception occurred: {}", ex)
            return ConfigureMagic.SERVER_ERROR.format(ex)
        except KeyboardInterrupt:
            logger.info("Received Interrupt to shutdown kernel. Please wait while the kernel will be refreshed.")


def load_ipython_extension(ipython):
    # The `ipython` argument is the currently active `InteractiveShell`
    # instance, which can be used in any way. This allows you to register
    # new magics or aliases, for example.
    logger.info("Loading ConfigureMagic ...")
    ipython.register_magics(ConfigureMagic)


def unload_ipython_extension(ipython):
    logger.info("Unloading ConfigureMagic is a NO-OP. You will need to restart kernel now.")
    return "NO-OP"
