# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import sys
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

version_ns = {}
with open(os.path.join(here, 'enterprise_gateway', '_version.py')) as f:
    exec(f.read(), {}, version_ns)


version = version_ns['__version__']
github_url = 'http://github.com/SparkTC/enterprise_gateway'

setup_args = dict(
    name='jupyter_enterprise_gateway',
    author='Jupyter Development Team',
    author_email='jupyter@googlegroups.com',
    url=github_url,
    description='A web server for spawning and communicating with remote Jupyter kernels',
    long_description='''\
Jupyter Enterprise Gateway is a lightweight, multi-tenant, scalable and secure gateway that enables 
Jupyter Notebooks to share resources across an Apache Spark cluster.
''',
    version=version,
    download_url='%s/archive/%s.tar.gz' % (github_url, version),
    license='BSD',
    platforms="Linux, Mac OS X, Windows",
    keywords=['Interactive', 'Interpreter', 'Kernel', 'Web', 'Cloud'],
    packages=[
        'enterprise_gateway',
        'enterprise_gateway.services',
        'enterprise_gateway.services.kernels',
        'enterprise_gateway.services.kernelspecs',
        'enterprise_gateway.services.processproxies',
        'enterprise_gateway.services.sessions',
    ],
    scripts=[
        'scripts/jupyter-enterprisegateway'
    ],
    install_requires=[
        'jupyter_core>=4.0',
        'jupyter_client>=4.2.0',
        'notebook>=5.1.0,<6.0',
        'jupyter_kernel_gateway>=1.1.2',
        'traitlets>=4.2.0',
        'tornado>=4.2.0',
        'requests>=2.7,<3.0',
        'paramiko>=2.1.2',
        'yarn-api-client>=0.2.3'
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
            'jupyter-enterprisegateway = enterprise_gateway:launch_instance'
        ]
    }
    # Don't bother installing the .py scripts if if we're using entrypoints
    setup_args.pop('scripts', None)

if __name__ == '__main__':
    setup(**setup_args)
