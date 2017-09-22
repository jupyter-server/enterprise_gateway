# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Session manager that keeps all its metadata in memory."""

import os
from traitlets.config.configurable import LoggingConfigurable
from traitlets import Bool
from jupyter_core.paths import jupyter_data_dir
import json


import threading
kernels_lock = threading.Lock()
kernel_session_location = os.getenv('EG_KERNEL_SESSION_LOCATION', jupyter_data_dir())


class KernelSessionManager(LoggingConfigurable):
    """
        KernelSessionManager is used to manage kernel sessions.  It loads the complete set of persisted kernel
        sessions during construction.  Following construction the parent object calls start_sessions to allow
        Enterprise Gateway to validate that all loaded sessions are still valid.  Those that it cannot 'revive' 
        are marked for deletion and the in-memory dictionary is updated - and the entire collection is written 
        to store (file or database).
        
        As kernels are created and destroyed, the KernelSessionManager is called upon to keep kernel session
        state consistent.
    """

    enable_persistence = Bool(default_value=False, config=True,
        help="""Enable kernel session persistence.  Default = False"""
    )

    def __init__(self, kernel_manager, *args, **kwargs):
        super(KernelSessionManager, self).__init__(*args, **kwargs)
        self.kernel_manager = kernel_manager
        if self.enable_persistence:
            self._sessions = dict()
            self.kernel_session_file = os.path.join(self._get_sessions_loc(), 'kernels.json')
            self._load_sessions()

    def create_session(self, kernel_id, **kwargs):
        # Persists information about the kernel session within the designated repository.
        if self.enable_persistence:
            km = self.kernel_manager.get_kernel(kernel_id)

            # Compose the kernel_session entry
            kernel_session = dict()
            kernel_session['kernel_id'] = kernel_id
            kernel_session['username'] = self._get_kernel_username(kwargs.get('env',{}))
            kernel_session['kernel_name'] = km.kernel_name

            # Build the inner dictionaries: connection_info, process_proxy and add to kernel_session
            kernel_session['connection_info'] = km.get_connection_info()
            kernel_session['launch_args'] = kwargs.copy()
            kernel_session['process_info'] = km.process_proxy.get_process_info() if km.process_proxy else {}
            self._save_session(kernel_id, kernel_session)

    def refresh_session(self, kernel_id, **kwargs):
        # Persists information about the kernel session within the designated repository.
        if self.enable_persistence:
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
            self._commit_sessions()  # persist changes
        finally:
            kernels_lock.release()

    def _load_sessions(self):
        # Read directory/table and initialize _sessions member.  Must be called from constructor.
        if os.path.exists(self.kernel_session_file):
            self.log.debug("Loading saved sessions from {}".format(self.kernel_session_file))
            with open(self.kernel_session_file) as fp:
                self._sessions = json.load(fp)
                fp.close()

    def start_sessions(self):
        # Track which sessions didn't restart...
        if self.enable_persistence:
            sessions_to_remove = []
            for kernel_id, kernel_session in self._sessions.items():
                if not self._start_session(kernel_session):
                    sessions_to_remove.append(kernel_id)

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

        self.log.info("Started persisted kernel session for id: %s" % kernel_id)
        return True

    def delete_session(self, kernel_id):
        # Removes saved session from dictionary and persisted store
        if self.enable_persistence:
            self._delete_sessions([kernel_id])
            self.log.info("Deleted persisted kernel session for id: %s" % kernel_id)

    def _delete_sessions(self, kernel_ids):
        # Remove unstarted sessions and rewrite
        kernels_lock.acquire()
        try:
            for kernel_id in kernel_ids:
                self._sessions.pop(kernel_id, None)

            self._commit_sessions()  # persist changes
        finally:
            kernels_lock.release()

    def _commit_sessions(self):
        # Commits the sessions dictionary to persistent store.  Caller is responsible for single-threading call.
        with open(self.kernel_session_file, 'w') as fp:
            json.dump(self._sessions, fp)
            fp.close()

    def _get_sessions_loc(self):
        path = os.path.join(kernel_session_location, 'sessions')
        if not os.path.exists(path):
            os.makedirs(path, 0o755)
        self.log.info("Kernel session persistence location: {}".format(path))
        return path

    @staticmethod
    def _get_kernel_username(env_dict):
        return env_dict.get('KERNEL_USERNAME', 'unspecified')
