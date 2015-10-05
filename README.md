# Jupyter Kernel Gateway

A [JupyterApp](https://github.com/jupyter/jupyter_core/blob/master/jupyter_core/application.py) that implements a `/api/kernels` resource similar to the one found in [Jupyter Notebook](https://github.com/jupyter/notebook). Delegates launching of kernels to a configured kernel provisioner. Intended to be accessed by [jupyter-js-services](https://github.com/jupyter/jupyter-js-services) and similar clients.

TODO

[X] test fixture
[X] setup.py
[ ] define delegate API for kernel provisioner
[ ] implement local docker delegate
[ ] implement at least one remote delegate
