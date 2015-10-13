# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from setuptools import setup

setup(
    name='kernel_gateway',
    author='Jupyter Development Team',
    author_email='jupyter@googlegroups.com',
    url='http://jupyter.org',
    description='Headless Jupyter kernel provisioner and Websocket proxy',
    version='0.1',
    license='BSD',
    platforms=['Jupyter Notebook 4.x'],
    packages=[
        'kernel_gateway',
        'kernel_gateway.base',
        'kernel_gateway.services',
        'kernel_gateway.services.kernels',
        'kernel_gateway.services.kernelspecs',
    ],
    scripts=[
        'scripts/jupyter-kernelgateway'
    ],
    install_requires=[
        'jupyter_core>=4.0, <5.0',
        'jupyter_client>=4.0, <5.0',
        'notebook>=4.0, <5.0'
    ],
)
