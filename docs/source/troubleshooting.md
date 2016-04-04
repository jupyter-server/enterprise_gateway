## Troubleshooting

### I can't access kernel gateway in my Docker container.

The kernel gateway server listens on port 8888 by default. Make sure this internal port is exposed on an external port when starting the container. For example, if you run:

```
docker run -it --rm -p 9000:8888 jupyter/minimal-kernel
```

you can access your kernel gateway on the IP address of your Docker host an port 9000.

### Kernel gateway raises an error when I use `notebook-http` mode.

The `notebook-http` mode publishes a web API defined by annotations and code in a notebook. Make sure you are specifying a path or URL of a notebook (`*.ipynb`) file when you launch the kernel gateway in this mode. Set the `--KernelGatewayApp.seed_uri` command line parameter or `KG_SEED_URI` environment variable to do so.