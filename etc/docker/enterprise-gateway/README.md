This image adds support for [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster. It is currently built on jupyter/minimal-notebook as a base with Apache Spark 2.4.6 installed on top.

**Note: If you're looking for the YARN-based image of this name, it has been moved to [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/).**

# What it Gives You

- [Jupyter Enterprise Gateway](https://github.com/jupyter-server/enterprise_gateway)
- Python/R/Toree kernels that can be launched and distributed across a managed cluster.

# Basic Use

Pull this image, along with all of the elyra/kernel-\* images to each of your managed nodes. Although manual seeding of images across the cluster is not required, it is highly recommended since kernel startup times can timeout and image downloads can seriously undermine that window.

## Kubernetes

Enterprise Gateway is deployed into Kubernetes using [Helm](https://helm.sh/). See the [Kubernetes section of our Operator's Guide](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/operators/deploy-kubernetes.html) for further details.

## Docker Swarm

Download the [`docker-compose.yml`](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/docker/docker-compose.yml) file and make any necessary changes for your configuration. The compose file consists of three pieces, the Enterprise Gateway container itself, a proxy layer container, and a Docker network. We recommend that a volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

## Docker (Traditional)

Same instructions as for Docker Swarm using [`docker-compose.yml`](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/docker/docker-compose.yml). Please note that you can still run Enterprise Gateway as a traditional docker container within a Docker Swarm cluster, yet have the kernel containers launched as Docker Swarm services since how the kernels are launched is a function of their configured process proxy class.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
