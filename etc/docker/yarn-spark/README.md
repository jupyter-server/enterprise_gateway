Built on [aghorbani/spark:2.1.0](https://hub.docker.com/r/aghorbani/spark/) that includes
[Hadoop](http://hadoop.apache.org/) (2.7.1) and [Spark](https://spark.apache.org/) (2.1.0), this image updates Java to 
1.8 (jdk-8u162), and adds Anaconda (4.4 with R) and [Toree](https://toree.apache.org/) (0.2.0) to act as a base image 
for [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).

# What it Gives You
* Hadoop 2.7.1 
* Spark 2.1.0
* Java 1.8 (jdk-8u162)
* Anaconda 4.4 (python 2.7.13) with R packages
* Toree 0.2.0-incubating
* `elyra` service user, with system users `jovyan`, `bob`, and `alice`.  The jovyan uid is `1000` to match other jupyter
 images.
* Password-less ssh for service user
* Users have HDFS folder setup at startup

# Basic Use
As of the 0.9.0 release of [Jupyter Enterprise Gateway](https://github.com/jupyter/enterprise_gateway/releases)
this image can be started as a separate YARN cluster to better demonstrate remote kernel capabilities.  See section 
[Dual Mode](https://hub.docker.com/r/elyra/enterprise-gateway/#dual_mode) on the enterprise-gateway page for command 
usage.
