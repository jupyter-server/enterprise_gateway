# What this image Gives You

- Ubuntu base image : bionic
- Hadoop 2.7.7
- Apache Spark 2.4.6
- Java 1.8 runtime
- Mini-conda latest (python 3.8) with R packages
- Toree 0.4.0-incubating
- `jovyan` service user, with system users `elyra`, `bob`, and `alice`. The jovyan uid is `1000` to match other jupyter
  images.
- Password-less ssh for service user
- Users have HDFS folder setup at startup

# Basic Use

As of the 0.9.0 release of [Jupyter Enterprise Gateway](https://github.com/jupyter-server/enterprise_gateway/releases)
this image can be started as a separate YARN cluster to better demonstrate remote kernel capabilities. See section
[Dual Mode](https://hub.docker.com/r/elyra/enterprise-gateway/#dual_mode) on the enterprise-gateway page for command
usage.
