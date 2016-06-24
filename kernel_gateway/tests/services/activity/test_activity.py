# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for tracking client/kernel activities."""

import unittest
from kernel_gateway.services.activity.manager import ActivityManager, LAST_MESSAGE_TO_CLIENT, LAST_MESSAGE_TO_KERNEL, LAST_TIME_STATE_CHANGED, BUSY, CONNECTIONS, LAST_CLIENT_CONNECT, LAST_CLIENT_DISCONNECT
import uuid
from datetime import datetime

class TestActivityManager(unittest.TestCase):
    """Unit tests the ActivityManager class."""
    def setUp(self):
        self.kernel_id = 'fake_id-{}'.format(uuid.uuid1().hex)
        self.kernel_manager = [self.kernel_id]
        self.activity = ActivityManager(self.kernel_manager)

    def test_store_creates_default_metrics(self):
        """Unknown kernels should have default activity values."""
        expected_default_values  = [(LAST_MESSAGE_TO_CLIENT, None),
            (LAST_MESSAGE_TO_KERNEL, None),
            (LAST_TIME_STATE_CHANGED , None),
            (BUSY , False),
            (CONNECTIONS , 0),
            (LAST_CLIENT_CONNECT , None),
            (LAST_CLIENT_DISCONNECT , None)
        ]
        values = self.activity.get_map_for_kernel(self.kernel_id)

        self.assertEqual(len(values), len(expected_default_values), 'The number of default values was different than expected.')

        for expected_tuple in expected_default_values:
            key, expected_value = expected_tuple
            self.assertEqual(values[key], expected_value,
                'Activity {} was not initialized to correct value {}'.format(key, expected_value)
            )

    def test_publish_sets_activity_value(self):
        """publish should set the value for an existing activity"""
        self.activity.publish(self.kernel_id, BUSY, True)
        self.assertEqual(self.activity.get()[self.kernel_id][BUSY], True, 'Kernel activity value was not properly set')
        time = datetime.utcnow()
        self.activity.publish(self.kernel_id, LAST_MESSAGE_TO_KERNEL, time)
        self.assertEqual(self.activity.get()[self.kernel_id][LAST_MESSAGE_TO_KERNEL], time, 'Kernel activity value was not properly set')

    def test_publish_sets_activity_value_for_new_activity(self):
        """publish should set the value for a new activity"""
        new_activity = uuid.uuid1().hex
        value = 'some awesome value'
        self.activity.publish(self.kernel_id, new_activity, value)
        self.assertEqual(self.activity.get()[self.kernel_id][new_activity], value, 'Kernel activity value was not properly set')

    def test_publish_populates_store_for_new_kernel(self):
        """publish should initialize an activity object for a new kernel"""
        new_activity = uuid.uuid1().hex
        value = 'some awesome value'
        self.activity.publish(self.kernel_id, new_activity, value)
        self.assertTrue(self.activity.get()[self.kernel_id] is not None, 'Kernel activity object was not created')

    def test_increment_activity_should_increment_activity(self):
        """increment_activity should increment the value of an activity"""
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.assertEqual(self.activity.get()[self.kernel_id][CONNECTIONS], 3, 'Kernel activity value was incremented')

    def test_increment_activity_should_raise_type_error_for_non_int(self):
        """increment_activity should raise a TypeError for incrementing a non-integer value"""
        new_activity = uuid.uuid1().hex
        self.activity.publish(self.kernel_id, new_activity, 'some awesome value')
        try:
            self.activity.increment_activity(self.kernel_id, new_activity)
        except TypeError:
            return
        self.fail('TypeError was not raised')

    def test_increment_activity_should_raise_key_error_for_unknown_activity(self):
        """increment_activity should raise a KeyError for incrementing an unknown activity"""
        try:
            self.activity.increment_activity(self.kernel_id, uuid.uuid1().hex)
        except KeyError:
            return
        self.fail('KeyError was not raised')

    def test_increment_activity_populates_store_for_new_kernel(self):
        """increment_activity should initialize an activity object for a new kernel"""
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.assertTrue(self.activity.get()[self.kernel_id] is not None, 'Kernel activity object was not created')

    def test_decrement_activity_should_decrement_activity(self):
        """decrement_activity should decreate the value of an activity"""
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.activity.decrement_activity(self.kernel_id, CONNECTIONS)
        self.assertEqual(self.activity.get()[self.kernel_id][CONNECTIONS], 1, 'Kernel activity value was decremented')

    def test_decrement_activity_should_raise_type_error_for_non_int(self):
        """decrement_activity should raise a TypeError for decrementing a non-integer value"""
        new_activity = uuid.uuid1().hex
        self.activity.publish(self.kernel_id, new_activity, 'some awesome value')
        try:
            self.activity.decrement_activity(self.kernel_id, new_activity)
        except TypeError:
            return
        self.fail('TypeError was not raised')

    def test_decrement_activity_should_raise_key_error_for_unknown_activity(self):
        """decrement_activity should raise a KeyError for decrementing an unknown activity"""
        try:
            self.activity.decrement_activity(self.kernel_id, uuid.uuid1().hex)
        except KeyError:
            return
        self.fail('KeyError was not raised')

    def test_decrement_activity_populates_store_for_new_kernel(self):
        """decrement_activity should initialize an activity object for a new kernel"""
        self.activity.decrement_activity(self.kernel_id, CONNECTIONS)
        self.assertTrue(self.activity.get()[self.kernel_id] is not None, 'Kernel activity object was not created')

    def test_remove_should_remove_kernel_from_get(self):
        """remove should remove the kernel from the store's values"""
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.activity.remove(self.kernel_id)
        self.assertTrue(not self.kernel_id in self.activity.get(), 'Kernel was not removed from values')

    def test_remove_should_not_allow_new_activities_for_a_kernel(self):
        """remove should not allow future activities for a kernel to be recorded"""
        self.activity.increment_activity(self.kernel_id, CONNECTIONS)

        # Simulate kernel shutdown and removal from the activity tracker
        self.kernel_manager.remove(self.kernel_id)
        self.activity.remove(self.kernel_id)

        self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        self.assertTrue(self.activity.get().get(self.kernel_id) is None, 'New kernel activities were created when they should not have been')

    def test_get_should_return_list_of_kernel_activities(self):
        """get should return a list of all kernel activities record"""
        # Simulate three kernels
        for i in range(3):
            kernel_id = '{}-{}'.format(self.kernel_id, i)
            # Track each one in the kernel manager so that they're not ignored
            # by the activity manager
            self.kernel_manager.append(kernel_id)
            self.activity.increment_activity(kernel_id, CONNECTIONS)
        self.assertEqual(len(self.activity.get()), 3, 'Activities were not created for all of the kernels')
