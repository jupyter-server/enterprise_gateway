# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Manager that tracks kernel activity."""

from traitlets.config.configurable import LoggingConfigurable

# Constants for activity keys in the store
LAST_MESSAGE_TO_CLIENT = 'last_message_to_client'
LAST_MESSAGE_TO_KERNEL = 'last_message_to_kernel'
LAST_TIME_STATE_CHANGED = 'last_time_state_changed'
BUSY = 'busy'
CONNECTIONS = 'connections'
LAST_CLIENT_CONNECT = 'last_client_connect'
LAST_CLIENT_DISCONNECT = 'last_client_disconnect'

# Initial values for all kernel activity keys
DEFAULT_ACTIVITY_VALUES = {
    LAST_MESSAGE_TO_CLIENT: None,
    LAST_MESSAGE_TO_KERNEL: None,
    LAST_TIME_STATE_CHANGED: None,
    BUSY: False,
    CONNECTIONS: 0,
    LAST_CLIENT_CONNECT: None,
    LAST_CLIENT_DISCONNECT: None
}

class ActivityManager(LoggingConfigurable):
    """Represents a store of activity values for kernels. Intended to be used as a
    singleton.

    Parameters
    ----------
    kernel_manager : jupyter_client.multikernelmanager.MultiKernelManager
        Manager instance responsible for the lifecycle of all kernels tracked
        by this class

    Attributes
    ----------
    values : dict
        Kernel ID keys to dictionary of tracked activity values
    kernel_manager : jupyter_client.multikernelmanager.MultiKernelManager
        See parameters.
    """
    def __init__(self, kernel_manager, *args, **kwargs):
        super(ActivityManager, self).__init__(*args, **kwargs)
        self.values = {}
        self.kernel_manager = kernel_manager

    def get_map_for_kernel(self, kernel_id):
        """Gets activity values for a kernel.

        Parameters
        ----------
        kernel_id : str
            Unique identifier for the kernel

        Returns
        -------
        dict
            Activity values for the kernel or defaults if the `kernel_id` is
            not tracked
        """
        if kernel_id not in self.kernel_manager:
            return DEFAULT_ACTIVITY_VALUES.copy()

        if not kernel_id in self.values:
            self.values[kernel_id] = DEFAULT_ACTIVITY_VALUES.copy()

        return self.values[kernel_id]

    def publish(self, kernel_id, activity_type, value=None):
        """Sets the `value` stored for `activity_type` for `kernel_id`.

        Parameters
        ----------
        kernel_id : str
            Unique identifier for the kernel
        activity_type : str
            Activity key to set
        value : any
            Value to set for the activity
        """
        self.get_map_for_kernel(kernel_id)[activity_type] = value

    def increment_activity(self, kernel_id, activity_type):
        """Increments the `activity_type` value (an `int`) for `kernel_id`.

        Parameters
        ----------
        kernel_id : str
            Unique identifier for the kernel
        activity_type : str
            Activity key to set

        Raises
        ------
        TypeError
            If the stored value is not an int
        """
        self.get_map_for_kernel(kernel_id)[activity_type] += 1

    def decrement_activity(self, kernel_id, activity_type):
        """Decrements the `activity_type` value (an `int`) for `kernel_id`.

        Parameters
        ----------
        kernel_id : str
            Unique identifier for the kernel
        activity_type : str
            Activity key to set

        Raises
        ------
        TypeError
            If the stored value is not an int
        """
        self.get_map_for_kernel(kernel_id)[activity_type] -= 1

    def remove(self, kernel_id):
        """Removes all activity values for `kernel_id`.

        Adds the `kernel_id` to the set of IDs to ignore to prevent activities
        during shutdown from causing this manager to being tracking the
        kernel again.

        Parameters
        ----------
        kernel_id : str
            Unique identifier for the kernel
        """
        if kernel_id in self.values:
            del self.values[kernel_id]

    def get(self):
        """Gets all tracked activities for all kernels.

        Returns
        -------
        dict
            Kernel ID keys, activity dictionary values
        """
        return self.values
