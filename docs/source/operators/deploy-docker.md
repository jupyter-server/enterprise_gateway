# Docker and Docker Swarm deployments

This section describes how to deploy Enterprise Gateway into an existing Docker or Docker Swarm cluster. The two deployments are nearly identical and any differences will be noted.

The base Enterprise Gateway image is [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) and can be found in the Enterprise Gateway dockerhub organization [elyra](https://hub.docker.com/r/elyra/), along with other images. See [Docker Images](../contributors/docker.md) for image details.

The following sample kernelspecs are currently available on Docker and Docker Swarm deployments:

- R_docker
- python_docker
- python_tf_docker
- python_tf_gpu_docker
- scala_docker

## Docker Swarm deployment

Enterprise Gateway manifests itself as a Docker Swarm service. It is identified by the name `enterprise-gateway` within the cluster. In addition, all objects related to Enterprise Gateway, including kernel instances, have a label of `app=enterprise-gateway` applied.

The current deployment uses a compose stack definition, [docker-compose.yml](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/docker/docker-compose.yml) which creates an overlay network intended for use solely by Enterprise Gateway and any kernel-based services it launches.

To deploy the stack to a swarm cluster from a manager node, use:

```bash
docker stack deploy -c docker-compose.yml enterprise-gateway
```

More information about deploying and managing stacks can be found [here](https://docs.docker.com/engine/reference/commandline/stack_deploy/).

Since Swarm's support for session-based affinity has not been investigated at this time, the deployment script configures a single replica. Once session affinity is available, the number of replicas can be increased.

```{note}
Once session affinity has been figured out, we can (theretically) configure Enterprise Gateway for high availability by increasing the replicas.  However, HA support cannot be fully realized until Enterprise Gateway has finalized its persistent sessions functionality.
```

## Docker deployment

An alternative deployment of Enterprise Gateway in docker environments is to deploy Enterprise Gateway as a traditional docker container. This can be accomplished via the [docker-compose.yml](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/docker/docker-compose.yml) file. However, keep in mind that in choosing this deployment approach, one loses leveraging swarm's monitoring & restart capabilities. That said, choosing this approach does not preclude one from leveraging swarm's scheduling capabilities for launching kernels. As noted below, kernel instances, and how they manifest as docker-based entities (i.e., a swarm service or a docker container), is purely a function of the process proxy class to which they're associated.

To start the stack using compose:

```bash
docker-compose up
```

The documentation for managing a compose stack can be found [here](https://docs.docker.com/compose/overview/).

## Kernelspec Modifications

One of the more common areas of customization we see occur within the kernelspec files located in /usr/local/share/jupyter/kernels. To customize the kernel definitions, the kernels directory can be exposed as a mounted volume thereby making it available to all containers within the swarm cluster.

As an example, we have included the necessary commands to mount these volumes, both in the deployment script and in the [launch_docker.py](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/docker/scripts/launch_docker.py) file used to launch docker-based kernels. By default, these references are commented out as they require the system administrator to ensure the directories are available throughout the cluster.

Note that because the kernel launch script, [launch_docker.py](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/docker/scripts/launch_docker.py), resides in the kernelspecs hierarchy, updates or modifications to docker-based kernel instances can now also take place.

## Docker and Docker Swarm Kernel Instances

Enterprise Gateway currently supports launching of _vanilla_ (i.e., non-spark) kernels within a Docker Swarm cluster. When kernels are launched, Enterprise Gateway is responsible for creating the appropriate entity. The kind of entity created is a function of the corresponding process proxy class.

When the process proxy class is `DockerSwarmProcessProxy` the `launch_docker.py` script will create a Docker Swarm _service_. This service uses a restart policy of `none` meaning that it's configured to go away upon failures or completion. In addition, because the kernel is launched as a swarm service, the kernel can "land" on any node of the cluster.

When the process proxy class is `DockerProcessProxy` the `launch_docker.py` script will create a traditional docker _container_. As a result, the kernel will always reside on the same host as the corresponding Enterprise Gateway.

Items worth noting:

1. The Swarm service or Docker container name will be composed of the launching username (`KERNEL_USERNAME`) and kernel-id.
1. The service/container will have 3 labels applied: "kernel_id=<kernel-id>", "component=kernel", and "app=enterprise-gateway" - similar to Kubernetes.
1. The service/container will be launched within the same docker network as Enterprise Gateway.

## DockerSwarmProcessProxy

To indicate that a given kernel should be launched as a Docker Swarm service into a swarm cluster, the kernel.json file's `metadata` stanza must include a `process_proxy` stanza indicating a `class_name:` of `DockerSwarmProcessProxy`. This ensures the appropriate lifecycle management will take place relative to a Docker Swarm environment.

Along with the `class_name:` entry, this process proxy stanza should also include a proxy configuration stanza which specifies the docker image to associate with the kernel's service container. If this entry is not provided, the Enterprise Gateway implementation will use a default entry of `elyra/kernel-py:VERSION`. In either case, this value is made available to the rest of the parameters used to launch the kernel by way of an environment variable: `KERNEL_IMAGE`.

```{note}
_The use of `VERSION` in docker image tags is a placeholder for the appropriate version-related image tag.  When kernelspecs are built via the Enterprise Gateway Makefile, `VERSION` is replaced with the appropriate version denoting the target release.  A full list of available image tags can be found in the dockerhub repository corresponding to each image._
```

```json
{
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.docker_swarm.DockerSwarmProcessProxy",
      "config": {
        "image_name": "elyra/kernel-py:VERSION"
      }
    }
  }
}
```

As always, kernels are launched by virtue of the `argv:` stanza in their respective kernel.json files. However, when launching kernels in a docker environment, what gets invoked isn't the kernel's launcher, but, instead, a python script that is responsible for using the [Docker Python API](https://docker-py.readthedocs.io/en/stable/) to create the corresponding instance.

```json
{
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_docker/scripts/launch_docker.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

## DockerProcessProxy

Running containers in Docker Swarm versus traditional Docker are different enough to warrant having separate process proxy implementations. As a result, the kernel.json file could reference the `DockerProcessProxy` class and, accordingly, a traditional docker container (as opposed to a swarm _service_) will be created. The rest of the kernel.json file, image name, argv stanza, etc. is identical.

```json
{
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.docker_swarm.DockerProcessProxy",
      "config": {
        "image_name": "elyra/kernel-py:VERSION"
      }
    }
  },
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_docker/scripts/launch_docker.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

Upon invocation, the invoked process proxy will set a "docker mode" environment variable (`EG_DOCKER_MODE`) to either `swarm` or `docker`, depending on the process proxy instance, that the `launch_docker.py` script uses to determine whether a _service_ or _container_ should be created, respectively.

It should be noted that each of these forms of process proxy usage does **NOT** need to match to the way in which the Enterprise Gateway instance was deployed. For example, if Enterprise Gateway was deployed as a Docker Swarm service and a `DockerProcessProxy` is used, that corresponding kernel will be launched as a traditional docker container and will reside on the same host as wherever the Enterprise Gateway (swarm) service is running. Similarly, if Enterprise Gateway was deployed using standard Docker container and a `DockerSwarmProcessProxy` is used (and assuming a swarm configuration is present), that corresponding kernel will be launched as a docker swarm service and will reside on whatever host the Docker Swarm scheduler decides is best. That is, the kernel container's lifecycle will be managed by the corresponding process proxy and the Enterprise Gateway's deployment has no bearing.
