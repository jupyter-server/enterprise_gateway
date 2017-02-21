# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel pools that track and delegate to kernels."""

from jupyter_client.session import Session

from tornado.locks import Semaphore
from tornado import gen


class KernelPool(object):
    """Spawns a pool of kernels.

    The kernel pool is responsible for clean up and shutdown of individual
    kernels that are members of the pool.

    Parameters
    ----------
    prespawn_count
        Number of kernels to spawn immediately
    kernel_manager
        Kernel manager instance
    """
    def __init__(self, prespawn_count, kernel_manager):
        self.kernel_manager = kernel_manager
        # Make sure we've got a int
        if not prespawn_count:
            prespawn_count = 0
        for _ in range(prespawn_count):
            self.kernel_manager.start_seeded_kernel()

    def shutdown(self):
        """Shuts down all running kernels."""
        kids = self.kernel_manager.list_kernel_ids()
        for kid in kids:
            self.kernel_manager.shutdown_kernel(kid, now=True)

class ManagedKernelPool(KernelPool):
    """Spawns a pool of kernels that are treated as identical delegates for
    future requests.

    Manages access to individual kernels using a borrower/lender pattern.
    Cleans them all up when shut down.

    Parameters
    ----------
    prespawn_count
        Number of kernels to spawn immediately
    kernel_manager
        Kernel manager instance

    Attributes
    ----------
    kernel_clients : dict
        Map of kernel IDs to client instances for communicating with them
    on_recv_funcs : dict
        Map of kernel IDs to iopub callback functions
    kernel_pool : list
        List of available delegate kernel IDs
    kernel_semaphore : tornado.locks.Semaphore
        Semaphore that controls access to the kernel pool
    """
    def __init__(self, prespawn_count, kernel_manager):
        # Make sure there's at least one kernel as a delegate
        if not prespawn_count:
            prespawn_count = 1

        super(ManagedKernelPool, self).__init__(prespawn_count, kernel_manager)

        self.kernel_clients = {}
        self.on_recv_funcs = {}
        self.kernel_pool = []

        kernel_ids = self.kernel_manager.list_kernel_ids()
        self.kernel_semaphore = Semaphore(len(kernel_ids))

        # Create clients and iopub handlers for prespawned kernels
        for kernel_id in kernel_ids:
            self.kernel_clients[kernel_id] = kernel_manager.get_kernel(kernel_id).client()
            self.kernel_pool.append(kernel_id)
            iopub = self.kernel_manager.connect_iopub(kernel_id)
            iopub.on_recv(self.create_on_reply(kernel_id))

    @gen.coroutine
    def acquire(self):
        """Gets a kernel client and removes it from the available pool of
        clients.

        Returns
        -------
        tuple
            Kernel client instance, kernel ID
        """
        yield self.kernel_semaphore.acquire()
        kernel_id = self.kernel_pool[0]
        del self.kernel_pool[0]
        raise gen.Return((self.kernel_clients[kernel_id], kernel_id))

    def release(self, kernel_id):
        """Puts a kernel back into the pool of kernels available to handle
        requests.

        Parameters
        ----------
        kernel_id : str
            Kernel to return to the pool
        """
        self.kernel_pool.append(kernel_id)
        self.kernel_semaphore.release()

    def _on_reply(self, kernel_id, session, msg_list):
        """Invokes the iopub callback registered for the `kernel_id` and passes
        it a deserialized list of kernel messages.

        Parameters
        ----------
        kernel_id : str
            Kernel that sent the reply
        msg_list : list
            List of 0mq messages
        """
        idents, msg_list = session.feed_identities(msg_list)
        msg = session.deserialize(msg_list)
        self.on_recv_funcs[kernel_id](msg)

    def create_on_reply(self, kernel_id):
        """Creates an anonymous function to handle reply messages from the
        kernel.

        Parameters
        ----------
        kernel_id
            Kernel to listen to

        Returns
        -------
        function
            Callback function taking a kernel ID and 0mq message list
        """
        kernel = self.kernel_clients[kernel_id]
        session = Session(
            config=kernel.session.config,
            key=kernel.session.key,
        )
        return lambda msg_list: self._on_reply(kernel_id, session, msg_list)

    def on_recv(self, kernel_id, func):
        """Registers a callback function for iopub messages from a particular
        kernel.

        This is needed to avoid having multiple callbacks per kernel client.

        Parameters
        ----------
        kernel_id
            Kernel from which to receive iopub messages
        func
            Callback function to use for kernel iopub messages
        """
        self.on_recv_funcs[kernel_id] = func

    def shutdown(self):
        """Shuts down all kernels and their clients.
        """
        for kid in self.kernel_clients:
            self.kernel_clients[kid].stop_channels()
            self.kernel_manager.shutdown_kernel(kid, now=True)

        # Any remaining kernels that were not created for our pool should be shutdown
        super(ManagedKernelPool, self).shutdown()
