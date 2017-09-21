## Troubleshooting

### I can't access enterprise gateway in my Docker container.

The enterprise gateway server listens on port 8888 by default. Make sure this internal port is exposed 
on an external port when starting the container. For example, if you run:

```
docker run -it --rm -p 9000:8888 jupyter/enterprise-gateway
```

you can access your enterprise gateway on the IP address of your Docker host at port 9000.
