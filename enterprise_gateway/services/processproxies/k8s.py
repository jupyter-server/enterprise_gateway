"""Code related to managing kernels running in Kubernetes clusters."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import fnmatch
import logging
import os
import re
import shlex
from collections.abc import Iterable, Mapping
from typing import Any

import kubernetes
import urllib3
import yaml
from kubernetes import client, config
from tornado import web

from ..kernels.remotemanager import RemoteKernelManager
from ..sessions.kernelsessionmanager import KernelSessionManager
from .container import ContainerProcessProxy
from .processproxy import proxy_config_override, split_list_setting

urllib3.disable_warnings()

# Default logging level of kubernetes produces too much noise - raise to warning only.
logging.getLogger("kubernetes").setLevel(os.environ.get("EG_KUBERNETES_LOG_LEVEL", logging.WARNING))

enterprise_gateway_namespace = os.environ.get("EG_NAMESPACE", "default")
default_kernel_service_account_name = os.environ.get(
    "EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME", "default"
)
kernel_cluster_role = os.environ.get("EG_KERNEL_CLUSTER_ROLE", "cluster-admin")
share_gateway_namespace = bool(os.environ.get("EG_SHARED_NAMESPACE", "False").lower() == "true")
kpt_dir = os.environ.get("EG_POD_TEMPLATE_DIR", "/tmp")  # noqa

POD_SECURITY_LEVELS = ("privileged", "baseline", "restricted")


def pod_security_labels(level: str) -> dict[str, str]:
    """Return the Pod Security Admission labels that enforce ``level`` on a namespace.

    Kernels can create pods in the namespace Enterprise Gateway creates for them (Spark
    drivers create executors), which no gateway-side check sees.  Enforcing a Pod Security
    Standard on the namespace keeps those pods from using host paths, host namespaces or
    privileged containers.

    Parameters
    ----------
    level : str
        A Pod Security Standard (privileged, baseline or restricted), or empty to add no
        labels and leave the namespace to the cluster's default policy.

    Returns
    -------
    dict[str, str]
        The enforce, warn and audit labels for ``level``.

    Raises
    ------
    ValueError
        If ``level`` is not a Pod Security Standard.  This fails startup rather than
        silently creating unprotected namespaces.
    """
    if not level:
        return {}
    if level not in POD_SECURITY_LEVELS:
        msg = (
            f"Invalid EG_KERNEL_NAMESPACE_POD_SECURITY value '{level}'. Use one of "
            f"{', '.join(POD_SECURITY_LEVELS)}, or an empty value to add no labels."
        )
        raise ValueError(msg)
    return {f"pod-security.kubernetes.io/{mode}": level for mode in ("enforce", "warn", "audit")}


kernel_namespace_pod_security_labels = pod_security_labels(
    os.environ.get("EG_KERNEL_NAMESPACE_POD_SECURITY", "baseline").strip()
)

config.load_incluster_config()

# Fields of a Kubernetes VolumeMount.  Like volume types, field names are matched exactly:
# API servers that decoded field names case-insensitively would accept "MountPropagation".
VOLUME_MOUNT_FIELDS = frozenset(
    {
        "name",
        "mountPath",
        "readOnly",
        "subPath",
        "subPathExpr",
        "mountPropagation",
        "recursiveReadOnly",
    }
)

_DNS1123_LABEL_PATTERN = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_DNS1123_SUBDOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}$)[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*"
)
# Volume types and field names are camelCase identifiers.  Anything else is never echoed
# back to the client.
_FIELD_NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,62}")

# Namespaces this gateway created for kernels and has not deleted yet.  Clients must not
# launch into them (GHSA-hchm-85c7-pr3j): a pod there gets the owning kernel's service
# account permissions, can mount its secrets and volumes, and passes its network policies.
# Namespaces are registered as soon as they exist, so kernels still starting are covered.
_managed_kernel_namespaces: set[str] = set()


def validate_kernel_namespace(
    client_env: Mapping[str, Any],
    allowed_namespaces: str | Iterable[str] | None,
    gateway_namespace: str,
    managed_namespaces: Iterable[str],
) -> None:
    """Reject a client-supplied kernel namespace unless the operator allows it.

    Enterprise Gateway can create pods in any namespace, so a client that picks the
    namespace (``KERNEL_NAMESPACE``) also picks which service accounts, secrets and volumes
    its kernel can use.  A client-supplied namespace must match ``allowed_namespaces``
    (shell-style patterns), which is empty by default.  The gateway's own namespace,
    ``kube-*`` namespaces, and namespaces the gateway created for other kernels are always
    rejected, even when ``*`` is allowed (GHSA-hchm-85c7-pr3j).  Kernels that do not set
    ``KERNEL_NAMESPACE`` are not affected.

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.
    allowed_namespaces : str | Iterable[str] | None
        Namespace patterns clients may use, as a list or comma-separated string.
    gateway_namespace : str
        The namespace Enterprise Gateway runs in.
    managed_namespaces : Iterable[str]
        Namespaces Enterprise Gateway created for kernels and has not deleted.

    Raises
    ------
    tornado.web.HTTPError
        400 if the namespace is malformed (the value is not echoed), reserved, owned by
        another kernel, or not allowed.
    """
    if "KERNEL_NAMESPACE" not in client_env:
        return
    namespace = client_env["KERNEL_NAMESPACE"]
    if not isinstance(namespace, str) or not _DNS1123_LABEL_PATTERN.fullmatch(namespace):
        raise web.HTTPError(
            400,
            "KERNEL_NAMESPACE must be a valid Kubernetes namespace name (lowercase letters, "
            "digits and '-', at most 63 characters)",
        )
    omit_hint = "Or omit KERNEL_NAMESPACE so Enterprise Gateway creates a namespace for the kernel."
    if namespace == gateway_namespace or namespace.startswith("kube-"):
        owner = "Enterprise Gateway" if namespace == gateway_namespace else "Kubernetes"
        raise web.HTTPError(
            400,
            f"KERNEL_NAMESPACE '{namespace}' is reserved for {owner} and cannot be used for "
            f"kernels. {omit_hint}",
        )
    patterns = split_list_setting(allowed_namespaces)
    if not any(fnmatch.fnmatchcase(namespace, pattern) for pattern in patterns):
        raise web.HTTPError(
            400,
            f"KERNEL_NAMESPACE '{namespace}' is not permitted. Enterprise Gateway only launches "
            "kernels into client-specified namespaces that match EG_ALLOWED_KERNEL_NAMESPACES "
            "(or allowed_namespaces in the kernelspec's process-proxy config). Ask your "
            "Enterprise Gateway operator to add it, or omit KERNEL_NAMESPACE so Enterprise "
            "Gateway creates a namespace for the kernel.",
        )
    if namespace in managed_namespaces:
        raise web.HTTPError(
            400,
            f"KERNEL_NAMESPACE '{namespace}' cannot be used: Enterprise Gateway created it for "
            f"another kernel. {omit_hint}",
        )


# Label that Enterprise Gateway sets on every namespace it creates for a kernel.  A client
# namespace carrying it was created by the gateway (possibly on another replica, or before a
# restart) and must not be reused -- see ``_create_kernel_namespace``.
_EG_NAMESPACE_OWNERSHIP_LABEL = "kernel_id"


def reject_client_namespace_owned_by_eg(client_env: Mapping[str, Any]) -> None:
    """Reject a client namespace that the Kubernetes API shows the gateway created.

    ``_managed_kernel_namespaces`` only records namespaces created by *this* process, so a
    second replica, or the same gateway after a restart, would not recognize its own kernel
    namespaces.  This confirms against the API that a client-supplied ``KERNEL_NAMESPACE``
    does not carry the gateway's per-kernel label before reusing it (GHSA-hchm-85c7-pr3j).

    The check is positive: the namespace is rejected only when the API confirms the label.
    A missing namespace (404) is allowed -- the client owns its lifecycle -- and a transient
    API error is logged and allowed, leaving the allowlist as the primary gate.

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.

    Raises
    ------
    tornado.web.HTTPError
        400 if the namespace carries the gateway's per-kernel label.
    """
    namespace = client_env.get("KERNEL_NAMESPACE")
    if not namespace:
        return
    try:
        read_namespace = client.CoreV1Api().read_namespace(name=namespace)
    except client.rest.ApiException as err:
        if err.status == 404:
            return
        logging.getLogger(__name__).warning(
            "Could not read namespace '%s' to confirm ownership (status %s); allowing it on the "
            "basis of the allowlist.",
            namespace,
            err.status,
        )
        return
    except Exception as err:  # never fail a launch on a transient namespace lookup error
        logging.getLogger(__name__).warning(
            "Could not read namespace '%s' to confirm ownership (%s); allowing it on the basis "
            "of the allowlist.",
            namespace,
            err,
        )
        return
    metadata = getattr(read_namespace, "metadata", None)
    labels = getattr(metadata, "labels", None) or {}
    if _EG_NAMESPACE_OWNERSHIP_LABEL in labels:
        raise web.HTTPError(
            400,
            f"KERNEL_NAMESPACE '{namespace}' was created by Enterprise Gateway for another "
            "kernel and cannot be reused. Omit KERNEL_NAMESPACE so Enterprise Gateway creates a "
            "namespace for the kernel, or use a namespace you manage yourself.",
        )


def validate_kernel_service_account(
    client_env: Mapping[str, Any], default_service_account: str
) -> None:
    """Reject an unsafe client-supplied ``KERNEL_SERVICE_ACCOUNT_NAME``.

    The name must be a valid Kubernetes service account name.  In addition, a non-default
    account is honored only when the client also supplies a ``KERNEL_NAMESPACE`` (which the
    namespace check has confirmed is operator-allowed and is not the gateway's own).  Without
    a client namespace the kernel lands in a namespace Enterprise Gateway chooses -- a
    per-kernel namespace, or the gateway's own namespace when ``EG_SHARED_NAMESPACE`` is set --
    so letting the client name the account there would, in shared mode, run the kernel as the
    gateway's own service account (GHSA-hchm-85c7-pr3j).

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.
    default_service_account : str
        The account Enterprise Gateway uses when the client supplies none
        (``EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME``).

    Raises
    ------
    tornado.web.HTTPError
        400 if the name is malformed, or a non-default account is set without a client
        namespace.  The value is not echoed.
    """
    if "KERNEL_SERVICE_ACCOUNT_NAME" not in client_env:
        return
    account = client_env["KERNEL_SERVICE_ACCOUNT_NAME"]
    if not isinstance(account, str) or not _DNS1123_SUBDOMAIN_PATTERN.fullmatch(account):
        raise web.HTTPError(
            400,
            "KERNEL_SERVICE_ACCOUNT_NAME must be a valid Kubernetes service account name "
            "(lowercase letters, digits, '-' and '.', at most 253 characters)",
        )
    if "KERNEL_NAMESPACE" not in client_env and account != default_service_account:
        raise web.HTTPError(
            400,
            "KERNEL_SERVICE_ACCOUNT_NAME may only be set together with an allowlisted "
            "KERNEL_NAMESPACE. Without a namespace, Enterprise Gateway runs the kernel with "
            "EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME.",
        )


# Spark-submit options that the bundled Spark-on-Kubernetes kernelspecs set themselves, as
# EG-controlled values, before appending the client's KERNEL_EXTRA_SPARK_OPTS.  Because a later
# ``--conf`` wins, a client value could otherwise re-point the driver pod's namespace, service
# account, image or pod template (GHSA-hchm-85c7-pr3j).  Matched per dotted component so that a
# wildcard does not cross a '.' boundary.
_FORBIDDEN_SPARK_CONF_PATTERNS = (
    "spark.kubernetes.namespace",
    "spark.kubernetes.authenticate.*",
    "spark.kubernetes.container.image",
    "spark.kubernetes.driver.container.image",
    "spark.kubernetes.executor.container.image",
    "spark.kubernetes.driver.podtemplatefile",
    "spark.kubernetes.executor.podtemplatefile",
    "spark.kubernetes.driver.secrets.*",
    "spark.kubernetes.executor.secrets.*",
    "spark.kubernetes.driver.secretkeyref.*",
    "spark.kubernetes.executor.secretkeyref.*",
)

# Spark-submit flags that would move the kernel off its intended cluster, mode or identity.
_FORBIDDEN_SPARK_FLAGS = frozenset({"--master", "--deploy-mode", "--proxy-user"})


def _spark_conf_key_matches(key: str, pattern: str) -> bool:
    """Match a dotted Spark conf key against a pattern component-by-component.

    Unlike a plain ``fnmatch`` over the whole key, a ``*`` component matches exactly one
    conf-key component, so ``spark.kubernetes.authenticate.*`` does not spill across dots.
    """
    key_parts = key.split(".")
    pattern_parts = pattern.split(".")
    if pattern_parts[-1] == "*":  # trailing '*' covers one-or-more remaining components
        if len(key_parts) < len(pattern_parts):
            return False
        key_parts = key_parts[: len(pattern_parts) - 1] + ["*"]
    if len(key_parts) != len(pattern_parts):
        return False
    return all(pp in ("*", kp) for pp, kp in zip(pattern_parts, key_parts))


def validate_kernel_extra_spark_opts(
    client_env: Mapping[str, Any], allowed_volume_types: str | Iterable[str] | None
) -> None:
    """Reject ``KERNEL_EXTRA_SPARK_OPTS`` that override EG-controlled Spark settings.

    The bundled Spark-on-Kubernetes kernelspecs append the client's ``KERNEL_EXTRA_SPARK_OPTS``
    to their ``spark-submit`` options after setting the pod namespace, service account, image and
    labels.  A later ``--conf`` would win, so a client value could place the driver pod in any
    namespace (as any service account) or mount the node (GHSA-hchm-85c7-pr3j).  This rejects the
    EG-controlled ``--conf`` keys and the cluster/mode/identity flags, and holds Spark volume
    options to the same type allowlist as ``KERNEL_VOLUMES``.  Options such as driver/executor
    memory and cores stay allowed.

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.
    allowed_volume_types : str | Iterable[str] | None
        Volume types clients may use, as for :func:`validate_kernel_volumes`.

    Raises
    ------
    tornado.web.HTTPError
        400 if the value cannot be parsed or sets a forbidden option.
    """
    value = client_env.get("KERNEL_EXTRA_SPARK_OPTS")
    if not value:
        return
    try:
        tokens = shlex.split(str(value))
    except ValueError as err:
        raise web.HTTPError(
            400, "KERNEL_EXTRA_SPARK_OPTS could not be parsed as shell options"
        ) from err

    allowed_types_lower = {t.lower() for t in split_list_setting(allowed_volume_types)}
    conf_values: list[str] = []
    index = 0
    while index < len(tokens):
        arg = tokens[index]
        if arg in _FORBIDDEN_SPARK_FLAGS:
            raise web.HTTPError(400, f"KERNEL_EXTRA_SPARK_OPTS may not set '{arg}'")
        if arg == "--conf" and index + 1 < len(tokens):
            conf_values.append(tokens[index + 1])
            index += 2
            continue
        if arg.startswith("--conf="):
            conf_values.append(arg[len("--conf=") :])
        index += 1

    for conf in conf_values:
        key = conf.split("=", 1)[0].strip()
        lowered = key.lower()
        if any(
            _spark_conf_key_matches(lowered, pattern) for pattern in _FORBIDDEN_SPARK_CONF_PATTERNS
        ):
            raise web.HTTPError(
                400,
                f"KERNEL_EXTRA_SPARK_OPTS may not set the Spark configuration key '{key}'; it is "
                "managed by Enterprise Gateway",
            )
        parts = lowered.split(".")
        if "volumes" in parts:
            type_index = parts.index("volumes") + 1
            vol_type = parts[type_index] if type_index < len(parts) else ""
            if "*" not in allowed_types_lower and vol_type not in allowed_types_lower:
                original_type = key.split(".")[type_index] if type_index < len(parts) else ""
                raise web.HTTPError(
                    400,
                    f"KERNEL_EXTRA_SPARK_OPTS requests a Spark volume of type '{original_type}', "
                    "which is not allowed. See EG_ALLOWED_KERNEL_VOLUME_TYPES.",
                )


def validate_kernel_volumes(
    client_env: Mapping[str, Any], allowed_volume_types: str | Iterable[str] | None
) -> None:
    """Reject client-supplied volumes whose type the operator has not allowed.

    ``KERNEL_VOLUMES`` and ``KERNEL_VOLUME_MOUNTS`` are rendered into the kernel pod (or
    SparkApplication) as-is.  A volume type such as ``hostPath`` or ``gitRepo`` gives the
    kernel access to the node it runs on, so each volume must use exactly one source whose
    type is in ``allowed_volume_types`` (GHSA-hchm-85c7-pr3j).  Types are matched exactly,
    so case variants such as ``HostPath`` are rejected.

    Parameters
    ----------
    client_env : Mapping[str, Any]
        Environment values supplied by the client for this kernel.
    allowed_volume_types : str | Iterable[str] | None
        Volume types clients may use, as a list or comma-separated string.  ``*`` allows
        any type; an empty value allows none.

    Raises
    ------
    tornado.web.HTTPError
        400 if a value is not a YAML list of mappings, a volume is malformed or uses a type
        that is not allowed, or a volume mount has an unsupported field.  The message names
        the volume and type only when they are well-formed identifiers.
    """
    allowed = set(split_list_setting(allowed_volume_types))

    if "KERNEL_VOLUMES" in client_env:
        for index, volume in enumerate(_load_mapping_list("KERNEL_VOLUMES", client_env)):
            name = volume.get("name")
            if not isinstance(name, str) or not _DNS1123_LABEL_PATTERN.fullmatch(name):
                raise web.HTTPError(
                    400,
                    f"KERNEL_VOLUMES entry {index} must have a 'name' that is a valid Kubernetes "
                    "volume name (lowercase letters, digits and '-', at most 63 characters)",
                )
            sources = [key for key in volume if key != "name"]
            if len(sources) != 1:
                raise web.HTTPError(
                    400, f"KERNEL_VOLUMES volume '{name}' must define exactly one volume source"
                )
            volume_type = sources[0]
            if "*" not in allowed and volume_type not in allowed:
                raise web.HTTPError(
                    400,
                    f"KERNEL_VOLUMES volume '{name}' uses volume type {_quoted(volume_type)}, "
                    f"which is not allowed. Allowed types: {', '.join(sorted(allowed)) or 'none'}. "
                    "To permit it, ask your Enterprise Gateway operator to add it to "
                    "EG_ALLOWED_KERNEL_VOLUME_TYPES (or to allowed_volume_types in the "
                    "kernelspec's process-proxy config).",
                )

    if "KERNEL_VOLUME_MOUNTS" in client_env:
        for index, mount in enumerate(_load_mapping_list("KERNEL_VOLUME_MOUNTS", client_env)):
            for field in mount:
                if field not in VOLUME_MOUNT_FIELDS:
                    raise web.HTTPError(
                        400,
                        f"KERNEL_VOLUME_MOUNTS entry {index} has unsupported field "
                        f"{_quoted(field)}. Supported fields: "
                        f"{', '.join(sorted(VOLUME_MOUNT_FIELDS))}.",
                    )


def _load_mapping_list(name: str, client_env: Mapping[str, Any]) -> list[dict]:
    """Parse ``client_env[name]`` the way the kernel launchers do: a YAML list of mappings."""
    value = client_env[name]
    try:
        parsed = yaml.safe_load(value) if isinstance(value, str) else None
    except yaml.YAMLError:
        parsed = None
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise web.HTTPError(400, f"{name} must be a YAML list of mappings")
    return parsed


def _quoted(identifier: Any) -> str:
    """Quote ``identifier`` for an error message, or describe it if it is not safe to echo."""
    if isinstance(identifier, str) and _FIELD_NAME_PATTERN.fullmatch(identifier):
        return f"'{identifier}'"
    return "(unprintable name)"


def get_subject_class():
    """
    Returns the appropriate Subject class based on the kubernetes client version.

    In kubernetes-client, V1Subject was renamed to RbacV1Subject.
    This function returns the appropriate class based on the installed version.
    """
    # Check if V1Subject exists in the client
    if hasattr(client, 'V1Subject'):
        logging.debug(
            "Using client.V1Subject for Kubernetes client version: %s", kubernetes.__version__
        )
        return client.V1Subject
    # Fall back to RbacV1Subject for older versions
    logging.debug(
        "Using client.RbacV1Subject for Kubernetes client version: %s", kubernetes.__version__
    )
    return client.RbacV1Subject


class KubernetesProcessProxy(ContainerProcessProxy):
    """
    Kernel lifecycle management for Kubernetes kernels.
    """

    # Identifies the kind of object being managed by this process proxy.
    # For these values we will prefer the values found in the 'kind' field
    # of the object's metadata.  This attribute is strictly used to provide
    # context to log messages.
    object_kind = "Pod"

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)

        self.kernel_pod_name = None
        self.kernel_namespace = None
        self.delete_kernel_namespace = False

    @classmethod
    def validate_client_env(
        cls,
        client_env: Mapping[str, Any],
        proxy_config: Mapping[str, Any],
        kernel_manager: RemoteKernelManager,
    ) -> None:
        """Rejects client-supplied Kubernetes resources the operator has not allowed."""
        super().validate_client_env(client_env, proxy_config, kernel_manager)
        allowed_volume_types = proxy_config_override(
            proxy_config, "allowed_volume_types", kernel_manager.allowed_kernel_volume_types
        )
        validate_kernel_volumes(client_env, allowed_volume_types)
        validate_kernel_extra_spark_opts(client_env, allowed_volume_types)
        validate_kernel_namespace(
            client_env,
            proxy_config_override(
                proxy_config, "allowed_namespaces", kernel_manager.allowed_kernel_namespaces
            ),
            enterprise_gateway_namespace,
            _managed_kernel_namespaces,
        )
        reject_client_namespace_owned_by_eg(client_env)
        validate_kernel_service_account(client_env, default_kernel_service_account_name)

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> KubernetesProcessProxy:
        """Launches the specified process within a Kubernetes environment."""
        # Set env before superclass call, so we can see these in the debug output

        # Kubernetes relies on internal env variables to determine its configuration.  When
        # running within a K8s cluster, these start with KUBERNETES_SERVICE, otherwise look
        # for envs prefixed with KUBECONFIG.
        for key in os.environ:
            if key.startswith("KUBECONFIG") or key.startswith("KUBERNETES_SERVICE"):
                kwargs["env"][key] = os.environ[key]

        # Determine pod name and namespace - creating the latter if necessary
        self.kernel_pod_name = self._determine_kernel_pod_name(**kwargs)
        self.kernel_namespace = self._determine_kernel_namespace(**kwargs)

        await super().launch_process(kernel_cmd, **kwargs)
        return self

    def get_initial_states(self) -> set:
        """Return list of states in lowercase indicating container is starting (includes running)."""
        return ["pending", "running"]

    def get_error_states(self) -> set:
        """Return list of states in lowercase indicating container failed ."""
        return ["failed"]

    def get_container_status(self, iteration: int | None) -> str:
        """Return current container state."""
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.
        pod_status = ""
        kernel_label_selector = "kernel_id=" + self.kernel_id + ",component=kernel"
        ret = client.CoreV1Api().list_namespaced_pod(
            namespace=self.kernel_namespace, label_selector=kernel_label_selector
        )
        if ret and ret.items:
            pod_info = ret.items[0]
            self.container_name = pod_info.metadata.name
            if pod_info.status:
                pod_status = pod_info.status.phase.lower()
                if pod_status == "running" and not self.assigned_host:
                    # Pod is running, capture IP
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_host = self.container_name
                    self.assigned_node_ip = pod_info.status.host_ip

        if iteration:  # only log if iteration is not None (otherwise poll() is too noisy)
            self.log.debug(
                f"{iteration}: Waiting to connect to k8s {self.object_kind.lower()} in "
                f"namespace '{self.kernel_namespace}'. Name: '{self.container_name}', "
                f"Status: '{pod_status}', Pod IP: '{self.assigned_ip}', KernelID: '{self.kernel_id}'"
            )

        return pod_status

    def delete_managed_object(self, termination_stati: list[str]) -> bool:
        """Deletes the object managed by this process-proxy

        A return value of True indicates the object is considered deleted,
        otherwise a False or None value is returned.

        Note: the caller is responsible for handling exceptions.
        """
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy="Background")

        # Deleting a Pod will return a v1.Pod if found and its status will be a PodStatus containing
        # a phase string property
        # https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.21/#podstatus-v1-core
        v1_pod = client.CoreV1Api().delete_namespaced_pod(
            namespace=self.kernel_namespace, body=body, name=self.container_name
        )
        status = None
        if v1_pod and v1_pod.status:
            status = v1_pod.status.phase

        result = status in termination_stati

        return result

    def terminate_container_resources(self) -> bool | None:
        """Terminate any artifacts created on behalf of the container's lifetime."""
        # Kubernetes objects don't go away on their own - so we need to tear down the namespace
        # and/or pod associated with the kernel.  We'll always target the pod first so that shutdown
        # is perceived as happening more rapidly.  Then, if we created the namespace, and we're not
        # in the process of restarting the kernel, we'll delete the namespace.
        # After deleting the pod we check the container status, rather than the status returned
        # from the pod deletion API, since it's not necessarily reflective of the actual status.

        result = False
        termination_stati = ["Succeeded", "Failed", "Terminating", "Success"]

        # Delete the managed object then, if applicable, the namespace
        object_type = self.object_kind
        try:
            result = self.delete_managed_object(termination_stati)
            if not result:
                # If the status indicates the object is not terminated, capture its current status.
                # If None, update the result to True, else issue warning that it is not YET deleted
                # since we still have the hard termination sequence to occur.
                cur_status = self.get_container_status(None)
                if cur_status is None:
                    result = True
                else:
                    self.log.warning(
                        f"{object_type} '{self.kernel_namespace}.{self.container_name}'"
                        f" is not yet deleted.  Current status is '{cur_status}'."
                    )

            if self.delete_kernel_namespace and not self.kernel_manager.restarting:
                object_type = "Namespace"
                # Status is a return value for calls that don't return other objects.
                # https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.21/#status-v1-meta
                body = client.V1DeleteOptions(
                    grace_period_seconds=0, propagation_policy="Background"
                )
                v1_status = client.CoreV1Api().delete_namespace(
                    name=self.kernel_namespace, body=body
                )
                _managed_kernel_namespaces.discard(self.kernel_namespace)
                status = None
                if v1_status:
                    status = v1_status.status

                if status and any(s in status for s in termination_stati):
                    result = True

                if not result:
                    self.log.warning(
                        f"Namespace {self.kernel_namespace} is not yet deleted.  "
                        f"Current status is '{status}'."
                    )

        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                result = True  # okay if it's not found
            else:
                self.log.warning(f"Error occurred deleting {object_type.lower()}: {err}")

        if result:
            self.log.debug(
                f"KubernetesProcessProxy.terminate_container_resources, "
                f"{self.object_kind}: {self.kernel_namespace}.{self.container_name}, "
                f"kernel ID: {self.kernel_id} has been terminated."
            )
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning(
                "KubernetesProcessProxy.terminate_container_resources, "
                f"{self.object_kind}: {self.kernel_namespace}.{self.container_name}, "
                f"kernel ID: {self.kernel_id} has not been terminated."
            )

        # Check if there's a kernel pod template file for this kernel and silently delete it.
        kpt_file = kpt_dir + "/kpt_" + self.kernel_id
        try:
            os.remove(kpt_file)
        except OSError:
            pass

        return result

    def _safe_template_substitute(self, template_str: str, variables: dict) -> str | None:
        """
        Safely substitute variables in Jinja2-style template syntax.
        Only supports simple variable substitution: {{ variable_name }}
        Logs missing variables and returns None if any are missing.
        """
        # Pattern to match {{ variable_name }} with optional whitespace
        # Explicitly exclude variables starting with underscore to prevent magic method attacks
        pattern = r'\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}'
        missing_vars = []

        def replace_var(match):
            var_name = match.group(1)
            if var_name in variables:
                return str(variables[var_name])
            else:
                missing_vars.append(var_name)
                return match.group(0)  # Keep original placeholder

        result = re.sub(pattern, replace_var, template_str)

        # Check if there are any remaining {{ }} patterns that didn't match our simple pattern
        # This catches malicious templates like {{ foo.__class__ }} or {{ 1+1 }}
        if '{{' in result and '}}' in result:
            self.log.warning(
                "Invalid template syntax detected in KERNEL_POD_NAME: contains unsupported expressions"
            )
            return None

        # Log missing variables and return None if any are missing
        if missing_vars:
            self.log.warning(f"Template variables not found in KERNEL_POD_NAME: {missing_vars}")
            return None  # Signal caller to use default

        return result

    def _determine_kernel_pod_name(self, **kwargs: dict[str, Any] | None) -> str:
        pod_name = kwargs["env"].get("KERNEL_POD_NAME")

        if pod_name is None:
            pod_name = KernelSessionManager.get_kernel_username(**kwargs) + "-" + self.kernel_id
        else:
            self.log.debug(f"Processing KERNEL_POD_NAME based on env var => {pod_name}")
            if "{{" in pod_name and "}}" in pod_name:
                self.log.debug("Processing KERNEL_POD_NAME template variables")
                keywords = {}
                for name, value in kwargs["env"].items():
                    if name.startswith("KERNEL_"):
                        keywords[name.lower()] = value
                keywords["kernel_id"] = self.kernel_id

                # Safe template substitution with fallback
                substituted = self._safe_template_substitute(pod_name, keywords)
                if substituted is None:
                    # Fall back to default if template variables are missing
                    self.log.warning(
                        "Falling back to default pod name due to missing template variables"
                    )
                    pod_name = (
                        KernelSessionManager.get_kernel_username(**kwargs) + "-" + self.kernel_id
                    )
                else:
                    pod_name = substituted

        # Rewrite pod_name to be compatible with DNS name convention
        # And put back into env since kernel needs this
        pod_name = re.sub("[^0-9a-z]+", "-", pod_name.lower())
        while pod_name.startswith("-"):
            pod_name = pod_name[1:]
        while pod_name.endswith("-"):
            pod_name = pod_name[:-1]
        kwargs["env"]["KERNEL_POD_NAME"] = pod_name

        return pod_name

    def _determine_kernel_namespace(self, **kwargs: dict[str, Any] | None) -> str:
        # Since we need the service account name regardless of whether we're creating the namespace or not,
        # get it now.
        service_account_name = KubernetesProcessProxy._determine_kernel_service_account_name(
            **kwargs
        )

        # If KERNEL_NAMESPACE was provided, then we assume it already exists.  If not provided, then we'll
        # create the namespace and record that we'll want to delete it as well.
        namespace = kwargs["env"].get("KERNEL_NAMESPACE")
        if namespace is None:
            # check if share gateway namespace is configured...
            if share_gateway_namespace:  # if so, set to EG namespace
                namespace = enterprise_gateway_namespace
                self.log.warning(
                    "Shared namespace has been configured.  All kernels will reside in EG namespace: {}".format(
                        namespace
                    )
                )
            else:
                namespace = self._create_kernel_namespace(service_account_name)
            kwargs["env"]["KERNEL_NAMESPACE"] = namespace  # record in env since kernel needs this
        else:
            self.log.info(f"KERNEL_NAMESPACE provided by client: {namespace}")

        return namespace

    @staticmethod
    def _determine_kernel_service_account_name(**kwargs: dict[str, Any] | None) -> str:
        # Check if an account name was provided.  If not, set to the default name (which can be set
        # from the EG env as well).  Finally, ensure the env value is set.
        service_account_name = kwargs["env"].get(
            "KERNEL_SERVICE_ACCOUNT_NAME", default_kernel_service_account_name
        )
        kwargs["env"]["KERNEL_SERVICE_ACCOUNT_NAME"] = service_account_name
        return service_account_name

    def _create_kernel_namespace(self, service_account_name: str) -> str:
        # Creates the namespace for the kernel based on the kernel username and kernel id.  Since we're creating
        # the namespace, we'll also note that it should be deleted as well.  In addition, the kernel pod may need
        # to list/create other pods (true for spark-on-k8s), so we'll also create a RoleBinding associated with
        # the namespace's default ServiceAccount.  Since this is always done when creating a namespace, we can
        # delete the RoleBinding when deleting the namespace (no need to record that via another member variable).

        namespace = self.kernel_pod_name

        # create the namespace ...
        labels = {
            "app": "enterprise-gateway",
            "component": "kernel",
            "kernel_id": self.kernel_id,
            **kernel_namespace_pod_security_labels,
        }
        namespace_metadata = client.V1ObjectMeta(name=namespace, labels=labels)
        body = client.V1Namespace(metadata=namespace_metadata)

        # create the namespace
        try:
            client.CoreV1Api().create_namespace(body=body)
            self.delete_kernel_namespace = True
            _managed_kernel_namespaces.add(namespace)
            self.log.info(f"Created kernel namespace: {namespace}")

            # Now create a RoleBinding for this namespace for the default ServiceAccount.  We'll reference
            # the ClusterRole, but that will only be applied for this namespace.  This prevents the need for
            # creating a role each time.
            self._create_role_binding(namespace, service_account_name)
        except Exception as err:
            if (
                isinstance(err, client.rest.ApiException)
                and err.status == 409
                and self.kernel_manager.restarting
            ):
                self.delete_kernel_namespace = (
                    True  # okay if ns already exists and restarting, still mark for delete
                )
                _managed_kernel_namespaces.add(namespace)
                self.log.info(f"Re-using kernel namespace: {namespace}")
            else:
                if self.delete_kernel_namespace:
                    reason = "Error occurred creating role binding for namespace '{}': {}".format(
                        namespace, err
                    )
                    # delete the namespace since we'll be using the EG namespace...
                    body = client.V1DeleteOptions(
                        grace_period_seconds=0, propagation_policy="Background"
                    )
                    client.CoreV1Api().delete_namespace(name=namespace, body=body)
                    _managed_kernel_namespaces.discard(namespace)
                    self.log.warning(f"Deleted kernel namespace: {namespace}")
                else:
                    reason = f"Error occurred creating namespace '{namespace}': {err}"
                self.log_and_raise(http_status_code=500, reason=reason)

        return namespace

    def _create_role_binding(self, namespace: str, service_account_name: str) -> None:
        # Creates RoleBinding instance for the given namespace.  The role used will be the ClusterRole named by
        # EG_KERNEL_CLUSTER_ROLE.
        # Note that roles referenced in RoleBindings are scoped to the namespace so re-using the cluster role prevents
        # the need for creating a new role with each kernel.
        # The ClusterRole will be bound to the kernel service user identified by KERNEL_SERVICE_ACCOUNT_NAME then
        # EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME, respectively.
        # We will not use a try/except clause here since _create_kernel_namespace will handle exceptions.

        role_binding_name = kernel_cluster_role  # use same name for binding as cluster role
        labels = {"app": "enterprise-gateway", "component": "kernel", "kernel_id": self.kernel_id}
        binding_metadata = client.V1ObjectMeta(name=role_binding_name, labels=labels)
        binding_role_ref = client.V1RoleRef(
            api_group="", kind="ClusterRole", name=kernel_cluster_role
        )
        # Use the appropriate Subject class based on kubernetes client version
        SubjectClass = get_subject_class()
        binding_subjects = SubjectClass(
            api_group="", kind="ServiceAccount", name=service_account_name, namespace=namespace
        )

        body = client.V1RoleBinding(
            kind="RoleBinding",
            metadata=binding_metadata,
            role_ref=binding_role_ref,
            subjects=[binding_subjects],
        )

        client.RbacAuthorizationV1Api().create_namespaced_role_binding(
            namespace=namespace, body=body
        )
        self.log.info(
            "Created kernel role-binding '{}' in namespace: {} for service account: {}".format(
                role_binding_name, namespace, service_account_name
            )
        )

    def get_process_info(self) -> dict[str, Any]:
        """Captures the base information necessary for kernel persistence relative to kubernetes."""
        process_info = super().get_process_info()
        process_info.update(
            {"kernel_ns": self.kernel_namespace, "delete_ns": self.delete_kernel_namespace}
        )
        return process_info

    def load_process_info(self, process_info: dict[str, Any]) -> None:
        """Loads the base information necessary for kernel persistence relative to kubernetes."""
        super().load_process_info(process_info)
        self.kernel_namespace = process_info["kernel_ns"]
        self.delete_kernel_namespace = process_info["delete_ns"]
        if self.delete_kernel_namespace:  # restored kernel owns the namespace EG created for it
            _managed_kernel_namespaces.add(self.kernel_namespace)
