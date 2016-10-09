# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import sys
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

version_ns = {}
with open(os.path.join(here, 'kernel_gateway', '_version.py')) as f:
    exec(f.read(), {}, version_ns)

setup_args = dict(
    name='jupyter_kernel_gateway',
    author='Jupyter Development Team',
    author_email='jupyter@googlegroups.com',
    url='http://github.com/jupyter-incubator/kernel_gateway',
    description='A web server for spawning and communicating with Jupyter kernels',
    long_description='''\
Jupyter Kernel Gateway is a web server that supports different mechanisms for
spawning and communicating with Jupyter kernels, such as:

* A Jupyter Notebook server-compatible HTTP API used for requesting kernels
  and talking the `Jupyter kernel protocol <https://jupyter-client.readthedocs.io/en/latest/messaging.html>`_
  with the kernels over Websockets
* A HTTP API defined by annotated notebook cells that maps HTTP verbs and
  resources to code to execute on a kernel

The server launches kernels in its local process/filesystem space. It can be
containerized and scaled out using common technologies like
`tmpnb <https://github.com/jupyter/tmpnb>`_,
`Cloud Foundry <https://github.com/cloudfoundry>`_, and
`Kubernetes <http://kubernetes.io/>`_.
''',
    version=version_ns['__version__'],
    license='BSD',
    platforms="Linux, Mac OS X, Windows",
    keywords=['Interactive', 'Interpreter', 'Kernel', 'Web', 'Cloud'],
    packages=[
        'kernel_gateway',
        'kernel_gateway.base',
        'kernel_gateway.jupyter_websocket',
        'kernel_gateway.notebook_http',
        'kernel_gateway.notebook_http.cell',
        'kernel_gateway.notebook_http.swagger',
        'kernel_gateway.services',
        'kernel_gateway.services.activity',
        'kernel_gateway.services.kernels',
        'kernel_gateway.services.kernelspecs',
        'kernel_gateway.services.sessions',
    ],
    scripts=[
        'scripts/jupyter-kernelgateway'
    ],
    install_requires=[
        'jupyter_core>=4.0,<5.0',
        'jupyter_client>=4.2.0,<5.0',
        'notebook>=4.1.0,<5.0',
        'traitlets>=4.2.0,<5.0',
        'tornado>=4.2.0,<5.0',
        'requests>=2.7,<3.0'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3'
    ],
    include_package_data=True,
)

if 'setuptools' in sys.modules:
    # setupstools turns entrypoint scripts into executables on windows
    setup_args['entry_points'] = {
        'console_scripts': [
            'jupyter-kernelgateway = kernel_gateway:launch_instance'
        ]
    }
    # Don't bother installing the .py scripts if if we're using entrypoints
    setup_args.pop('scripts', None)

if __name__ == '__main__':
    setup(**setup_args)
