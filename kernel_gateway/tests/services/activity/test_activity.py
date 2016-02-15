# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import unittest
import re
from kernel_gateway.services.activity.manager import ActivityManager, LAST_MESSAGE_TO_CLIENT, LAST_MESSAGE_TO_KERNEL, LAST_TIME_STATE_CHANGED, BUSY, CONNECTIONS, LAST_CLIENT_CONNECT, LAST_CLIENT_DISCONNECT
import uuid
from datetime import datetime

class TestActivityStore(unittest.TestCase):
    def get_kernel_id_and_store(self):
        kernel_id = 'fake_id-{}'.format(uuid.uuid1().hex)
        store = ActivityManager()
        return kernel_id, store

    def test_store_creates_default_metrics(self):
        '''Tests if the activity object for a kernel is correctly initialized.'''
        expected_default_values  = [(LAST_MESSAGE_TO_CLIENT, None),
            (LAST_MESSAGE_TO_KERNEL, None),
            (LAST_TIME_STATE_CHANGED , None),
            (BUSY , False),
            (CONNECTIONS , 0),
            (LAST_CLIENT_CONNECT , None),
            (LAST_CLIENT_DISCONNECT , None)
        ]
        kernel_id, store = self.get_kernel_id_and_store()
        values = {}
        store.populate_kernel_with_defaults(values)

        self.assertEqual(len(values), len(expected_default_values), 'The number of default values was different than expected.')

        for expected_tuple in expected_default_values:
            key, expected_value = expected_tuple
            self.assertEqual(values[key], expected_value,
                'Activity {} was not initialized to correct value {}'.format(key, expected_value)
            )

    def test_publish_sets_activity_value(self):
        '''publish should set the value for an existing activity'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.publish(kernel_id, BUSY, True)
        self.assertEqual(store.get()[kernel_id][BUSY], True, 'Kernel activity value was not properly set')
        time = datetime.now()
        store.publish(kernel_id, LAST_MESSAGE_TO_KERNEL, time)
        self.assertEqual(store.get()[kernel_id][LAST_MESSAGE_TO_KERNEL], time, 'Kernel activity value was not properly set')

    def test_publish_sets_activity_value_for_new_activity(self):
        '''publish should set the value for a new activity'''
        kernel_id, store = self.get_kernel_id_and_store()
        new_activity = uuid.uuid1().hex
        value = 'some awesome value'
        store.publish(kernel_id, new_activity, value)
        self.assertEqual(store.get()[kernel_id][new_activity], value, 'Kernel activity value was not properly set')

    def test_publish_populates_store_for_new_kernel(self):
        '''publish should initialize an activity object for a new kernel'''
        kernel_id, store = self.get_kernel_id_and_store()
        new_activity = uuid.uuid1().hex
        value = 'some awesome value'
        store.publish(kernel_id, new_activity, value)
        self.assertTrue(store.get()[kernel_id] is not None, 'Kernel activity object was not created')

    def test_increment_activity_should_increment_activity(self):
        '''increment_activity should increment the value of an activity'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity(kernel_id, CONNECTIONS)
        store.increment_activity(kernel_id, CONNECTIONS)
        store.increment_activity(kernel_id, CONNECTIONS)
        self.assertEqual(store.get()[kernel_id][CONNECTIONS], 3, 'Kernel activity value was incremented')

    def test_increment_activity_should_raise_type_error_for_non_int(self):
        '''increment_activity should raise a TypeError for incrementing a non-integer value'''
        kernel_id, store = self.get_kernel_id_and_store()
        new_activity = uuid.uuid1().hex
        store.publish(kernel_id, new_activity, 'some awesome value')
        try:
            store.increment_activity(kernel_id, new_activity)
        except TypeError:
            return
        self.fail('TypeError was not raised')

    def test_increment_activity_should_raise_key_error_for_unknown_activity(self):
        '''increment_activity should raise a KeyError for incrementing an unknown activity'''
        kernel_id, store = self.get_kernel_id_and_store()
        try:
            store.increment_activity(kernel_id, uuid.uuid1().hex)
        except KeyError:
            return
        self.fail('KeyError was not raised')

    def test_increment_activity_populates_store_for_new_kernel(self):
        '''increment_activity should initialize an activity object for a new kernel'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity(kernel_id, CONNECTIONS)
        self.assertTrue(store.get()[kernel_id] is not None, 'Kernel activity object was not created')

    def test_decrement_activity_should_increment_activity(self):
        '''decrement_activity should increment the value of an activity'''

    def test_decrement_activity_should_raise_type_error_for_non_int(self):
        '''decrement_activity should raise a TypeError for decrementing a non-integer value'''
        kernel_id, store = self.get_kernel_id_and_store()
        new_activity = uuid.uuid1().hex
        store.publish(kernel_id, new_activity, 'some awesome value')
        try:
            store.decrement_activity(kernel_id, new_activity)
        except TypeError:
            return
        self.fail('TypeError was not raised')

    def test_decrement_activity_should_raise_key_error_for_unknown_activity(self):
        '''decrement_activity should raise a KeyError for decrementing an unknown activity'''
        kernel_id, store = self.get_kernel_id_and_store()
        try:
            store.decrement_activity(kernel_id, uuid.uuid1().hex)
        except KeyError:
            return
        self.fail('KeyError was not raised')

    def test_decrement_activity_populates_store_for_new_kernel(self):
        '''decrement_activity should initialize an activity object for a new kernel'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.decrement_activity(kernel_id, CONNECTIONS)
        self.assertTrue(store.get()[kernel_id] is not None, 'Kernel activity object was not created')

    def test_remove_should_blacklist_kernel(self):
        '''remove should add the kernel_id to the blacklist'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity(kernel_id, CONNECTIONS)
        store.remove(kernel_id)
        self.assertTrue(kernel_id in store.ignore, 'Kernel was not blacklisted')

    def test_remove_should_remove_kernel_from_get(self):
        '''remove should remove the kernel from the store's values'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity(kernel_id, CONNECTIONS)
        store.remove(kernel_id)
        self.assertTrue(not kernel_id in store.get(), 'Kernel was not removed from values')

    def test_remove_should_not_allow_new_activities_for_a_kernel(self):
        '''remove should not allow future activities for a kernel to be recorded'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity(kernel_id, CONNECTIONS)
        store.remove(kernel_id)
        store.increment_activity(kernel_id, CONNECTIONS)
        self.assertTrue(store.get().get(kernel_id) is None, 'New kernel activities were created when they should not have been')

    def test_get_should_return_list_of_kernel_activities(self):
        '''get should return a list of all kernel activities record'''
        kernel_id, store = self.get_kernel_id_and_store()
        store.increment_activity('{}-1'.format(kernel_id), CONNECTIONS)
        store.increment_activity('{}-2'.format(kernel_id), CONNECTIONS)
        store.increment_activity('{}-3'.format(kernel_id), CONNECTIONS)
        print(store.get())
        self.assertEqual(len(store.get()), 3, 'Activities were not created for all of the kernels')
