# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from tornado import ioloop

def teardown():
    """The test fixture appears to leak something on certain platforms that
    endlessly tries an async socket connect and fails after the tests end.
    As a stopgap, force a cleanup here.
    """
    ioloop.IOLoop.current().stop()
    ioloop.IOLoop.current().close(True)
