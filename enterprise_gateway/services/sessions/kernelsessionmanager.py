# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Session manager that keeps all its metadata in memory."""

import copy
import getpass
import json
import os
import threading

from ipython_genutils.py3compat import (bytes_to_str, str_to_bytes)
from jupyter_core.paths import jupyter_data_dir
from traitlets import Bool
from traitlets.config.configurable import LoggingConfigurable

kernels_lock = threading.Lock()
kernel_session_location = os.getenv('EG_KERNEL_SESSION_LOCATION', jupyter_data_dir())


class KernelSessionManager(LoggingConfigurable):
    """KernelSessionManager is persist and load kernel sessions from persistent storage.

        KernelSessionManager provides the basis for an HA solution.  It loads the complete set of persisted kernel
        sessions during construction.  Following construction the parent object calls start_sessions to allow
        Enterprise Gateway to validate that all loaded sessions are still valid.  Those that it cannot 'revive' 
        are marked for deletion and the in-memory dictionary is updated - and the entire collection is written 
        to store (file or database).
        
        As kernels are created and destroyed, the KernelSessionManager is called upon to keep kernel session
        state consistent.
    """

    enable_persistence = Bool(default_value=False, config=True,
        help="""Enable kernel session persistence.  Default = False""")

    def __init__(self, kernel_manager, **kwargs):
        super(KernelSessionManager, self).__init__(**kwargs)
        self.kernel_manager = kernel_manager
        self._sessions = dict()
        self._sessionsByUser = dict()
        if self.enable_persistence:
            self.kernel_session_file = os.path.join(self._get_sessions_loc(), 'kernels.json')
            self._load_sessions()

    def create_session(self, kernel_id, **kwargs):
        """Creates a session associated with this kernel.

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
        kernel_session = dict()
        kernel_session['kernel_id'] = kernel_id
        kernel_session['username'] = KernelSessionManager.get_kernel_username(**kwargs)
        kernel_session['kernel_name'] = km.kernel_name

        # Build the inner dictionaries: connection_info, process_proxy and add to kernel_session
        kernel_session['connection_info'] = km.get_connection_info()
        kernel_session['launch_args'] = kwargs.copy()
        kernel_session['process_info'] = km.process_proxy.get_process_info() if km.process_proxy else {}
        self._save_session(kernel_id, kernel_session)

    def refresh_session(self, kernel_id):
        """Refreshes the session from its persisted state. Called on kernel restarts."""
        self.log.debug("Refreshing kernel session for id: {}".format(kernel_id))
        km = self.kernel_manager.get_kernel(kernel_id)

        # Compose the kernel_session entry
        kernel_session = self._sessions[kernel_id]

        # Build the inner dictionaries: connection_info, process_proxy and add to kernel_session
        kernel_session['connection_info'] = km.get_connection_info()
        kernel_session['process_info'] = km.process_proxy.get_process_info() if km.process_proxy else {}
        self._save_session(kernel_id, kernel_session)

    def _save_session(self, kernel_id, kernel_session):
        # Write/commit the addition, update dictionary
        kernels_lock.acquire()
        try:
            self._sessions[kernel_id] = kernel_session
            username = kernel_session['username']
            if username not in self._sessionsByUser:
                self._sessionsByUser[username] = []
                self._sessionsByUser[username].append(kernel_id)
            else:
                # Only append if not there yet (e.g. restarts will be there already)
                if kernel_id not in self._sessionsByUser[username]:
                    self._sessionsByUser[username].append(kernel_id)
            self._commit_sessions()  # persist changes
        finally:
            kernels_lock.release()

    def _load_sessions(self):
        if self.enable_persistence:
            # Read directory/table and initialize _sessions member.  Must be called from constructor.
            if os.path.exists(self.kernel_session_file):
                self.log.debug("Loading saved sessions from {}".format(self.kernel_session_file))
                with open(self.kernel_session_file) as fp:
                    self._sessions = self._post_load_transformation(json.load(fp))
                    fp.close()

    def start_sessions(self):
        """ Attempt to start persisted sessions.

        Determines if session startup was successful.  If unsuccessful, the session is removed
        from persistent storage.
        """
        if self.enable_persistence:
            sessions_to_remove = []
            for kernel_id, kernel_session in self._sessions.items():
                self.log.info("Attempting startup of persisted kernel session for id: %s..." % kernel_id)
                if self._start_session(kernel_session):
                    self.log.info("Startup of persisted kernel session for id '{}' was successful.  Client should "
                                  "reconnect kernel.".format(kernel_id))
                else:
                    sessions_to_remove.append(kernel_id)
                    self.log.warn("Startup of persisted kernel session for id '{}' was not successful.  Check if "
                                  "client is still active and restart kernel.".format(kernel_id))

            self._delete_sessions(sessions_to_remove)

    def _start_session(self, kernel_session):
        # Attempt to start kernel from persisted state.  if started, record kernel_session in dictionary
        # else delete session
        kernel_id = kernel_session['kernel_id']
        kernel_started = self.kernel_manager.start_kernel_from_session(kernel_id=kernel_id,
                                                                kernel_name=kernel_session['kernel_name'],
                                                                connection_info=kernel_session['connection_info'],
                                                                process_info=kernel_session['process_info'],
                                                                launch_args=kernel_session['launch_args'])
        if not kernel_started:
            return False

        return True

    def delete_session(self, kernel_id):
        """Removes saved session associated with kernel_id from dictionary and persisted storage."""
        self._delete_sessions([kernel_id])

        if self.enable_persistence:
            self.log.info("Deleted persisted kernel session for id: %s" % kernel_id)

    def _delete_sessions(self, kernel_ids):
        # Remove unstarted sessions and rewrite
        kernels_lock.acquire()
        try:
            for kernel_id in kernel_ids:
                # Prior to removing session, update the per User list
                kernel_session = self._sessions[kernel_id]
                username = kernel_session['username']
                if username in self._sessionsByUser and kernel_id in self._sessionsByUser[username]:
                    self._sessionsByUser[username].remove(kernel_id)
                self._sessions.pop(kernel_id, None)

            self._commit_sessions()  # persist changes
        finally:
            kernels_lock.release()

    def _commit_sessions(self):
        if self.enable_persistence:
            # Commits the sessions dictionary to persistent store.  Caller is responsible for single-threading call.
            with open(self.kernel_session_file, 'w') as fp:
                json.dump(self._pre_save_transformation(self._sessions), fp)
                fp.close()

    @staticmethod
    def _pre_save_transformation(sessions):
        sessions_copy = copy.deepcopy(sessions)
        for kernel_id, session in sessions_copy.items():
            if session.get('connection_info'):
                info = session['connection_info']
                key = info.get('key')
                if key:
                    info['key'] = bytes_to_str(key)

        return sessions_copy

    @staticmethod
    def _post_load_transformation(sessions):
        sessions_copy = copy.deepcopy(sessions)
        for kernel_id, session in sessions_copy.items():
            if session.get('connection_info'):
                info = session['connection_info']
                key = info.get('key')
                if key:
                    info['key'] = str_to_bytes(key)

        return sessions_copy

    def _get_sessions_loc(self):
        path = os.path.join(kernel_session_location, 'sessions')
        if not os.path.exists(path):
            os.makedirs(path, 0o755)
        self.log.info("Kernel session persistence location: {}".format(path))
        return path

    def active_sessions(self, username):
        """ Returns the number of active sessions for the given username.

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
    def get_kernel_username(**kwargs):
        """ Returns the kernel's logical username from env dict.

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
        env_dict = kwargs.get('env', {})

        # Ensure KERNEL_USERNAME is set
        kernel_username = env_dict.get('KERNEL_USERNAME')
        if kernel_username is None:
            kernel_username = getpass.getuser()
            env_dict['KERNEL_USERNAME'] = kernel_username

        return kernel_username
