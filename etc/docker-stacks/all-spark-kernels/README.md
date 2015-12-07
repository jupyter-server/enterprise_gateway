## Example Docker Stack

This Dockerfile shows how to extend the [jupyter/all-spark-notebook](https://hub.docker.com/r/jupyter/all-spark-notebook) image to make the kernel gateway the container entrypoint. The result listens on port 8888 on all interfaces within the container by default, but accepts additional command line args passed through `docker run`.

```
docker build -t jupyter-incubator/all-spark-kernels .
docker run -it --rm jupyter-incubator/all-spark-kernels --help-all
```

It's definitely not the smallest possible image--it has all the libs for working in the notebook itself like pandoc--but the Dockerfile definition is darn simple.