## Troubleshooting

### I can't access elyra in my Docker container.

The elyra server listens on port 8888 by default. Make sure this internal port is exposed on an 
external port when starting the container. For example, if you run:

```
docker run -it --rm -p 9000:8888 jupyter/minimal-kernel
```

you can access your kernel gateway on the IP address of your Docker host an port 9000.
