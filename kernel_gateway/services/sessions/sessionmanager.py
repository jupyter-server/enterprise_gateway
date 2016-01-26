"""A base class session manager."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import uuid

from tornado import web

from traitlets.config.configurable import LoggingConfigurable
from ipython_genutils.py3compat import unicode_type

class SessionManager(LoggingConfigurable):

    def __init__(self, kernel_manager):
        self.kernel_manager = kernel_manager
        self._sessions = []
        self._columns = ['session_id', 'path', 'kernel_id']

    def session_exists(self, path):
        """Check to see if the session for a given notebook exists"""
        return bool([item for item in self._sessions if item['path'] == path])

    def new_session_id(self):
        "Create a uuid for a new session"
        return unicode_type(uuid.uuid4())

    def create_session(self, path=None, kernel_name=None):
        """Creates a session and returns its model"""
        session_id = self.new_session_id()
        # allow nbm to specify kernels cwd
        kernel_id = self.kernel_manager.start_kernel(path=path,
                                                     kernel_name=kernel_name)
        return self.save_session(session_id, path=path,
                                 kernel_id=kernel_id)

    def save_session(self, session_id, path=None, kernel_id=None):
        """Saves the items for the session with the given session_id
        
        Given a session_id (and any other of the arguments), this method
        creates a row in the sqlite session database that holds the information
        for a session.
        
        Parameters
        ----------
        session_id : str
            uuid for the session; this method must be given a session_id
        path : str
            the path for the given notebook
        kernel_id : str
            a uuid for the kernel associated with this session
        
        Returns
        -------
        model : dict
            a dictionary of the session model
        """
        self._sessions.append({'session_id': session_id, 
                               'path':path, 
                               'kernel_id': kernel_id})

        return self.get_session(session_id=session_id)

    def get_session_by_key(self, key, val):
        s = [item for item in self._sessions if item[key] == val]
        return None if not s else s[0]

    def get_session(self, **kwargs):
        """Returns the model for a particular session.
        
        Takes a keyword argument and searches for the value in the session
        database, then returns the rest of the session's info.

        Parameters
        ----------
        **kwargs : keyword argument
            must be given one of the keywords and values from the session database
            (i.e. session_id, path, kernel_id)

        Returns
        -------
        model : dict
            returns a dictionary that includes all the information from the 
            session described by the kwarg.
        """
        if not kwargs:
            raise TypeError("must specify a column to query")

        for param in kwargs.keys():
            if param not in self._columns:
                raise TypeError("No such column: %r", param)

        #multiple columns are never passed into kwargs so just using the
        #first and only one.
        column = list(kwargs.keys())[0]
        row = self.get_session_by_key(column, kwargs[column])

        if not row:
            raise web.HTTPError(404, u'Session not found: %s' % kwargs[column])

        return self.row_to_model(row)

    def update_session(self, session_id, **kwargs):
        """Updates the values in the session database.
        
        Changes the values of the session with the given session_id
        with the values from the keyword arguments. 
        
        Parameters
        ----------
        session_id : str
            a uuid that identifies a session in the sqlite3 database
        **kwargs : str
            the key must correspond to a column title in session database,
            and the value replaces the current value in the session 
            with session_id.
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


    def row_to_model(self, row):
        """Takes sqlite database session row and turns it into a dictionary"""
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

    def list_sessions(self):
        """Returns a list of dictionaries containing all the information from
        the session database"""

        l = [self.row_to_model(r) for r in self._sessions]
        return l

    def delete_session(self, session_id):
        """Deletes the row in the session database with given session_id"""
        # Check that session exists before deleting
        s = self.get_session_by_key('session_id', session_id)
        if not s:
            raise KeyError

        self.kernel_manager.shutdown_kernel(s['kernel_id'])
        self._sessions.remove(s)
