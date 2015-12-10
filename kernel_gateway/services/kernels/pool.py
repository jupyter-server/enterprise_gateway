# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from tornado.locks import Semaphore
from tornado import gen


class KernelPool():
    def __init__(self, prespawn_count, kernel_manager):
        self.kernel_clients = {}
        self.on_recv_funcs = {}
        self.kernel_manager = kernel_manager
        self.pool_index = 0
        self.kernel_pool = []
        self.kernel_semaphore = Semaphore(prespawn_count)

        for _ in range(prespawn_count):
            kernel_id = kernel_manager.start_kernel()
            self.kernel_clients[kernel_id] = kernel_manager.get_kernel(kernel_id).client()
            self.kernel_pool.append(kernel_id)
            iopub = self.kernel_manager.connect_iopub(kernel_id)
            iopub.on_recv(self.create_on_reply(kernel_id))

    @gen.coroutine
    def acquire(self):
        yield self.kernel_semaphore.acquire()
        kernel_id = self.kernel_pool[0]
        del self.kernel_pool[0]
        raise gen.Return((self.kernel_clients[kernel_id], kernel_id))

    def release(self, kernel_id):
        self.kernel_pool.append(kernel_id)
        self.kernel_semaphore.release()

    def _on_reply(self, kernel_id, msg_list):
        idents, msg_list = self.kernel_clients[kernel_id].session.feed_identities(msg_list)
        msg = self.kernel_clients[kernel_id].session.deserialize(msg_list)
        self.on_recv_funcs[kernel_id](msg)

    def create_on_reply(self, kernel_id):
        return lambda msg_list: self._on_reply(kernel_id, msg_list)

    def on_recv(self, kernel_id, func):
        self.on_recv_funcs[kernel_id] = func

    def shutdown(self):
        for kid in self.kernel_clients:
            self.kernel_clients[kid].stop_channels()
            self.kernel_manager.shutdown_kernel(kid, now=True)

        # Any remaining kernels that were not created for our pool should be shutdown
        kids = self.kernel_manager.list_kernel_ids()
        for kid in kids:
            self.kernel_manager.shutdown_kernel(kid, now=True)
