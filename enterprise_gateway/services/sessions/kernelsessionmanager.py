"""Session manager that keeps all its metadata in memory."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import getpass
import json
import os
import threading

import requests
from jupyter_core.paths import jupyter_data_dir
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from traitlets import Bool, CaselessStrEnum, Unicode, default
from traitlets.config.configurable import LoggingConfigurable

kernels_lock = threading.Lock()

# These will be located under the `persistence_root` and exist
# to make integration with ContentsManager implementations easier.
KERNEL_SESSIONS_DIR_NAME = "kernel_sessions"


class KernelSessionManager(LoggingConfigurable):
    """
    KernelSessionManager is used to save and load kernel sessions from persistent storage.

    KernelSessionManager provides the basis for an HA solution.  It loads the complete set of persisted kernel
    sessions during construction.  Following construction the parent object calls start_sessions to allow
    Enterprise Gateway to validate that all loaded sessions are still valid.  Those that it cannot 'revive'
    are marked for deletion and the in-memory dictionary is updated - and the entire collection is written
    to store (file or database).

    As kernels are created and destroyed, the KernelSessionManager is called upon to keep kernel session
    state consistent.

    NOTE: This class is essentially an abstract base class that requires its `load_sessions` and `save_sessions`
    have implementations in subclasses.  abc.MetaABC is not used due to conflicts with derivation of
    LoggingConfigurable - which seemed more important.
    """

    # Session Persistence
    session_persistence_env = "EG_KERNEL_SESSION_PERSISTENCE"
    session_persistence_default_value = False
    enable_persistence = Bool(
        session_persistence_default_value,
        config=True,
        help="""Enable kernel session persistence (True or False). Default = False
(EG_KERNEL_SESSION_PERSISTENCE env var)""",
    )

    @default("enable_persistence")
    def _session_persistence_default(self) -> bool:
        return bool(
            os.getenv(
                self.session_persistence_env, str(self.session_persistence_default_value)
            ).lower()
            == "true"
        )

    # Persistence root
    persistence_root_env = "EG_PERSISTENCE_ROOT"
    persistence_root = Unicode(
        config=True,
        help="""Identifies the root 'directory' under which the 'kernel_sessions' node will
