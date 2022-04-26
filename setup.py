# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import sys

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

v = sys.version_info
if v[:2] < (3, 7):
    error = "ERROR: Jupyter Enterprise Gateway requires Python version 3.7 or above."
    print(error, file=sys.stderr)
    sys.exit(1)

version_ns = {}
with open(os.path.join(here, "enterprise_gateway", "_version.py")) as f:
    exec(f.read(), {}, version_ns)

setup_args = dict(
    name="jupyter_enterprise_gateway",
    author="Jupyter Development Team",
    author_email="jupyter@googlegroups.com",
    url="http://github.com/jupyter/enterprise_gateway",
    description="A web server for spawning and communicating with remote Jupyter kernels",
    long_description="""\
A lightweight, multi-tenant, scalable and secure gateway that enables
Jupyter Notebooks to share resources across distributed clusters such as
Apache Spark, Kubernetes and others..
""",
    long_description_content_type="text/plain",
    version=version_ns["__version__"],
    license="BSD",
    platforms="Linux, Mac OS X, Windows",
    keywords=["Interactive", "Interpreter", "Kernel", "Web", "Cloud"],
    packages=[
        "enterprise_gateway",
        "enterprise_gateway.base",
        "enterprise_gateway.client",
        "enterprise_gateway.services",
        "enterprise_gateway.services.api",
        "enterprise_gateway.services.kernels",
        "enterprise_gateway.services.kernelspecs",
        "enterprise_gateway.services.processproxies",
        "enterprise_gateway.services.sessions",
    ],
    install_requires=[
        "docker>=3.5.0",
        "future",
        "jinja2>=3.1",
        "jupyter_client~=6.1",
        "jupyter_core>=4.6.0",
        "kubernetes>=4.0.0",
        "jupyter_server>=1.2",
        "paramiko>=2.1.2",
        "pexpect>=4.2.0",
        "pycryptodomex>=3.9.7",
        "pyzmq>=17.0.0",
        "requests~=2.7",
        "tornado>=6.1",
        "traitlets>=4.3.3",
        "watchdog>=2.1.3",
        "yarn-api-client>=1.0",
    ],
    extras_require={
        "test": [
            "coverage",
            "pytest",
            "pytest-tornasync",
            "ipykernel",
            "pre-commit",
            "websocket-client",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    include_package_data=True,
)

if "setuptools" in sys.modules:
    # setupstools turns entrypoint scripts into executables on windows
    setup_args["entry_points"] = {
        "console_scripts": [
            "jupyter-enterprisegateway = enterprise_gateway.enterprisegatewayapp:launch_instance"
        ]
    }
    # Don't bother installing the .py scripts if if we're using entrypoints
    setup_args.pop("scripts", None)

if __name__ == "__main__":
    setup(**setup_args)
