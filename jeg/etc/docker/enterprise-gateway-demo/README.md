Built on [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/), this image adds support for [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) to better demonstrate running Python, R and Scala kernels in YARN-cluster mode.

# What it Gives You

- [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/) base functionality
- [Jupyter Enterprise Gateway](https://github.com/jupyter-incubator/enterprise_gateway)
- Python/R/Toree kernels that target YARN-cluster mode

# Basic Use

**elyra/enterprise-gateway-demo** can be used as a combined YARN cluster in which the kernels run locally in YARN-cluster mode, or combined with a different instance of itself or an [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/) instance to more easily view that kernels are running remotely.

Prior to using either mode, we recommend you create a local docker network. This better isolates the container(s) and avoids port collisions that might come into play if you're using a gateway-enabled Notebook image on the same host. Here's a simple way to create a docker network...

`docker network create -d bridge jeg`

Once created, you just add `--net jeg` to the enterprise gateway run commands. Using `--net jeg` when creating instances of the gateway-enabled Notebook image are not necessary.

### Combined Mode

To run the image as a combined YARN/Enterprise Gateway instance, use the following command:

`docker run -itd --rm -p 8888:8888 -p 8088:8088 -p 8042:8042 --net=jeg elyra/enterprise-gateway-demo --elyra`

To produce a general usage statement, the following can used...

`docker run --rm elyra/enterprise-gateway-demo --help`

To run the enterprise-gateway-demo container in an interactive mode, where enterprise gateway is manually started within the container, use the following...

`docker run -it --rm -p 8888:8888 -p 8088:8088 -p 8042:8042 --net=jeg elyra/enterprise-gateway-demo /bin/bash`

Once in the container, enterprise-gateway-demo can be started using `sudo -u jovyan /usr/local/bin/start-enterprise-gateway.sh`

### Dual Mode

To get a better idea that kernels are running remote, you can invoke elyra/enterprise-gateway-demo to be the YARN master or use [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/).

To invoke the YARN master using elyra/demo-base...

`docker run -d --rm -h yarnmaster --name yarnmaster -p 8088:8088 -p 8042:8042 --net jeg elyra/demo-base --yarn`

or using elyra/enterprise-gateway-demo...

`docker run -d --rm -h yarnmaster --name yarnmaster -p 8088:8088 -p 8042:8042 --net jeg elyra/enterprise-gateway-demo --yarn`

Then, invoke elyra/enterprise-gateway-demo as purely an Enterprise Gateway host that indicates the name of its YARN master...

`docker run -it --rm -h elyra --name elyra -p 8888:8888 --net jeg -e YARN_HOST=yarnmaster elyra/enterprise-gateway-demo --elyra`

**Tip:** YARN logs can be accessed via host system's public IP on port `8042` rather than using container's `hostname:8042`, while YARN Resource manager can be accessed via container's `hostname:8088` port.

#### Bring Your Own Kernels

elyra/enterprise-gateway-demo sets up `JUPYTER_PATH` to point to `/tmp/byok`. This enables the ability to use docker volumes to mount your own set of kernelspec files. The kernelspecs must reside in a `kernels` directory. You can mount to the appropriate point in one of two ways via the docker `-v` option:

`-v <host_directory_containing_kernels_directory>:/tmp/byok`

or

`-v <host_kernels_directory>:/tmp/byok/kernels`

To confirm Enterprise Gateway is detecting the new kernelspecs, monitor the log (`docker logs -f <container_name>`) and issue a refresh from the gateway-enabled Notebook instance. Each refresh of the notebook's tree view triggers a refresh of the set of kernelspecs in Enterprise Gateway.

# Connecting a client notebook

You can use any gateway-enabled notebook server to hit the running docker container.

Note: Given the size of the enterprise-gateway-demo when combined with a YARN/Spark installation, it is recommended that you have at least 4GB of memory allocated for your docker image in order to run kernels (particularly the Toree/Scala kernel).

# Recognized Environment Variables

The following environment variables are recognized during startup of the container and can be specified via docker's `-e` option. These will rarely need to be modified.

`KG_IP`: specifies the IP address of enterprise gateway. This should be a public IP. Default = 0.0.0.0
`KG_PORT`: specifies the port that enterprise gateway is listening on. This port should be mapped to a host port via `-p`. Default = 8888
`KG_PORT_RETRIES`: specifies the number of retries due to port conflicts that will be attempted. Default = 0

`EG_REMOTE_HOSTS`: specifies a comma-separated lists of hostnames which can be used to run YARN-client kernels. Default = <container-hostname>
`EG_YARN_ENDPOINT`: specifies the HTTP endpoint of the YARN Resource Manager. Default = http://<hostname>:8088/ws/v1/cluster}
`EG_SSH_PORT=`: specifies the port of the SSH server. This container is setup to use port `2122`. This value should not be changed. Default = 2122

`EG_ENABLE_TUNNELING`: specifies whether port tunneling will be used. This value is currently `False` because ssh tunneling is not working unless Enterprise Gateway is run as the root user. This can be accomplished by starting the container with `bash` as the command and running `start-enterprise-gateway.sh` directly (sans `sudo`).

NOTE: Dual Mode functionality is only available in tags 0.9.0+