reside.  This directory should exist.  (EG_PERSISTENCE_ROOT env var)""",
    )

    @default("persistence_root")
    def _persistence_root_default(self) -> str:
        return os.getenv(self.persistence_root_env, "/")

    def __init__(self, kernel_manager: RemoteMappingKernelManager, **kwargs):  # noqa: F821
        """Initialize the manager."""
        super().__init__(**kwargs)
        self.kernel_manager = kernel_manager
        self._sessions = {}
        self._sessionsByUser = {}

    def create_session(self, kernel_id: str, **kwargs) -> None:
        """
        Creates a session associated with this kernel.

        All items associated with the active kernel's state are saved.

        Parameters
        ----------
        kernel_id : str
            The uuid string associated with the active kernel

        **kwargs : optional
            Information used for the launch of the kernel

        """
        km = self.kernel_manager.get_kernel(kernel_id)

        # Compose the kernel_session entry
        kernel_session = {}
        kernel_session["kernel_id"] = kernel_id
        kernel_session["username"] = KernelSessionManager.get_kernel_username(**kwargs)
        kernel_session["kernel_name"] = km.kernel_name

        # Build the inner dictionaries: connection_info, process_proxy and add to kernel_session
        kernel_session["connection_info"] = km.get_connection_info()
        kernel_session["launch_args"] = kwargs.copy()
        kernel_session["process_info"] = (
            km.process_proxy.get_process_info() if km.process_proxy else {}
        )
        self._save_session(kernel_id, kernel_session)

    def refresh_session(self, kernel_id: str) -> None:
        """
        Refreshes the session from its persisted state. Called on kernel restarts.
        """
        self.log.debug(f"Refreshing kernel session for id: {kernel_id}")
        km = self.kernel_manager.get_kernel(kernel_id)

        # Compose the kernel_session entry
        kernel_session = self._sessions[kernel_id]

        # Build the inner dictionaries: connection_info, process_proxy and add to kernel_session
        kernel_session["connection_info"] = km.get_connection_info()
        kernel_session["process_info"] = (
            km.process_proxy.get_process_info() if km.process_proxy else {}
        )
        self._save_session(kernel_id, kernel_session)

    def _save_session(self, kernel_id: str, kernel_session: dict) -> None:
        # Write/commit the addition, update dictionary
        kernels_lock.acquire()
        try:
            self._sessions[kernel_id] = kernel_session
            username = kernel_session["username"]
            if username not in self._sessionsByUser:
                self._sessionsByUser[username] = []
                self._sessionsByUser[username].append(kernel_id)
            else:
                # Only append if not there yet (e.g. restarts will be there already)
                if kernel_id not in self._sessionsByUser[username]:
                    self._sessionsByUser[username].append(kernel_id)
            self.save_session(kernel_id)  # persist changes in file/DB etc.
        finally:
            kernels_lock.release()

    def start_session(self, kernel_id: str) -> bool | None:
        """Start a session for a given kernel."""
        kernel_session = self._sessions.get(kernel_id, None)
        if kernel_session is not None:
            return self._start_session(kernel_session)
        return None

    def start_sessions(self) -> None:
        """
        Attempt to start persisted sessions.

        Determines if session startup was successful.  If unsuccessful, the session is removed
        from persistent storage.
        """
        if self.enable_persistence:
            self.load_sessions()
            sessions_to_remove = []
            for kernel_id, kernel_session in self._sessions.items():
                self.log.info(
                    "Attempting startup of persisted kernel session for id: %s..." % kernel_id
                )
                if self._start_session(kernel_session):
                    self.log.info(
                        "Startup of persisted kernel session for id '{}' was successful.  Client should "
                        "reconnect kernel.".format(kernel_id)
                    )
                else:
                    sessions_to_remove.append(kernel_id)
                    self.log.warning(
                        "Startup of persisted kernel session for id '{}' was not successful.  Check if "
                        "client is still active and restart kernel.".format(kernel_id)
                    )

            self._delete_sessions(sessions_to_remove)

    def _start_session(self, kernel_session: dict) -> bool:
        # Attempt to start kernel from persisted state.  if started, record kernel_session in dictionary
        # else delete session
        kernel_id = kernel_session["kernel_id"]
        kernel_started = self.kernel_manager.start_kernel_from_session(
            kernel_id=kernel_id,
            kernel_name=kernel_session["kernel_name"],
            connection_info=kernel_session["connection_info"],
            process_info=kernel_session["process_info"],
            launch_args=kernel_session["launch_args"],
        )
        if not kernel_started:
            return False

        return True

    def delete_session(self, kernel_id: str) -> None:
        """
        Removes saved session associated with kernel_id from dictionary and persisted storage.
        """
        self._delete_sessions([kernel_id])

        if self.enable_persistence:
            self.log.info("Deleted persisted kernel session for id: %s" % kernel_id)

    def _delete_sessions(self, kernel_ids: list[str]) -> None:
        # Remove unstarted sessions and rewrite
        kernels_lock.acquire()
        try:
            for kernel_id in kernel_ids:
                # Prior to removing session, update the per User list
                kernel_session = self._sessions.get(kernel_id, None)
                if kernel_session is not None:
                    username = kernel_session["username"]
                    if (
                        username in self._sessionsByUser
                        and kernel_id in self._sessionsByUser[username]
                    ):
                        self._sessionsByUser[username].remove(kernel_id)
                    self._sessions.pop(kernel_id, None)

            self.delete_sessions(kernel_ids)
        finally:
            kernels_lock.release()

    @staticmethod
    def pre_save_transformation(session: dict) -> dict:
        """Handle a pre_save for a session."""
        kernel_id = next(iter(session.keys()))
        session_info = session[kernel_id]
        if session_info.get("connection_info"):
            info = session_info["connection_info"]
            key = info.get("key")
            if key:
                info["key"] = key.decode("utf8")

        return session

    @staticmethod
    def post_load_transformation(session: dict) -> dict:
        """Handle a post_load for a session."""
        kernel_id = next(iter(session.keys()))
        session_info = session[kernel_id]
        if session_info.get("connection_info"):
            info = session_info["connection_info"]
            key = info.get("key")
            if key:
                info["key"] = key.encode("utf8")

        return session

    # abstractmethod
    def load_sessions(self) -> None:
        """
        Load and initialize _sessions member from persistent storage.  This method is called from start_sessions().
        """
        msg = "KernelSessionManager.load_sessions() requires an implementation!"
        raise NotImplementedError(msg)

    # abstractmethod
    def load_session(self, kernel_id: str) -> None:
        """
        Load and initialize _sessions member from persistent storage for a single kernel.  This method is called from
        refresh_sessions().
        """
        msg = "KernelSessionManager.load_session() requires an implementation!"
        raise NotImplementedError(msg)

    # abstractmethod
    def delete_sessions(self, kernel_ids: list[str]) -> None:
        """
        Delete the sessions in persistent storage.  Caller is responsible for synchronizing call.
        """
        msg = "KernelSessionManager.delete_sessions(kernel_ids) requires an implementation!"
        raise NotImplementedError(msg)

    def save_session(self, kernel_id: str) -> None:
        """
        Saves the sessions dictionary to persistent store.  Caller is responsible for synchronizing call.
        """
        msg = "KernelSessionManager.save_session(kernel_id) requires an implementation!"
        raise NotImplementedError(msg)

    def active_sessions(self, username: str) -> int:
        """
        Returns the number of active sessions for the given username.

        Parameters
        ----------
        username : str
            The username associated with the active session

        Returns
        -------
        int corresponding to the number of active sessions associated with given user
        """
        if username in self._sessionsByUser:
            return len(self._sessionsByUser[username])
        return 0

    @staticmethod
    def get_kernel_username(**kwargs) -> str:
        """
        Returns the kernel's logical username from env dict.

        Checks the process env for KERNEL_USERNAME.  If set, that value is returned, else KERNEL_USERNAME is
        initialized to the current user and that value is returned.

        Parameters
        ----------
        kwargs : dict from which request env is accessed.

        Returns
        -------
        str indicating kernel username
        """
        # Get the env
        env_dict = kwargs.get("env", {})

        # Ensure KERNEL_USERNAME is set
        kernel_username = env_dict.get("KERNEL_USERNAME")
        if kernel_username is None:
            kernel_username = getpass.getuser()
            env_dict["KERNEL_USERNAME"] = kernel_username

        return kernel_username


class FileKernelSessionManager(KernelSessionManager):
    """
    Performs kernel session persistence operations against the file `sessions.json` located in the kernel_sessions
    directory in the directory pointed to by the persistence_root parameter (default JUPYTER_DATA_DIR).
    """

    # Change the default to Jupyter Data Dir.
    @default("persistence_root")
    def _persistence_root_default(self) -> str:
        return os.getenv(self.persistence_root_env, jupyter_data_dir())

    def __init__(self, kernel_manager: RemoteMappingKernelManager, **kwargs):  # noqa: F821
        """Initialize the manager."""
        super().__init__(kernel_manager, **kwargs)
        if self.enable_persistence:
            self.log.info(f"Kernel session persistence location: {self._get_sessions_loc()}")

    def delete_sessions(self, kernel_ids: list[str]) -> None:
        """Delete the sessions for a list of kernels."""
        if self.enable_persistence:
            for kernel_id in kernel_ids:
                kernel_file_name = "".join([kernel_id, ".json"])
                kernel_session_file_path = os.path.join(self._get_sessions_loc(), kernel_file_name)
                if os.path.exists(kernel_session_file_path):
                    os.remove(kernel_session_file_path)

    def save_session(self, kernel_id: str) -> None:
        """Save the session for a kernel."""
        if self.enable_persistence and kernel_id is not None:
            kernel_file_name = "".join([kernel_id, ".json"])
            kernel_session_file_path = os.path.join(self._get_sessions_loc(), kernel_file_name)
            temp_session = {}
            temp_session[kernel_id] = self._sessions[kernel_id]
            with open(kernel_session_file_path, "w") as fp:
                json.dump(KernelSessionManager.pre_save_transformation(temp_session), fp)
                fp.close()

    def load_sessions(self) -> None:
        """Load the sessions."""
        if self.enable_persistence:
            kernel_session_files = [
                json_files
                for json_files in os.listdir(self._get_sessions_loc())
                if json_files.endswith(".json")
            ]
            for kernel_session_file in kernel_session_files:
                self._load_session_from_file(kernel_session_file)

    def load_session(self, kernel_id: str) -> None:
        """Load the session for a kernel."""
        if self.enable_persistence and kernel_id is not None:
            kernel_session_file = "".join([kernel_id, ".json"])
            self._load_session_from_file(kernel_session_file)

    def _load_session_from_file(self, file_name: str) -> None:
        kernel_session_file_path = os.path.join(self._get_sessions_loc(), file_name)
        if os.path.exists(kernel_session_file_path):
            self.log.debug(f"Loading saved session(s) from {kernel_session_file_path}")
            with open(kernel_session_file_path) as fp:
                self._sessions.update(KernelSessionManager.post_load_transformation(json.load(fp)))
                fp.close()

    def _get_sessions_loc(self) -> str:
        path = os.path.join(self.persistence_root, KERNEL_SESSIONS_DIR_NAME)
        if not os.path.exists(path):
            os.makedirs(path, 0o755)
        return path


class WebhookKernelSessionManager(KernelSessionManager):
    """
    Performs kernel session persistence operations against URL provided (EG_WEBHOOK_URL). The URL must have 4 endpoints
    associated with it. 1 delete endpoint that takes a list of kernel ids in
    the body, 1 post endpoint that takes kernels id as a
    url param and the kernel session as the body, 1 get endpoint that returns
    all kernel sessions, and 1 get endpoint that returns
    a specific kernel session based on kernel id as url param.
    """

    # Webhook URL
    webhook_url_env = "EG_WEBHOOK_URL"
    webhook_url = Unicode(
        config=True,
        allow_none=True,
        help="""URL endpoint for webhook kernel session manager""",
    )

    @default("webhook_url")
    def _webhook_url_default(self) -> str | None:
        return os.getenv(self.webhook_url_env, None)

    # Webhook Username
    webhook_username_env = "EG_WEBHOOK_USERNAME"
    webhook_username = Unicode(
        config=True,
        allow_none=True,
        help="""Username for webhook kernel session manager API auth""",
    )

    @default("webhook_username")
    def _webhook_username_default(self) -> str | None:
        return os.getenv(self.webhook_username_env, None)

    # Webhook Password
    webhook_password_env = "EG_WEBHOOK_PASSWORD"  # noqa
    webhook_password = Unicode(
        config=True,
        allow_none=True,
        help="""Password for webhook kernel session manager API auth""",
    )

    @default("webhook_password")
    def _webhook_password_default(self) -> str | None:
        return os.getenv(self.webhook_password_env, None)

    # Auth Type
    auth_type_env = "EG_AUTH_TYPE"
    auth_type = CaselessStrEnum(
        config=True,
        allow_none=True,
        values=["basic", "digest"],
        help="""Authentication type for webhook kernel session manager API. Either basic, digest or None""",
    )

    @default("auth_type")
    def _auth_type_default(self) -> str | None:
        return os.getenv(self.auth_type_env, None)

    def __init__(self, kernel_manager: RemoteMappingKernelManager, **kwargs):  # noqa: F821
        """Initialize the manager."""
        super().__init__(kernel_manager, **kwargs)
        if self.enable_persistence:
            self.log.info("Webhook kernel session persistence activated")
            self.auth = ""
            if self.auth_type:
                if self.webhook_username and self.webhook_password:
                    if self.auth_type == "basic":
                        self.auth = HTTPBasicAuth(self.webhook_username, self.webhook_password)
                    elif self.auth_type == "digest":
                        self.auth = HTTPDigestAuth(self.webhook_username, self.webhook_password)
                    elif self.auth_type is None:
                        self.auth = ""
                    else:
                        self.log.error("No such option for auth_type/EG_AUTH_TYPE")
                else:
                    self.log.error("Username and/or password aren't set")

    def delete_sessions(self, kernel_ids: list[str]) -> None:
        """
        Deletes kernel sessions from database

        :param list of strings kernel_ids: A list of kernel ids
        """
        if self.enable_persistence:
            response = requests.delete(
                self.webhook_url, auth=self.auth, json=kernel_ids, timeout=60
            )
            self.log.debug(f"Webhook kernel session deleting: {kernel_ids}")
            if response.status_code != 204:
                self.log.error(response.raise_for_status())

    def save_session(self, kernel_id: str) -> None:
        """
        Saves kernel session to database

        :param string kernel_id: A kernel id
        """
        if self.enable_persistence and kernel_id is not None:
            temp_session = {}
            temp_session[kernel_id] = self._sessions[kernel_id]
            body = KernelSessionManager.pre_save_transformation(temp_session)
            response = requests.post(
                f"{self.webhook_url}/{kernel_id}", auth=self.auth, json=body, timeout=60
            )
            self.log.debug(f"Webhook kernel session saving: {kernel_id}")
            if response.status_code != 204:
                self.log.error(response.raise_for_status())

    def load_sessions(self) -> None:
        """
        Loads kernel sessions from database
        """
        if self.enable_persistence:
            response = requests.get(self.webhook_url, auth=self.auth, timeout=60)
            if response.status_code == 200:
                kernel_sessions = response.json()
                for kernel_session in kernel_sessions:
                    self._load_session_from_response(kernel_session)
            else:
                self.log.error(response.raise_for_status())

    def load_session(self, kernel_id: str) -> None:
        """
        Loads a kernel session from database

        :param string kernel_id: A kernel id
        """
        if self.enable_persistence and kernel_id is not None:
            response = requests.get(f"{self.webhook_url}/{kernel_id}", auth=self.auth, timeout=60)
            if response.status_code == 200:
                kernel_session = response.json()
                self._load_session_from_response(kernel_session)
            else:
                self.log.error(response.raise_for_status())

    def _load_session_from_response(self, kernel_session: dict) -> None:
        """
        Loads kernel session to current session

        :param dictionary kernel_session: Kernel session information
        """
        self.log.debug("Loading saved session(s)")
        self._sessions.update(
            KernelSessionManager.post_load_transformation(kernel_session["kernel_session"])
        )
