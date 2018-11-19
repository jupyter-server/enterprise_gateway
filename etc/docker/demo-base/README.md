# What this image Gives You
* CentOS base image : latest
* Hadoop 2.7.7 with 64-bit native libraries
* Apache Spark 2.3.1
* Java 1.8 runtime
* Mini-conda 4.5.11 (python 2.7.15) with R packages
* Toree 0.3.0-incubating
* `jovyan` service user, with system users `elyra`, `bob`, and `alice`.  The jovyan uid is `1000` to match other jupyter
 images.
* Password-less ssh for service user
* Users have HDFS folder setup at startup

# Basic Use
As of the 0.9.0 release of [Jupyter Enterprise Gateway](https://github.com/jupyter/enterprise_gateway/releases)
this image can be started as a separate YARN cluster to better demonstrate remote kernel capabilities.  See section 
[Dual Mode](https://hub.docker.com/r/elyra/enterprise-gateway/#dual_mode) on the enterprise-gateway page for command 
usage.
