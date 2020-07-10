# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Session manager that keeps all its metadata in memory."""

import uuid
from tornado import web
from traitlets.config.configurable import LoggingConfigurable
from ipython_genutils.py3compat import unicode_type


class SessionManager(LoggingConfigurable):
    """Simple implementation of the SessionManager interface that allows clients
    to associate basic metadata with a kernel.

    Parameters
    ----------
    kernel_manager : SeedingMappingKernelManager
        Used to start a kernel when creating a session

    Attributes
    ----------
    kernel_manager : SeedingMappingKernelManager
        Used to start a kernel when creating a session
    _sessions : list
        Sessions
    _columns : list
        Session metadata key names
    """
    def __init__(self, kernel_manager, *args, **kwargs):
        super(SessionManager, self).__init__(*args, **kwargs)
        self.kernel_manager = kernel_manager
        self._sessions = []
        self._columns = ['session_id', 'path', 'kernel_id']

    def session_exists(self, path, *args, **kwargs):
        """Checks to see if the session with the given path value exists.

        Parameters
        ----------
        path : str
            Session path value to search on

        Returns
        -------
        bool
        """
        return bool([item for item in self._sessions if item['path'] == path])

    def new_session_id(self):
        """Creates a uuid for a new session."""
        return unicode_type(uuid.uuid4())

    async def create_session(self, path=None, kernel_name=None, kernel_id=None, *args, **kwargs):
        """Creates a session and returns its model.

        Launches a kernel and stores the session metadata for later lookup.

        Parameters
        ----------
        path : str
            Path value to store in the session metadata
        kernel_name : str
            Kernel spec name
        kernel_id : str
            Existing kernel ID to bind to the session (unsupported)

        Returns
        -------
        dict
            Session model
        """
        session_id = self.new_session_id()
        # allow nbm to specify kernels cwd
        kernel_id = await self.kernel_manager.start_kernel(path=path, kernel_name=kernel_name)
        return self.save_session(session_id, path=path, kernel_id=kernel_id)

    def save_session(self, session_id, path=None, kernel_id=None, *args, **kwargs):
        """Saves the metadata for the session with the given `session_id`.

        Given a `session_id` (and any other of the arguments), this method
        appends a dictionary to the in-memory list of sessions.

        Parameters
        ----------
        session_id : str
            UUID for the session; this method must be given a session_id
        path : str
            Path for the given notebook
        kernel_id : str
            ID for the kernel associated with this session

        Returns
        -------
        dict
            Session model with `session_id`, `path`, and `kernel_id` keys
        """
        self._sessions.append({'session_id': session_id,
                               'path': path,
                               'kernel_id': kernel_id})

        return self.get_session(session_id=session_id)

    def get_session_by_key(self, key, val, *args, **kwargs):
        """Gets the first session with the given key/value pair.

        Parameters
        ----------
        key : hashable
            Session metadata key to match
        value : any
            Session metadata value to match

        Returns
        -------
        dict
            Matching session model or None if not found
        """
        s = [item for item in self._sessions if item[key] == val]
        return None if not s else s[0]

    def get_session(self, **kwargs):
        """Returns the model for a particular session.

        Takes a keyword argument and searches for the value in the in-memory
        session store. Returns the entire session model.

        Parameters
        ----------
        **kwargs : keyword argument
            One of the key/value pairs from `_columns`

        Raises
        ------
        TypeError
            If there are no kwargs or none of them match a key/column used in
            the metadata
        tornado.web.HTTPError
            404 Not Found if no session matches the provided metadata

        Returns
        -------
        model : dict
            All the information from the session described by the kwarg
        """
        if not kwargs:
            raise TypeError("Must specify a column to query")

        for param in kwargs.keys():
            if param not in self._columns:
                raise TypeError("No such column: %r", param)

        # multiple columns are never passed into kwargs so just using the
        # first and only one.
        column = list(kwargs.keys())[0]
        row = self.get_session_by_key(column, kwargs[column])

        if not row:
            raise web.HTTPError(404, u'Session not found: %s' % kwargs[column])

        return self.row_to_model(row)

    def update_session(self, session_id, *args, **kwargs):
        """Updates the values in the session store.

        Update the values of the session model with the given `session_id`
        with the values from the keyword arguments.

        Parameters
        ----------
        session_id : str
            UUID that identifies a session in the sqlite3 database
        **kwargs : str
            Key/value pairs to store

        Raises
        ------
        KeyError
            If no session matches the given `session_id`
        """
        if not kwargs:
            # no changes
            return

        row = self.get_session_by_key('session_id', session_id)

        if not row:
            raise KeyError

        self._sessions.remove(row)

        if 'path' in kwargs:
            row['path'] = kwargs['path']

        if 'kernel_id' in kwargs:
            row['kernel_id'] = kwargs['kernel_id']

        self._sessions.append(row)

    def row_to_model(self, row, *args, **kwargs):
        """Turns a "row" in the in-memory session store into a model dictionary.

        Parameters
        ----------
        row : dict
            Maps `id` to `session_id`, `notebook` to a dict containing the
            `path`, and `kernel` to the kernel model looked up using the
            `kernel_id`
        """
        if row['kernel_id'] not in self.kernel_manager:
            # The kernel was killed or died without deleting the session.
            # We can't use delete_session here because that tries to find
            # and shut down the kernel.
            self._sessions.remove(row)
            raise KeyError

        model = {
            'id': row['session_id'],
            'notebook': {
                'path': row['path']
            },
            'kernel': self.kernel_manager.kernel_model(row['kernel_id'])
        }
        return model

    def list_sessions(self, *args, **kwargs):
        """Returns a list of dictionaries containing all the information from
        the session store.

        Returns
        -------
        list
            Dictionaries from `row_to_model`
        """
        l = [self.row_to_model(r) for r in self._sessions]
        return l

    async def delete_session(self, session_id, *args, **kwargs):
        """Deletes the session in the session store with given `session_id`.

        Raises
        ------
        KeyError
            If the `session_id` is not in the store
        """
        # Check that session exists before deleting
        s = self.get_session_by_key('session_id', session_id)
        if not s:
            raise KeyError

        await self.kernel_manager.shutdown_kernel(s['kernel_id'])
        self._sessions.remove(s)
