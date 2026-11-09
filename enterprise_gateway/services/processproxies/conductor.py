"""Code related to managing kernels running in Conductor clusters."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import signal
import socket
import subprocess
import time
from collections.abc import Iterable
from random import randint
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit, urlunsplit

from jupyter_client import localinterfaces
from jupyter_server.utils import url_unescape
from tornado.web import HTTPError

from ..kernels.remotemanager import RemoteKernelManager
from .processproxy import RemoteProcessProxy, redaction_mask

pjoin = os.path.join
local_ip = localinterfaces.public_ips()[0]
poll_interval = float(os.getenv("EG_POLL_INTERVAL", "0.5"))
max_poll_attempts = int(os.getenv("EG_MAX_POLL_ATTEMPTS", "10"))

# Bound each curl invocation's TCP connect phase so a slow/blackholed failover host cannot
# stall a kernel launch (the HA list is tried host-by-host, four times over).
_CURL_CONNECT_TIMEOUT_SECONDS = int(os.getenv("EG_CONDUCTOR_CONNECT_TIMEOUT", "10"))

# curl SSL/TLS options permitted in KERNEL_CURL_SECURITY_OPT.  The value of this
# client-supplied variable is split into individual curl arguments and spliced
# into the curl command line (see the REST helpers below), so an unvalidated
# value permits curl *argument* injection even though no shell is involved:
# e.g. `-o`/`--output` to overwrite files, `-T`/`--upload-file` or `--data @file`
# to exfiltrate local files, `-K`/`--config` to load an attacker-controlled
# config, or a bare token that curl interprets as an extra URL.  We fail closed
# with an allowlist of security-only options; operators needing an option not
# listed here must add it explicitly.
_CURL_SSL_BOOLEAN_OPTS = frozenset(
    {
        "-k",
        "--insecure",
        "--cert-status",
        "--ssl",
        "--ssl-reqd",
        "--ssl-no-revoke",
        "--ssl-revoke-best-effort",
        "--ssl-allow-beast",
        "--tlsv1",
        "--tlsv1.0",
        "--tlsv1.1",
        "--tlsv1.2",
        "--tlsv1.3",
        "--sslv2",
        "--sslv3",
        "--proxy-insecure",
    }
)
_CURL_SSL_VALUE_OPTS = frozenset(
    {
        "--cacert",
        "--capath",
        "--cert",
        "-E",
        "--cert-type",
        "--ciphers",
        "--tls13-ciphers",
        "--crlfile",
        "--key",
        "--key-type",
        "--pass",
        "--pinnedpubkey",
        "--tls-max",
        "--curves",
        "--proxy-cacert",
        "--proxy-capath",
        "--proxy-cert",
        "--proxy-cert-type",
        "--proxy-key",
        "--proxy-key-type",
        "--proxy-pass",
        "--proxy-ciphers",
    }
)


def validate_curl_security_opt(value: str) -> list[str]:
    """Validate ``KERNEL_CURL_SECURITY_OPT`` and return it as a list of curl args.

    The value is a space-separated list of curl SSL/TLS options.  Because the
    tokens are spliced directly into a curl command line, only an allowlist of
    security-related options (and their arguments) is permitted; anything else
    is rejected to prevent curl argument injection.

    Parameters
    ----------
    value:
        Raw ``KERNEL_CURL_SECURITY_OPT`` value.

    Returns
    -------
    list[str]
        The validated, tokenized curl arguments (may be empty).

    Raises
    ------
    tornado.web.HTTPError
        400 if a token is a non-allowlisted option or a stray (URL-like) token,
        or if the value ends with a value-option that is missing its argument.
    """
    tokens = value.split()
    expect_arg = False
    for token in tokens:
        if expect_arg:
            # Consume this token as the argument to the preceding value-option.
            expect_arg = False
            continue
        if not token.startswith("-"):
            # curl would treat a bare token as an additional URL to fetch.
            raise HTTPError(400, "KERNEL_CURL_SECURITY_OPT contains an unexpected token")
        opt = token.split("=", 1)[0]
        if "=" in token:
            if opt not in _CURL_SSL_VALUE_OPTS:
                raise HTTPError(
                    400, f"KERNEL_CURL_SECURITY_OPT contains a disallowed curl option: {opt}"
                )
        elif opt in _CURL_SSL_VALUE_OPTS:
            expect_arg = True
        elif opt not in _CURL_SSL_BOOLEAN_OPTS:
            raise HTTPError(
                400, f"KERNEL_CURL_SECURITY_OPT contains a disallowed curl option: {opt}"
            )
    if expect_arg:
        # A trailing value-option would make curl consume the next fixed argument
        # (e.g. "-b") as its value, turning the following token into an extra URL.
        raise HTTPError(400, "KERNEL_CURL_SECURITY_OPT ends with an option missing its value")
    return tokens


class ConductorClusterProcessProxy(RemoteProcessProxy):
    """
    Kernel lifecycle management for Conductor clusters.
    """

    initial_states: ClassVar = {"SUBMITTED", "WAITING", "RUNNING"}
    final_states: ClassVar = {"FINISHED", "KILLED", "RECLAIMED"}  # Don't include FAILED state

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.application_id = None
        self.driver_id = None
        self.env = None
        self.rest_credential = None
        self.jwt_token = None
        self.conductor_endpoint = proxy_config.get(
            "conductor_endpoint", kernel_manager.conductor_endpoint
        )
        self.ascd_endpoint = self.conductor_endpoint
        self.conductor_ha_allowed_hosts = proxy_config.get(
            "conductor_ha_allowed_hosts", kernel_manager.conductor_ha_allowed_hosts
        )

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> ConductorClusterProcessProxy:
        """
        Launches the specified process within a Conductor cluster environment.
        """
        await super().launch_process(kernel_cmd, **kwargs)

        self.env = kwargs.get("env")
        self.kernel_headers = kwargs.get("kernel_headers")

        # Get Conductor cred from process env
        env_dict = dict(os.environ.copy())
        if env_dict and "EGO_SERVICE_CREDENTIAL" in env_dict:
            self.rest_credential = env_dict["EGO_SERVICE_CREDENTIAL"]
        elif self.kernel_headers and "Jwt-Auth-User-Payload" in self.kernel_headers:
            kwargs.get("env")["KERNEL_NOTEBOOK_COOKIE_JAR"] = "kernelcookie" + str(randint(0, 1000))
            jsonKH = json.loads(self.kernel_headers["Jwt-Auth-User-Payload"])
            self.jwt_token = jsonKH["accessToken"]
            await asyncio.get_event_loop().run_in_executor(
                None, self._performConductorJWTLogonAndRetrieval, self.jwt_token, kwargs.get("env")
            )
        else:
            error_message = (
                "ConductorClusterProcessProxy failed to obtain the Conductor credential."
            )
            self.log_and_raise(http_status_code=500, reason=error_message)

        # dynamically update Spark submit parameters
        await asyncio.get_event_loop().run_in_executor(
            None, self._update_launch_info, kernel_cmd, kwargs.get("env")
        )
        # Enable stderr PIPE for the run command
        kwargs.update({"stderr": subprocess.PIPE})
        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.debug(
            "Conductor cluster kernel launched using Conductor endpoint: {}, pid: {}, Kernel ID: {}, "
            "cmd: '{}'".format(
                self.conductor_endpoint, self.local_proc.pid, self.kernel_id, kernel_cmd
            )
        )
        await self.confirm_remote_startup()
        return self

    def _update_launch_info(self, kernel_cmd: list[str], env_dict: dict) -> None:
        """
        Dynamically assemble the spark-submit configuration passed from NB2KG.
        """
        if any(arg.endswith(".sh") for arg in kernel_cmd):
            self.log.debug("kernel_cmd contains execution script")
        else:
            kernel_dir = self.kernel_manager.kernel_spec_manager._find_spec_directory(
                self.kernel_manager.kernel_name
            )
            cmd = pjoin(kernel_dir, "bin/run.sh")
            kernel_cmd.insert(0, cmd)

        # add SPARK_HOME, PYSPARK_PYTHON, update SPARK_OPT to contain SPARK_MASTER and EGO_SERVICE_CREDENTIAL
        env_dict["SPARK_HOME"] = env_dict["KERNEL_SPARK_HOME"]
        env_dict["PYSPARK_PYTHON"] = env_dict["KERNEL_PYSPARK_PYTHON"]
        # add KERNEL_SPARK_OPTS to append user configured Spark configuration
        user_defined_spark_opts = ""
        if "KERNEL_SPARK_OPTS" in env_dict:
            user_defined_spark_opts = env_dict["KERNEL_SPARK_OPTS"]

        # Get updated one_notebook_master_rest_url for KERNEL_NOTEBOOK_MASTER_REST and SPARK_OPTS.
        if self.jwt_token is None:
            self._update_notebook_master_rest_url(env_dict)

        if "--master" not in env_dict["SPARK_OPTS"]:
            env_dict["SPARK_OPTS"] = (
                "--master {master} --conf spark.ego.credential={rest_cred} "
                "--conf spark.pyspark.python={pyspark_python} {spark_opts} "
                "{user_defined_spark_opts}".format(
                    master=env_dict["KERNEL_NOTEBOOK_MASTER_REST"],
                    rest_cred="'" + self.rest_credential + "'",
                    pyspark_python=env_dict["PYSPARK_PYTHON"],
                    spark_opts=env_dict["SPARK_OPTS"],
                    user_defined_spark_opts=user_defined_spark_opts,
                )
            )

    def _update_notebook_master_rest_url(self, env_dict: dict) -> None:
        """
        Updates the notebook master rest url to update KERNEL_NOTEBOOK_MASTER_REST,
        conductor_endpoint, and SPARK_OPTS.
        """

        self.log.debug("Updating notebook master rest urls.")
        response = None
        # Assemble REST call
        header = "Accept: application/json"
        authorization = "Authorization: %s" % self.rest_credential
        if (
            "KERNEL_NOTEBOOK_DATA_DIR" not in env_dict
            or "KERNEL_NOTEBOOK_COOKIE_JAR" not in env_dict
            or "KERNEL_CURL_SECURITY_OPT" not in env_dict
        ):
            self.log.warning(
                "Could not find KERNEL environment variables. Not updating notebook master rest url."
            )
            return
        if (
            "CONDUCTOR_REST_URL" not in env_dict
            or "KERNEL_SIG_ID" not in env_dict
            or "KERNEL_NOTEBOOK_MASTER_REST" not in env_dict
        ):
            self.log.warning(
                "Could not find CONDUCTOR_REST_URL or KERNEL_SIG_ID or KERNEL_NOTEBOOK_MASTER_REST. "
                "Not updating notebook master rest url."
            )
            return

        cookie_jar = pjoin(
            env_dict["KERNEL_NOTEBOOK_DATA_DIR"], env_dict["KERNEL_NOTEBOOK_COOKIE_JAR"]
        )
        sslconf = validate_curl_security_opt(env_dict["KERNEL_CURL_SECURITY_OPT"])
        ascd_rest_url = env_dict["CONDUCTOR_REST_URL"]
        ig_id = quote(str(env_dict["KERNEL_SIG_ID"]), safe="")
        url = f"{ascd_rest_url}conductor/v1/instances?id={ig_id}&fields=outputs"
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        _harden_curl_cmd(cmd)
        # Perform REST call
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True
            )
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            if (
                response is None
                or len(response) < 1
                or not response[0]
                or not response[0]["outputs"]
            ):
                response = None
        except Exception as e:
            self.log.warning(
                f"Getting instance group with cmd '{_redact_cmd(cmd)}' failed with exception: '{e}'.  Continuing..."
            )
            return

        outputs = response[0]["outputs"]

        if (
            "one_notebook_master_rest_url" not in outputs
            or not outputs["one_notebook_master_rest_url"]
            or "value" not in outputs["one_notebook_master_rest_url"]
            or not outputs["one_notebook_master_rest_url"]["value"]
        ):
            self.log.warning(
                "Could not get one_notebook_master_rest_url from instance group. "
                "Not updating notebook master rest url."
            )
            return
        if (
            "one_notebook_master_web_submission_url" not in outputs
            or not outputs["one_notebook_master_web_submission_url"]
            or "value" not in outputs["one_notebook_master_web_submission_url"]
            or not outputs["one_notebook_master_web_submission_url"]["value"]
        ):
            self.log.warning(
                "Could not get one_notebook_master_web_submission_url from instance group. "
                "Not updating notebook master rest url."
            )
            return

        updated_one_notebook_master_rest_url = outputs["one_notebook_master_rest_url"]["value"]
        updated_one_notebook_master_web_submission_url = outputs[
            "one_notebook_master_web_submission_url"
        ]["value"]

        if updated_one_notebook_master_rest_url and updated_one_notebook_master_web_submission_url:
            self.log.debug(
                f"Updating KERNEL_NOTEBOOK_MASTER_REST to '{updated_one_notebook_master_rest_url}'."
            )
            os.environ["KERNEL_NOTEBOOK_MASTER_REST"] = updated_one_notebook_master_rest_url
            env_dict["KERNEL_NOTEBOOK_MASTER_REST"] = updated_one_notebook_master_rest_url
            self.conductor_endpoint = updated_one_notebook_master_web_submission_url

    def poll(self) -> bool | None:
        """
        Submitting a new kernel/app will take a while to be SUBMITTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in SUBMITTED/WAITING/RUNNING state.
        :return: None if the application's ID is available and state is SUBMITTED/WAITING/RUNNING. Otherwise False.
        """
        result = False

        if self._get_application_id():
            state = self._query_app_state_by_driver_id(self.driver_id)
            if state in ConductorClusterProcessProxy.initial_states:
                result = None
        return result

    def send_signal(self, signum: int) -> bool | None:
        """
        Currently only support 0 as poll and other as kill.
        :param signum
        :return: None if signal was successfully sent to kernel, False if an exception was thrown
        """
        self.log.debug(f"ConductorClusterProcessProxy.send_signal {signum}")
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            return super().send_signal(signum)

    def kill(self) -> bool | None:
        """
        Kill a kernel.
        :return: None if the application existed and is not in RUNNING state, False otherwise.
        """
        state = None
        result = False
        if self.driver_id:
            resp = self._kill_app_by_driver_id(self.driver_id)
            self.log.debug(
                "ConductorClusterProcessProxy.kill: kill_app_by_driver_id({}) response: {}, confirming "
                "app state is not RUNNING".format(self.driver_id, resp)
            )
            i = 1
            state = self._query_app_state_by_driver_id(self.driver_id)
            while state not in ConductorClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = self._query_app_state_by_driver_id(self.driver_id)
                i = i + 1

            if state in ConductorClusterProcessProxy.final_states:
                result = None

        super().kill()

        self.log.debug(
            "ConductorClusterProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}".format(
                self.application_id, self.kernel_id, state
            )
        )
        return result

    def cleanup(self) -> None:
        """Clean up the kernel."""
        # we might have a defunct process (if using waitAppCompletion = false) - so poll, kill, wait when we have
        # a local_proc.
        if self.local_proc:
            self.log.debug(
                "ConductorClusterProcessProxy.cleanup: Clearing possible defunct process, pid={}...".format(
                    self.local_proc.pid
                )
            )
            if super().poll():
                super().kill()
            super().wait()
            self.local_proc = None

        # reset application id to force new query - handles kernel restarts/interrupts
        self.application_id = None

        # for cleanup, we should call the superclass last
        super().cleanup()

    def _parse_driver_submission_id(self, submission_response: str) -> None:
        """
        Parse driver id from stderr gotten back from launch_kernel
        :param submission_response
        """
        if submission_response:
            self.log.debug(f"Submission Response: {submission_response}\n")
            matched_lines = [
                line for line in submission_response.split("\n") if "submissionId" in line
            ]
            if matched_lines and len(matched_lines) > 0:
                driver_info = matched_lines[0]
                self.log.debug(f"Driver Info: {driver_info}")
                driver_id = driver_info.split(":")[1]
                driver_id = re.findall(r'"([^"]*)"', driver_id)
                if driver_id and len(driver_id) > 0:
                    self.driver_id = driver_id[0]
                    self.log.debug(f"Driver ID: {driver_id[0]}")
            # Handle Checking for submission error to report
            err_lines = [
                line
                for line in submission_response.split("\n")
                if "Application submission failed" in line
            ]
            if err_lines and len(err_lines) > 0:
                self.log_and_raise(
                    http_status_code=500,
                    reason=err_lines[0][err_lines[0].find("Application submission failed") :],
                )

    async def confirm_remote_startup(self) -> None:
        """
        Confirms the application is in a started state before returning.  Should post-RUNNING states be
        unexpectedly encountered ('FINISHED', 'KILLED', 'RECLAIMED') then we must throw, otherwise the rest
        of the gateway will believe its talking to a valid kernel.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            if self.local_proc.stderr:
                # Read stderr after the launch_kernel, and parse the driver id from the REST response
                output = self.local_proc.stderr.read().decode("utf-8")
                self._parse_driver_submission_id(output)
            i += 1
            await self.handle_timeout()

            if self._get_application_id(True):
                # Once we have an application ID, start monitoring state, obtain assigned host and get connection info
                app_state = self._get_application_state()

                if app_state in ConductorClusterProcessProxy.final_states:
                    error_message = (
                        "KernelID: '{}', ApplicationID: '{}' unexpectedly found in state '{}' "
                        "during kernel startup!".format(
                            self.kernel_id, self.application_id, app_state
                        )
                    )
                    self.log_and_raise(http_status_code=500, reason=error_message)

                self.log.debug(
                    "{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".format(
                        i, app_state, self.assigned_host, self.kernel_id, self.application_id
                    )
                )

                if self.assigned_host:
                    ready_to_connect = await self.receive_connection_info()
            else:
                self.detect_launch_failure()

    def _get_application_state(self) -> str:
        """
        Gets the current application state using the application_id already obtained.  Once the assigned host
        has been identified, it is no longer accessed.
        """
        app_state = None
        apps = self._query_app_by_driver_id(self.driver_id)

        if apps:
            for app in apps:
                if "state" in app:
                    app_state = app["state"]
                if not self.assigned_host and app["driver"]:
                    self.assigned_host = app["driver"]["host"]
                    # Set the driver host to the actual host where the application landed.
                    self.assigned_ip = socket.gethostbyname(self.assigned_host)
        return app_state

    async def handle_timeout(self) -> None:
        """
        Checks to see if the kernel launch timeout has been exceeded while awaiting connection info.
        """
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(
            self.start_time, RemoteProcessProxy.get_current_time()
        )

        if time_interval > self.kernel_launch_timeout:
            reason = f"Application failed to start within {self.kernel_launch_timeout} seconds."
            error_http_code = 500
            if self._get_application_id(True):
                if self._query_app_state_by_driver_id(self.driver_id) != "WAITING":
                    reason = "Kernel unavailable after {} seconds for driver_id {}, app_id {}, launch timeout: {}!"
                    reason = reason.format(
                        time_interval,
                        self.driver_id,
                        self.application_id,
                        self.kernel_launch_timeout,
                    )
                    error_http_code = 503
                else:
                    reason = "App {} is WAITING, but waited too long ({} secs) to get connection file".format(
                        self.application_id, self.kernel_launch_timeout
                    )
            await asyncio.get_event_loop().run_in_executor(None, self.kill)
            timeout_message = f"KernelID: '{self.kernel_id}' launch timeout due to: {reason}"
            self.log_and_raise(http_status_code=error_http_code, reason=timeout_message)

    def _get_application_id(self, ignore_final_states: bool = False) -> str:
        """
        Return the kernel's application ID if available, otherwise None.  If we're obtaining application_id
        from scratch, do not consider kernels in final states.
        """
        if not self.application_id:
            apps = self._query_app_by_driver_id(self.driver_id)
            state_condition = True
            if apps:
                for app in apps:
                    if "state" in app and ignore_final_states:
                        state_condition = (
                            app["state"] not in ConductorClusterProcessProxy.final_states
                        )
                    if "applicationid" in app and len(app["applicationid"]) > 0 and state_condition:
                        self.application_id = app["applicationid"]
                        time_interval = RemoteProcessProxy.get_time_diff(
                            self.start_time, RemoteProcessProxy.get_current_time()
                        )
                        self.log.info(
                            "ApplicationID: '{}' assigned for KernelID: '{}', state: {}, "
                            "{} seconds after starting.".format(
                                app["applicationid"], self.kernel_id, app["state"], time_interval
                            )
                        )
                    else:
                        self.log.debug(
                            "ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(
                                self.kernel_id
                            )
                        )
            else:
                self.log.debug(
                    f"ApplicationID not yet assigned for KernelID: '{self.kernel_id}' - retrying..."
                )
        return self.application_id

    def get_process_info(self) -> dict[str, Any]:
        """
        Captures the base information necessary for kernel persistence relative to Conductor clusters.
        """
        process_info = super().get_process_info()
        process_info.update({"application_id": self.application_id})
        process_info.update({"rest_credential": self.rest_credential})
        return process_info

    def load_process_info(self, process_info: dict[str, Any]) -> None:
        """
        Captures the base information necessary for kernel persistence relative to Conductor clusters.
        """
        super().load_process_info(process_info)
        self.application_id = process_info["application_id"]
        self.rest_credential = process_info["rest_credential"]

    def _query_app_by_driver_id(self, driver_id: str) -> dict | None:
        """
        Retrieve application by using driver ID.
        :param driver_id: as the unique driver id for query
        :return: The JSON object of an application. None if driver_id is not found.
        """
        response = None
        if not driver_id:
            return response
        # Assemble REST call
        env = self.env
        header = "Accept: application/json"
        authorization = "Authorization: %s" % self.rest_credential
        cookie_jar = pjoin(env["KERNEL_NOTEBOOK_DATA_DIR"], env["KERNEL_NOTEBOOK_COOKIE_JAR"])
        sslconf = validate_curl_security_opt(env["KERNEL_CURL_SECURITY_OPT"])
        url = f"{self.conductor_endpoint}/v1/applications?driverid={driver_id}"
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        _harden_curl_cmd(cmd)

        # Perform REST call
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True
            )
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            response = None if not response or not response["applist"] else response["applist"]
        except Exception as e:
            self.log.warning(
                f"Getting application with cmd '{_redact_cmd(cmd)}' failed with exception: '{e}'.  Continuing..."
            )
        return response

    def _query_app_by_id(self, app_id: str) -> dict | None:
        """
        Retrieve an application by application ID.
        :param app_id
        :return: The JSON object of an application. None if app_id is not found.
        """
        response = None
        # Assemble REST call
        env = self.env
        header = "Accept: application/json"
        authorization = "Authorization: %s" % self.rest_credential
        cookie_jar = pjoin(env["KERNEL_NOTEBOOK_DATA_DIR"], env["KERNEL_NOTEBOOK_COOKIE_JAR"])
        sslconf = validate_curl_security_opt(env["KERNEL_CURL_SECURITY_OPT"])
        url = f"{self.conductor_endpoint}/v1/applications?applicationid={app_id}"
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        _harden_curl_cmd(cmd)
        # Perform REST call
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True
            )
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            response = None if response is None or not response["applist"] else response["applist"]
        except Exception as e:
            self.log.warning(
                f"Getting application with cmd '{_redact_cmd(cmd)}' failed with exception: '{e}'.  Continuing..."
            )
        return response

    def _query_app_state_by_driver_id(self, driver_id: str) -> dict | None:
        """
        Return the state of an application.
        :param driver_id:
        :return:
        """
        response = None
        apps = self._query_app_by_driver_id(driver_id)
        if apps:
            for app in apps:
                if "state" in app:
                    response = app["state"]
        return response

    def _get_driver_by_app_id(self, app_id: str) -> dict | None:
        """
        Get driver info from application ID.
        :param app_id
        :return: The JSON response driver information of the corresponding application. None if app_id is not found.
        """
        response = None
        apps = self._query_app_by_id(app_id)
        if apps:
            for app in apps:
                if app and app["driver"]:
                    self.log.debug("Obtain Driver ID: {}".format(app["driver"]["id"]))
                    response = app["driver"]
        else:
            self.log.warning("Application id does not exist")
        return response

    def _kill_app_by_driver_id(self, driver_id: str):
        """
        Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.
        :param driver_id
        :return: The JSON response of killing the application. None if driver is not found.
        """
        self.log.debug(f"Kill driver: {driver_id}")
        if driver_id is None:
            if self.application_id is None:
                return None
            self.log.debug(
                "Driver does not exist, retrieving DriverID with ApplicationID: {}".format(
                    self.application_id
                )
            )
            driver_info = self._get_driver_by_app_id(self.application_id)
            if driver_info:
                self.driver_id = driver_info["id"]
            else:
                return None

        # Assemble REST call
        response = None
        env = self.env
        header = "Accept: application/json"
        authorization = "Authorization: %s" % self.rest_credential
        cookie_jar = pjoin(env["KERNEL_NOTEBOOK_DATA_DIR"], env["KERNEL_NOTEBOOK_COOKIE_JAR"])
        sslconf = validate_curl_security_opt(env["KERNEL_CURL_SECURITY_OPT"])
        url = f"{self.conductor_endpoint}/v1/submissions/kill/{self.driver_id}"
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "POST", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        _harden_curl_cmd(cmd)

        # Perform REST call
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True
            )
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
        except Exception as e:
            self.log.warning(
                f"Termination of application with cmd '{_redact_cmd(cmd)}' failed with exception: '{e}'.  Continuing..."
            )
        self.log.debug(f"Kill response: {response}")
        return response

    def _performRestCall(self, cmd: list[str], url: str, HA_LIST: list[str]) -> tuple:  # noqa
        _harden_curl_cmd(cmd)
        for HA in HA_LIST:
            cmd[-1] = _replace_url_host(url, HA)
            self.log.debug(_redact_cmd(cmd))
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                universal_newlines=True,
            )
            output, stderr = process.communicate()
            if (
                "Could not resolve host" not in stderr
                and "Failed connect to" not in stderr
                and "Connection refused" not in stderr
            ):
                return output, stderr
        self.log_and_raise(
            http_status_code=500, reason="Could not connect to ascd. Verify ascd is running."
        )
        return "Error", "Error"

    # confirm return type
    def _performConductorJWTLogonAndRetrieval(  # noqa
        self, jwt_token: str, env_dict: dict[str, Any]
    ):
        """
        Authenticate to Conductor with a JWT Token and setup the kernel environment variables.
        :param jwt_token: JWT Token to authenticate with to Conductor
        :param env_dict: Environment Dictionary of this Kernel launch
        :return: None
        """
        response = None
        if not jwt_token:
            return response
        # Assemble JWT Auth logon REST call
        env = self.env

        if env["KERNEL_IG_UUID"] is None:
            reasonErr = (
                "Instance group specified is None. Check environment "
                "specified instance group is available."
            )
            self.log_and_raise(http_status_code=500, reason=reasonErr)

        # Determine hostname of ascd_endpoint and setup the HA List.  The failover hosts are
        # client-supplied and receive the credential-bearing requests below, so validate them
        # before any request is sent.
        portcolon = self.ascd_endpoint.rfind(":")
        slash = self.ascd_endpoint.find("://")
        host = self.ascd_endpoint[slash + 3 : portcolon]
        HA_LIST = [
            host,
            *validate_conductor_ha_endpoints(
                env.get("KERNEL_CONDUCTOR_HA_ENDPOINTS"), host, self.conductor_ha_allowed_hosts
            ),
        ]

        header = "Accept: application/json"
        authorization = "Authorization: Bearer %s" % jwt_token
        cookie_jar = pjoin(env["KERNEL_NOTEBOOK_DATA_DIR"], env["KERNEL_NOTEBOOK_COOKIE_JAR"])
        sslconf = validate_curl_security_opt(env["KERNEL_CURL_SECURITY_OPT"])
        url = "{}/auth/logon/jwt?topology={}".format(
            self.ascd_endpoint, quote(str(env["KERNEL_TOPOLOGY"]), safe="")
        )
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        if "Error" in output:
            reasonErr = "Failed to perform JWT Auth Logon. " + output.splitlines()[0]
            self.log.warning(_redact_cmd(cmd))
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        self.rest_credential = url_unescape(output)[1:-1]

        # Assemble EGO Token Logon REST call
        authorization = "Authorization: PlatformToken token=" + output.strip('"')
        url = "%s/auth/logon" % self.ascd_endpoint
        cmd = ["curl", "-v", "-c", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        if "Error" in output:
            reasonErr = "Failed to perform EGO Auth Logon. " + output.splitlines()[0]
            self.log.warning(_redact_cmd(cmd))
            self.log_and_raise(http_status_code=500, reason=reasonErr)

        # Get the Python path to use to make sure the right conda environment is used
        url = "{}/anaconda/instances/{}".format(
            self.ascd_endpoint, quote(str(env["KERNEL_ANACONDA_INST_UUID"]), safe="")
        )
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        response = json.loads(output) if output else None
        if response is None or not response["parameters"]["deploy_home"]["value"]:
            reasonErr = "Could not retrieve anaconda instance. Verify anaconda instance with id "
            reasonErr = reasonErr + env["KERNEL_ANACONDA_INST_UUID"] + " exists"
            self.log.warning(_redact_cmd(cmd))
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        else:
            env_dict["KERNEL_PYSPARK_PYTHON"] = (
                response["parameters"]["deploy_home"]["value"]
                + "/anaconda/envs/"
                + env["KERNEL_ANACONDA_ENV"]
                + "/bin/python"
            )

        # Get instance group information we need
        url = "{}/instances?id={}&fields=sparkinstancegroup,outputs".format(
            self.ascd_endpoint,
            quote(str(env["KERNEL_IG_UUID"]), safe=""),
        )
        cmd = ["curl", "-v", "-b", cookie_jar, "-X", "GET", "-H", header, "-H", authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        response = json.loads(output) if output else None

        if response is None or len(response) == 0 or response[0] is None:
            reasonErr = (
                "Could not retrieve instance group. Verify instance group with id "
                + env["KERNEL_IG_UUID"]
                + " exists."
            )
            self.log.warning(_redact_cmd(cmd))
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        elif (
            response is None
            or response[0] is None
            or "value" not in response[0]["outputs"]["batch_master_rest_urls"]
        ):
            reasonErr = (
                "Could not retrieve outputs for instance group. Verify instance group with id "
                + env["KERNEL_IG_UUID"]
                + " is started"
            )
            self.log.warning(_redact_cmd(cmd))
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        else:
            env_dict["KERNEL_SPARK_HOME"] = response[0]["sparkinstancegroup"]["sparkhomedir"]
            env_dict["KERNEL_NOTEBOOK_MASTER_REST"] = response[0]["outputs"][
                "batch_master_rest_urls"
            ]["value"]
            self.conductor_endpoint = response[0]["outputs"]["one_batch_master_web_submission_url"][
                "value"
            ]
        return response


# Conductor HA failover host validation.
#
# Every Conductor REST call carries a JWT or EGO PlatformToken, and when the primary ascd
# host is unreachable the call is retried against each host in the client-supplied
# KERNEL_CONDUCTOR_HA_ENDPOINTS.  Clients may name their own (e.g. their team's) Conductor
# hosts, but those credentials must never reach a host outside the operator's trust
# boundary (EG_CONDUCTOR_HA_ALLOWED_HOSTS), nor an internal address.


def _harden_curl_cmd(cmd: list[str]) -> list[str]:
    """Insert curl safety flags, in place, immediately after the ``curl`` program name.

    ``--globoff`` stops curl from interpreting ``[...]``/``{...}`` in a (client-influenced)
    URL as a glob that expands into many requests; ``--connect-timeout`` bounds each
    connection attempt.  Returns ``cmd`` for convenience.
    """
    cmd[1:1] = ["--globoff", "--connect-timeout", str(_CURL_CONNECT_TIMEOUT_SECONDS)]
    return cmd


def _redact_cmd(cmd: list[str]) -> list[str]:
    """Return a copy of a curl command with Authorization header values masked.

    Each authenticated Conductor call passes the credential as an ``Authorization: ...``
    header argument.  The command is logged (at DEBUG, and at WARNING on failure), so the
    header value is replaced with the redaction mask before logging to keep JWTs and EGO
    PlatformTokens out of the logs.  The original list is not modified.
    """
    return [
        f"Authorization: {redaction_mask}" if arg.lower().startswith("authorization:") else arg
        for arg in cmd
    ]


def _replace_url_host(url: str, host: str) -> str:
    """Return ``url`` with its host replaced by ``host``, preserving port, path and query.

    Done via urlsplit/urlunsplit rather than string surgery so that a ``:`` or ``@`` in the
    (client-supplied) path or query cannot shift the authority curl connects to.  The port
    comes from ``url`` (the operator-configured endpoint); ``host`` is a bare hostname.
    """
    parts = urlsplit(url)
    netloc = f"{host}:{parts.port}" if parts.port is not None else host
    return urlunsplit(parts._replace(netloc=netloc))


# A failover host is spliced into the request URL in place of the primary host (see
# _performRestCall), so it must be a bare RFC 1123 hostname (underscores tolerated for
# legacy internal names) or IPv4 address.  A scheme, port, path, query, fragment or
# userinfo would let the request reach a different host than the one validated.
_HA_HOST_LABEL_RE = re.compile(r"(?!-)[a-z0-9_-]{1,63}(?<!-)")
_HA_HOST_MAX_LENGTH = 253
_THIS_NETWORK = ipaddress.IPv4Network("0.0.0.0/8")
# Each failover host is tried, in turn, on every one of the four authenticated REST calls.
# Cap the client-supplied list so a kernel launch cannot fan out into an unbounded number
# of credential-bearing connection attempts.
_MAX_HA_FAILOVER_HOSTS = 16


def validate_conductor_ha_endpoints(
    value: str | None,
    primary_host: str,
    allowed_hosts: str | Iterable[str] | None = None,
) -> list[str]:
    """Validate ``KERNEL_CONDUCTOR_HA_ENDPOINTS`` and return its failover hosts.

    Each comma-separated entry must be a bare hostname or IPv4 address, must not be an
    internal address (loopback, link-local, multicast, reserved or unspecified), and must
    fall inside the trust boundary given by ``allowed_hosts``.  When ``allowed_hosts`` is
    empty, the boundary is the DNS domain of ``primary_host``
    (``ascd1.corp.example.com`` -> ``corp.example.com``).

    Parameters
    ----------
    value:
        Raw ``KERNEL_CONDUCTOR_HA_ENDPOINTS`` value.  ``None`` or empty means no failover
        hosts.
    primary_host:
        Hostname of the operator-configured Conductor (ascd) endpoint.
    allowed_hosts:
        DNS domains (matching the domain and its subdomains) and IPv4 CIDRs, as a list or
        a comma-separated string.

    Returns
    -------
    list[str]
        The validated, lowercased failover hosts, de-duplicated and with any entry equal
        to ``primary_host`` removed, in the order given (may be empty).

    Raises
    ------
    tornado.web.HTTPError
        400 if any entry is malformed, an internal address, outside the trust boundary, or
        if more than ``_MAX_HA_FAILOVER_HOSTS`` distinct failover hosts are supplied.
    """
    domains, networks = _ha_trust_boundary(primary_host, allowed_hosts)
    primary = primary_host.strip().lower()
    hosts: list[str] = []
    seen = {primary}
    for position, entry in enumerate((value or "").split(","), start=1):
        host = entry.strip().lower()
        if not host:
            continue
        # Error messages identify a malformed entry by position rather than echoing it:
        # tornado %-formats the message when logging it.  Entries that pass this check
        # are limited to [a-z0-9_.-] and are safe to echo.
        if not _is_bare_hostname(host):
            raise HTTPError(
                400,
                f"KERNEL_CONDUCTOR_HA_ENDPOINTS entry {position} is not a bare hostname or "
                "IPv4 address",
            )
        ip = _parse_ipv4(host)
        if _is_internal_address(host, ip):
            raise HTTPError(
                400, f"KERNEL_CONDUCTOR_HA_ENDPOINTS host '{host}' is an internal address"
            )
        if ip is None:
            in_boundary = any(host == domain or host.endswith("." + domain) for domain in domains)
        else:
            in_boundary = any(ip in network for network in networks)
        if not in_boundary:
            raise HTTPError(
                400,
                f"KERNEL_CONDUCTOR_HA_ENDPOINTS host '{host}' is not an allowed Conductor "
                "host (see EG_CONDUCTOR_HA_ALLOWED_HOSTS)",
            )
        # Drop duplicates and the primary host; both only add redundant failover attempts.
        if host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    if len(hosts) > _MAX_HA_FAILOVER_HOSTS:
        raise HTTPError(
            400,
            f"KERNEL_CONDUCTOR_HA_ENDPOINTS specifies more than {_MAX_HA_FAILOVER_HOSTS} "
            "failover hosts",
        )
    return hosts


def _ha_trust_boundary(
    primary_host: str, allowed_hosts: str | Iterable[str] | None
) -> tuple[list[str], list[ipaddress.IPv4Network]]:
    """Split ``allowed_hosts`` into DNS domains and IPv4 networks.

    Falls back to the DNS domain of ``primary_host`` when no entries are configured.
    """
    if isinstance(allowed_hosts, str):
        allowed_hosts = allowed_hosts.split(",")
    domains: list[str] = []
    networks: list[ipaddress.IPv4Network] = []
    for raw_entry in allowed_hosts or []:
        entry = raw_entry.strip().lower()
        if not entry:
            continue
        try:
            networks.append(ipaddress.IPv4Network(entry, strict=False))
        except ValueError:
            # Accept "corp.example.com", ".corp.example.com" and "*.corp.example.com".
            domain = entry.removeprefix("*.").lstrip(".")
            if domain:
                domains.append(domain)
    if not domains and not networks:
        domains = _endpoint_domain(primary_host)
    return domains, networks


def _endpoint_domain(primary_host: str) -> list[str]:
    """Return the DNS domain of the Conductor endpoint host as the default boundary.

    An IP-literal, single-label or two-label endpoint yields no default, so that the
    boundary is never wider than a registrable domain (e.g. ``example.com`` -> ``com``).
    """
    labels = primary_host.lower().split(".")
    if _parse_ipv4(primary_host) is not None or len(labels) < 3:
        return []
    return [".".join(labels[1:])]


def _is_bare_hostname(host: str) -> bool:
    """Whether ``host`` is a bare (lowercase) hostname or IPv4 address."""
    return len(host) <= _HA_HOST_MAX_LENGTH and all(
        _HA_HOST_LABEL_RE.fullmatch(label) for label in host.split(".")
    )


def _parse_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """Return ``host`` as an IPv4 address, or ``None`` if it is a hostname."""
    try:
        return ipaddress.IPv4Address(host)
    except ValueError:
        return None


def _is_internal_address(host: str, ip: ipaddress.IPv4Address | None) -> bool:
    """Whether ``host`` names this machine or a non-unicast/special-purpose address."""
    if ip is None:
        return host == "localhost" or host.endswith(".localhost")
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or ip in _THIS_NETWORK
    )
