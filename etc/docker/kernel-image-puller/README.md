This image is responsible for contacting the configured [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) instance within a Kubernetes or Docker Swarm cluster and pulling the set of kernel-based images to the node on which it is running.

# What it Gives You

- The ability to add new nodes and have kernel images on those nodes automatically populated.
- The ability to configure new kernelspecs that use different images and have those images pulled to all cluster nodes.

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

As part of that deployment, Kernel Image Puller (KIP) will be launched on each node. On Kubernetes, this will be accomplished via a DaemonSet. On Docker Swarm, it will be via a global service. KIP will then contact the configured Enterprise Gateway instance, fetch the set of in-use kernelspecs, parse out the image names and pull those images.

There are a few points of configuration listed below - all of which are environment variables (defaults in parenthesis).

- `KIP_GATEWAY_HOST` (`http://localhost:8888`)
- `KIP_INTERVAL` (`300`)
- `KIP_LOG_LEVEL` (`INFO`)
- `KIP_NUM_PULLERS` (`2`)
- `KIP_NUM_RETRIES` (`3`)
- `KIP_PULL_POLICY` (`IfNotPresent`)
- `KIP_IMAGE_FETCHER` (`KernelSpecsFetcher`)

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
