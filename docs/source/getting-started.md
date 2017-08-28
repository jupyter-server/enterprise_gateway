## Getting started

This document describes some of the basics of installing and running Jupyter Elyra.

### Using pip

We upload stable releases of Jupyter Elyra to PyPI. You can use `pip` to install the latest version along with its dependencies.

```bash
# install from pypi
pip install jupyter_elyra
```

Once installed, you can use the `jupyter` CLI to run the server.

```bash
# run it with default options
jupyter elyra
```

### Using conda

You can install Jupyter Elyra using conda as well.

```bash
conda install -c conda-forge jupyter_elyra
```

Once installed, you can use the `jupyter` CLI to run the server as shown above.

### Using a docker-stacks image

You can add the kernel gateway to any [docker-stacks](https://github.com/jupyter/docker-stacks) image by writing a Dockerfile patterned after the following example:

```bash
# start from the jupyter image with R, Python, and Scala (Apache Toree) kernels pre-installed
FROM jupyter/all-spark-notebook

# install elyra
RUN pip install jupyter_elyra

# run jupyter elyra on container start, not notebook server
EXPOSE 8888
CMD ["jupyter", "elyra", "--ip=0.0.0.0", "--port=8888"]
```

You can then build and run it.

```bash
docker build -t my/elyra .
docker run -it --rm -p 8888:8888 my/elyra
```
