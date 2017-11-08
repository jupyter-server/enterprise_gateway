This image adds the current master branch commit from [jupyter/kernel_gateway_demos/nb2kg](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg) on top of image [jupyter/minimal-notebook](https://github.com/jupyter/docker-stacks/tree/master/minimal-notebook) with tag [`fa77fe99579b`](https://github.com/jupyter/docker-stacks/commit/fa77fe99579b7bf79f6c6311e933c5118e0ec897).  It must continue to use that image tag until NB2KG's dependencies are expanded to include Notebook versions >= 5.0.0.

The tag of the elyra/nb2kg image corresponds to the commit hash within the [juptyer/kernel_gateway_demos](https://github.com/jupyter/kernel_gateway_demos) repo.

# What it Gives You
This image is configured to be run against [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) instances, although running against Jupyter Kernel Gateway instances should be fine.

# Basic Use
If the gateway server is remote, the following command can be used to direct NB2KG to that gateway...

`docker run -t --rm -p 8888:8888 -e GATEWAY_HOST=<gateway-hostname> -v <host-notebook-directory>:/home/jovyan/work elyra/nb2kg:<tag>`

This will configure the `KG_URL` to `http://${GATEWAY_HOST}:8888` with KERNEL_USERNAME set to `jovyan`.

# Alternative Uses
If you have an `elyra/enterprise-gateway` container running on the same host, or would like to run mulitple notebook instances against the same gateway, the ports of the NB2KG can be adjusted as follows:

`docker run -t --rm -p 9002:9002 -e NB_PORT=9002 -e GATEWAY_HOST=<gateway-hostname> -v <host-notebook-directory>:/home/jovyan/work elyra/nb2kg`

This maps port `9002` of the container to host port `9002` and instructs the container to use `9002` as the notebook port. The use of `-e NB_PORT` is only necessary if running on the same host as the gateway server. If that's not the, then only `-p 9002:8888` is required to support multiple NB2KG instances on the same host.

You can then run multiple notebook sessions on the same host by using different port mappings.  In addition, additional users can be emulated by setting the `KG_HTTP_USER` environment variable.

`docker run -t --rm -p 9003:8888 -e GATEWAY_HOST=<gateway-hostname> -e KG_HTTP_USER=bob -v <host-notebook-directory>:/home/jovyan/work elyra/nb2kg`

Here, the notebook will be available at port `9003` on the host and the `KERNEL_USERNAME` variable will be set to `bob`. Note that in this case, `-e NB_PORT` is not used since the gateway is not on the same host (in this example).
