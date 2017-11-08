Built on [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/), this image adds support 
for [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) to better demonstrate 
running Python, R and Scala kernels in YARN-cluster mode.  It can also demonstrate invoking remote kernels 
via ssh (although in loopback) in YARN-client mode.

# What it Gives You
* [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/) base
* [Jupyter Enterprise Gateway](https://github.com/jupyter-incubator/enterprise_gateway)
* Python/R/Toree kernels that target both remote YARN-cluster and YARN-client modes (loopback)
* `elyra` service user, with system users `jovyan`, `bob`, and `alice`.  The jovyan uid is `1000` to match other jupyter images.
* Password-less ssh for service user
* Users have HDFS folder setup at startup

# Basic Use


The following command can be used to start enterprise gateway ...

`docker run -it --rm -p 8888:8888 -p 8088:8088 -p 8042:8042 --net=host elyra/enterprise-gateway:0.7.0.dev0 --elyra`

To produce a general usage statement, the following can used...

`docker run elyra/enterprise-gateway:0.7.0.dev0 --help`

To run the enterprise-gateway container in an interactive mode, where enterprise gateway is manually started within the container, use the following...

`docker run -it --rm -p 8888:8888 -p 8088:8088 -p 8042:8042 --net=host elyra/enterprise-gateway:0.7.0.dev0 bash`

Once in the container, enterprise-gateway can be started using `/usr/local/share/jupyter/start-enterprise-gateway.sh`

**Tip:** YARN logs can be accessed via host system's public IP on port `8042` rather than using container's `hostname:8042`, while YARN Resource manager can be accessed via container's `hostname:8088` port.

# Recognized Environment Variables
The following environment variables are recognized during startup of the container and can be specified via docker's `-e` option.  These will rarely need to be modified.

`KG_IP`: specifies the IP address of enterprise gateway.  This should be a public IP.  Default = 0.0.0.0
`KG_PORT`: specifies the port that enterprise gateway is listening on.  This port should be mapped to a host port via `-p`. Default = 8888
`KG_PORT_RETRIES`: specifies the number of retries due to port conflicts that will be attempted.  Default = 0

`EG_REMOTE_HOSTS`: specifies a comma-separated lists of hostnames which can be used to run YARN-client kernels.  Default = <container-hostname>
`EG_YARN_ENDPOINT`: specifies the HTTP endpoint of the YARN Resource Manager.  Default = http://<hostname>:8088/ws/v1/cluster}
`EG_SSH_PORT=`: specifies the port of the SSH server.  This container is setup to use port `2122`.  This value should not be changed.  Default = 2122

`EG_ENABLE_TUNNELING`: specifies whether port tunneling will be used.  This value is currently `False` because ssh tunneling is 
not working unless Enterprise Gateway is run as the root user.  This can be accomplished by starting the container with `bash` 
as the command and running `start-enterprise-gateway.sh` directly (sans `sudo`).
