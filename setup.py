# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

version_ns = {}
with open(os.path.join(here, 'kernel_gateway', '_version.py')) as f:
    exec(f.read(), {}, version_ns)

setup(
    name='jupyter_kernel_gateway',
    author='Jupyter Development Team',
    author_email='jupyter@googlegroups.com',
    url='http://github.com/jupyter-incubator/kernel_gateway',
    description='Headless Jupyter kernel provisioner and Websocket proxy',
    version=version_ns['__version__'],
    license='BSD',
    platforms="Linux, Mac OS X, Windows",
    keywords=['Interactive', 'Interpreter', 'Kernel', 'Web', 'Cloud'],
    packages=[
        'kernel_gateway',
        'kernel_gateway.base',
        'kernel_gateway.services',
        'kernel_gateway.services.kernels',
        'kernel_gateway.services.kernelspecs',
        'kernel_gateway.services.notebooks',
    ],
    scripts=[
        'scripts/jupyter-kernelgateway'
    ],
    install_requires=[
        'jupyter_core>=4.0, <5.0',
        'jupyter_client>=4.0, <5.0',
        'notebook>=4.0, <5.0',
        'requests>=2.7, <3.0'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
)
