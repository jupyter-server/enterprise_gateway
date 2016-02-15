# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

LAST_MESSAGE_TO_CLIENT = 'last_message_to_client'
LAST_MESSAGE_TO_KERNEL = 'last_message_to_kernel'
LAST_TIME_STATE_CHANGED = 'last_time_state_changed'
BUSY = 'busy'
CONNECTIONS = 'connections'
LAST_CLIENT_CONNECT = 'last_client_connect'
LAST_CLIENT_DISCONNECT = 'last_client_disconnect'

default_activity_values = [(LAST_MESSAGE_TO_CLIENT, None),
    (LAST_MESSAGE_TO_KERNEL, None),
    (LAST_TIME_STATE_CHANGED , None),
    (BUSY , False),
    (CONNECTIONS , 0),
    (LAST_CLIENT_CONNECT , None),
    (LAST_CLIENT_DISCONNECT , None)
]
class ActivityManager(object):
    '''Represents a store of activity values for kernels. There is a singleton instance
    called `activity` created in this module.'''
    def __init__(self):
        self.values = {}
        # A blacklist of kernels that have been removed so no more activities cannot sneak in.
        # This can happen when a kernel is deleted, and a websocket is later disconnected
        self.ignore = set()
        self.dummy_map = {}
        self.populate_kernel_with_defaults(self.dummy_map)

    def populate_kernel_with_defaults(self, activity_values):
        '''Sets the default value for known activities being recorded.
        '''
        for value in default_activity_values:
            activity_values[value[0]] = value[1]

    def get_map_for_kernel(self, kernel_id):
        '''Gets a map for a kernel. This method will always return a map, even if the kernel has been removed.
        In the event the kernel has been removed, the activities will not be recorded.
        '''
        if kernel_id in self.ignore:
            return self.dummy_map

        if not kernel_id in self.values:
            self.values[kernel_id] =  {}
            self.populate_kernel_with_defaults(self.values[kernel_id])

        return self.values[kernel_id]

    def publish(self, kernel_id, activity_type, value=None):
        '''Sets the value stored for *activity_type*. If the activity_type is not found, it
        will be created and assigned to *value*.
        '''
        self.get_map_for_kernel(kernel_id)[activity_type] = value;


    def increment_activity(self, kernel_id, activity_type):
        '''Increments the value stored for *activity_type*. If the value currently stored
        is not an int, an TypeError will be raised. If the activity_type is not found, a
        KeyError will be raised.
        '''
        self.get_map_for_kernel(kernel_id)[activity_type] += 1;

    def decrement_activity(self, kernel_id, activity_type):
        '''Decrements the value stored for *activity_type*. If the value currently stored
        is not an int, an TypeError will be raised. If the activity_type is not found, a
        KeyError will be raised.
        '''
        self.get_map_for_kernel(kernel_id)[activity_type] -= 1;

    def remove(self, kernel_id):
        '''Removes the activities for a kernel.'''
        if kernel_id in self.values:
            del self.values[kernel_id]
            self.ignore.add(kernel_id)

    def get(self):
        '''Returns a mapping of kernel_id to activity values.
        '''
        return self.values

activity = ActivityManager()
