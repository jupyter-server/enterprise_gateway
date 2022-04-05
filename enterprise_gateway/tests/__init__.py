# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from tornado import ioloop


def teardown():
    """The test fixture appears to leak something on certain platforms that
    endlessly tries an async socket connect and fails after the tests end.
    As a stopgap, force a cleanup here.
    """
    ioloop.IOLoop.current().stop()
    # Close is not necessary since process termination closes the loop.  This was causing intermittent
    # `Event loop is closed` exceptions.  These didn't affect the test resutls, but produced output that
    # was otherwise misleading noise.
    # ioloop.IOLoop.current().close(True)
