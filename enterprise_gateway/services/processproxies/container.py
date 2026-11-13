"""Code related to managing kernels running in containers."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import abc
import fnmatch
import logging
import os
import re
import signal
from collections.abc import Iterable, Mapping
from typing import Any

import urllib3  # docker ends up using this and it causes lots of noise, so turn off warnings
from jupyter_client import localinterfaces
from tornado import web

from ..kernels.remotemanager import RemoteKernelManager
from .processproxy import RemoteProcessProxy, proxy_config_override, split_list_setting

log = logging.getLogger(__name__)

urllib3.disable_warnings()

local_ip = localinterfaces.public_ips()[0]

default_kernel_uid = "1000"  # jovyan user is the default
default_kernel_gid = "100"  # users group is the default


def _parse_prohibited_ids(env_var: str, default: str) -> list[int]:
    """Parse a comma-separated list of IDs from an environment variable into integers.

    Raises:
        ValueError: If any entry in the configured value is not a valid integer.
            This enforces a fail-closed posture — a misconfigured prohibited list
            (e.g. usernames instead of numeric IDs) will prevent startup rather than
            silently yielding an empty list.
    """
    result: list[int] = []
    raw_value = os.getenv(env_var, default)
    for item in raw_value.split(","):
        stripped = item.strip()
        if stripped:
            try:
                result.append(int(stripped))
            except ValueError:
                msg = (
                    f"Invalid entry '{stripped}' in {env_var}='{raw_value}'. "
                    f"All entries must be numeric IDs, not usernames or group names. "
                    f"Example: {env_var}=0,1000"
                )
                log.critical(msg)
                raise ValueError(msg) from None
    return result


# These could be enforced via a PodSecurityPolicy, but those affect
# all pods so the cluster admin would need to configure those for
# all applications.
prohibited_uids = _parse_prohibited_ids("EG_PROHIBITED_UIDS", "0")
prohibited_gids = _parse_prohibited_ids("EG_PROHIBITED_GIDS", "0")

mirror_working_dirs = bool(os.getenv("EG_MIRROR_WORKING_DIRS", "false").lower() == "true")

# Get the globally-configured default images.  Defaulting to None if not set.
default_kernel_image = os.getenv("EG_KERNEL_IMAGE")
default_kernel_executor_image = os.getenv("EG_KERNEL_EXECUTOR_IMAGE")

# Container image references: [registry[:port]/]repository[:tag][@digest], following the
# grammar of github.com/distribution/reference.  Repository path components are lowercase.
_PATH_COMPONENT = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
_DOMAIN_COMPONENT = r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
_DOMAIN = rf"(?:{_DOMAIN_COMPONENT}(?:\.{_DOMAIN_COMPONENT})*|\[[a-fA-F0-9:]+\])(?::[0-9]+)?"
_IMAGE_REFERENCE_PATTERN = re.compile(
    rf"(?P<name>(?:{_DOMAIN}/)?{_PATH_COMPONENT}(?:/{_PATH_COMPONENT})*)"
    r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))?"
    r"(?:@(?P<digest>[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*:[0-9A-Fa-f]{32,}))?"
)
_MAX_IMAGE_NAME_LENGTH = 255


def validate_kernel_images(
    client_env: Mapping[str, Any],
    allowed_images: str | Iterable[str] | None,
    configured_images: Iterable[str] = (),
) -> None:
    """Reject client-supplied kernel images that are malformed or not allowed.

    ``KERNEL_IMAGE`` and ``KERNEL_EXECUTOR_IMAGE`` select the container image a kernel runs.
    Each must be a well-formed image reference.  When ``allowed_images`` is set, the image's
    repository must also match one of its patterns (GHSA-hchm-85c7-pr3j).  Patterns are
    shell-style globs (``*``, ``?``) over the repository, normalized the way Docker does:
    ``elyra/*`` means ``docker.io/elyra/*`` and ``python`` means ``docker.io/library/python``.
    Tags and digests are not part of the match.  ``configured_images`` (the operator's own
    images for this kernel) are always allowed, so clients that echo them keep working.

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.
    allowed_images : str | Iterable[str] | None
        Repository patterns, as a list or comma-separated string.  Empty allows any
        well-formed image; ``*`` does the same explicitly.
    configured_images : Iterable[str]
        Image references configured by the operator for this kernel.

    Raises
    ------
    tornado.web.HTTPError
        400 if an image reference is malformed (the value is not echoed) or does not match
        an allowed pattern.
    """
    patterns = split_list_setting(allowed_images)
    configured = {_canonical_reference(image) for image in configured_images if image}
    for name in ("KERNEL_IMAGE", "KERNEL_EXECUTOR_IMAGE"):
        if name not in client_env:
            continue
        image = client_env[name]
        reference = _canonical_reference(image)
        if reference is None:
            raise web.HTTPError(
                400,
                f"{name} is not a valid container image reference "
                "([registry/]repository[:tag][@digest], with a lowercase repository)",
            )
        if not patterns or "*" in patterns or reference in configured:
            continue
        img_domain, img_path = _split_repository(_IMAGE_REFERENCE_PATTERN.fullmatch(image)["name"])
        if not any(_repository_matches(img_domain, img_path, pattern) for pattern in patterns):
            raise web.HTTPError(
                400,
                f"{name} '{image}' is not allowed. Allowed images: {', '.join(patterns)}. "
                "To permit it, ask your Enterprise Gateway operator to add a matching pattern to "
                "EG_ALLOWED_KERNEL_IMAGES (or to allowed_images in the kernelspec's process-proxy "
                "config).",
            )


def _repository_matches(img_domain: str, img_path: str, pattern: str) -> bool:
    """Match an image's (domain, path) against an allowlist pattern.

    The pattern is canonicalized the same way, then matched part-by-part, so a ``*`` in the
    registry part cannot cross the ``/`` into the path and let another registry imitate the
    pattern (for example ``*.example.com/*`` must not accept ``evil.com/x.example.com/y``).
    """
    pat_domain, pat_path = _split_repository(pattern)
    return fnmatch.fnmatchcase(img_domain, pat_domain) and fnmatch.fnmatchcase(img_path, pat_path)


def _has_glob(value: str) -> bool:
    """Whether ``value`` contains an ``fnmatch`` wildcard."""
    return any(char in value for char in "*?[")


def _split_repository(name: str) -> tuple[str, str]:
    """Split ``name`` into Docker's explicit (registry, path), as in ``splitDockerDomain``.

    As in Docker, the first component names a registry only if it contains '.' or ':', is
    'localhost', or is not lowercase; otherwise the repository is on Docker Hub, so
    ``elyra.evil.com/x`` is a different registry while ``elyra/x`` is ``docker.io/elyra/x``.
    Docker's ``library/`` prefix for a bare official image (``python`` -> ``library/python``)
    is applied only to literal names, not to a wildcard path, so ``docker.io/*`` keeps meaning
    all of Docker Hub rather than only its official images.
    """
    first, separator, rest = name.partition("/")
    if separator and (
        "." in first or ":" in first or first == "localhost" or first.lower() != first
    ):
        domain, path = first, rest
    else:
        domain, path = "docker.io", name
    if domain == "index.docker.io":  # legacy name of Docker Hub
        domain = "docker.io"
    if domain == "docker.io" and "/" not in path and not _has_glob(path):
        path = f"library/{path}"
    return domain, path


def _canonical_repository(name: str) -> str:
    """Return ``name`` with Docker's default registry and namespace made explicit."""
    domain, path = _split_repository(name)
    return f"{domain}/{path}"


def _canonical_reference(image: Any) -> str | None:
    """Return the canonical form of an image reference, or None if it is malformed."""
    if not isinstance(image, str):
        return None
    match = _IMAGE_REFERENCE_PATTERN.fullmatch(image)
    if match is None or len(match["name"]) > _MAX_IMAGE_NAME_LENGTH:
        return None
    reference = _canonical_repository(match["name"])
    if match["tag"] or not match["digest"]:
        reference += f":{match['tag'] or 'latest'}"
    if match["digest"]:
        reference += f"@{match['digest']}"
    return reference


class ContainerProcessProxy(RemoteProcessProxy):
    """
    Kernel lifecycle management for container-based kernels.
    """

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.container_name = ""
        self.assigned_node_ip = None

    @classmethod
    def validate_client_env(
        cls,
        client_env: Mapping[str, Any],
        proxy_config: Mapping[str, Any],
        kernel_manager: RemoteKernelManager,
    ) -> None:
        """Rejects client-supplied kernel images that are malformed or not allowed."""
        super().validate_client_env(client_env, proxy_config, kernel_manager)
        configured_images = (
            proxy_config.get("image_name", default_kernel_image),
            proxy_config.get("executor_image_name", default_kernel_executor_image),
        )
        validate_kernel_images(
            client_env,
            proxy_config_override(
                proxy_config, "allowed_images", kernel_manager.allowed_kernel_images
            ),
            configured_images,
        )

    def _determine_kernel_images(self, **kwargs: dict[str, Any] | None) -> None:
        """
        Determine which kernel images to use.

        Initialize to any defined in the process proxy override that then let those provided
        by client via env override.
        """
        kernel_image = self.proxy_config.get("image_name", default_kernel_image)
        self.kernel_image = kwargs["env"].get("KERNEL_IMAGE", kernel_image)

        if self.kernel_image is None:
            self.log_and_raise(
                http_status_code=500,
                reason="No kernel image could be determined! Set the `image_name` in the "
                "process_proxy.config stanza of the corresponding kernel.json file.",
            )

        # If no default executor image is configured, default it to current image
        kernel_executor_image = self.proxy_config.get(
            "executor_image_name", default_kernel_executor_image or self.kernel_image
        )
        self.kernel_executor_image = kwargs["env"].get(
            "KERNEL_EXECUTOR_IMAGE", kernel_executor_image
        )

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> ContainerProcessProxy:
        """
        Launches the specified process within the container environment.
        """
        # Set env before superclass call so we see these in the debug output

        self._determine_kernel_images(**kwargs)
        kwargs["env"]["KERNEL_IMAGE"] = self.kernel_image
        kwargs["env"]["KERNEL_EXECUTOR_IMAGE"] = self.kernel_executor_image

        # If mirroring is not enabled, remove working directory if present
        if not mirror_working_dirs and "KERNEL_WORKING_DIR" in kwargs["env"]:
            del kwargs["env"]["KERNEL_WORKING_DIR"]

        self._enforce_prohibited_ids(**kwargs)

        await super().launch_process(kernel_cmd, **kwargs)

        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info(
            "{}: kernel launched. Kernel image: {}, KernelID: {}, cmd: '{}'".format(
                self.__class__.__name__, self.kernel_image, self.kernel_id, kernel_cmd
            )
        )

        await self.confirm_remote_startup()
        return self

    def _enforce_prohibited_ids(self, **kwargs: dict[str, Any] | None) -> None:
        """Determine UID and GID with which to launch container and ensure they are not prohibited."""
        kernel_uid = kwargs["env"].get("KERNEL_UID", default_kernel_uid)
        kernel_gid = kwargs["env"].get("KERNEL_GID", default_kernel_gid)

        try:
            uid_int = int(kernel_uid)
        except (ValueError, TypeError):
            self.log_and_raise(
                http_status_code=403,
                reason=f"Invalid KERNEL_UID value '{kernel_uid}': not a valid integer!",
            )

        try:
            gid_int = int(kernel_gid)
        except (ValueError, TypeError):
            self.log_and_raise(
                http_status_code=403,
                reason=f"Invalid KERNEL_GID value '{kernel_gid}': not a valid integer!",
            )

        max_id = 4294967295  # uint32 max — Linux uid_t/gid_t upper bound

        if not (0 <= uid_int <= max_id):
            self.log_and_raise(
                http_status_code=403,
                reason=f"Invalid KERNEL_UID value '{kernel_uid}': must be in range 0-{max_id}!",
            )

        if not (0 <= gid_int <= max_id):
            self.log_and_raise(
                http_status_code=403,
                reason=f"Invalid KERNEL_GID value '{kernel_gid}': must be in range 0-{max_id}!",
            )

        if uid_int in prohibited_uids:
            self.log_and_raise(
                http_status_code=403,
                reason=f"Kernel's UID value of '{kernel_uid}' has been denied via EG_PROHIBITED_UIDS!",
            )

        if gid_int in prohibited_gids:
            self.log_and_raise(
                http_status_code=403,
                reason=f"Kernel's GID value of '{kernel_gid}' has been denied via EG_PROHIBITED_GIDS!",
            )

        # Ensure the kernel's env has normalized values
        kwargs["env"]["KERNEL_UID"] = str(uid_int)
        kwargs["env"]["KERNEL_GID"] = str(gid_int)

    def poll(self) -> bool | None:
        """Determines if container is still active.

        Submitting a new kernel to the container manager will take a while to be Running.
        Thus kernel ID will probably not be available immediately for poll.
        So will regard the container as active when no status is available or one of the initial
        phases.

        Returns
        -------
        None if the container cannot be found or its in an initial state. Otherwise False.
        """
        result = False

        container_status = self.get_container_status(None)
        # Do not check whether container_status is None
        # EG couldn't restart kernels although connections exists.
        # See https://github.com/jupyter-server/enterprise_gateway/issues/827
        if container_status in self.get_initial_states():
            result = None
        return result

    def send_signal(self, signum: int) -> bool | None:
        """Send signal `signum` to container.

        Parameters
        ----------
        signum : int
            The signal number to send.  Zero is used to determine heartbeat.
        """
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            # This is very likely an interrupt signal, so defer to the super class
            # which should use the communication port.
            return super().send_signal(signum)

    def kill(self) -> bool | None:
        """Kills a containerized kernel.

        Returns
        -------
        None if the container is gracefully terminated, False otherwise.
        """
        result = None

        if self.container_name:  # We only have something to terminate if we have a name
            result = self.terminate_container_resources()

        return result

    def shutdown_listener(self):
        """Shut down the listener."""
        super().shutdown_listener()
        if self.container_name:  # We only have something to terminate if we have a name
            self.terminate_container_resources()

    async def confirm_remote_startup(self) -> None:
        """Confirms the container has started and returned necessary connection information."""
        self.log.debug("Trying to confirm kernel container startup status")
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 1
        container_status = self.get_container_status(i)
        while not container_status:
            i += 1
            self.detect_launch_failure()
            await self.handle_timeout()

            container_status = self.get_container_status(i)

        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            container_status = self.get_container_status(i)
            if container_status:
                if container_status in self.get_error_states():
                    self.log_and_raise(
                        http_status_code=500,
                        reason=f"Error starting kernel container; status: '{container_status}'.",
                    )
                else:
                    if self.assigned_host:
                        ready_to_connect = await self.receive_connection_info()
                        self.pid = (
                            0  # We won't send process signals for kubernetes lifecycle management
                        )
                        self.pgid = 0
            else:
                self.log_and_raise(
                    http_status_code=500,
                    reason="Error starting kernel container; status was not available. "
                    "Perhaps the kernel pod died unexpectedly",
                )

    def get_process_info(self) -> dict[str, Any]:
        """Captures the base information necessary for kernel persistence relative to containers."""
        process_info = super().get_process_info()
        process_info.update(
            {
                "assigned_node_ip": self.assigned_node_ip,
            }
        )
        return process_info

    def load_process_info(self, process_info: dict[str, Any]) -> None:
        """Loads the base information necessary for kernel persistence relative to containers."""
        super().load_process_info(process_info)
        self.assigned_node_ip = process_info["assigned_node_ip"]

    @abc.abstractmethod
    def get_initial_states(self):
        """Return list of states in lowercase indicating container is starting (includes running)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_error_states(self):
        """Returns the list of error states (in lowercase)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_container_status(self, iteration: int | None) -> str:
        """Returns the current container state (in lowercase) or the empty string if not available."""
        raise NotImplementedError

    @abc.abstractmethod
    def terminate_container_resources(self):
        """Terminate any artifacts created on behalf of the container's lifetime."""
        raise NotImplementedError
