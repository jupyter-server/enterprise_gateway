
## Supported Kernels

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

We provide sample kernel configuration and launcher tar files as part of [each release](https://github.com/jupyter/enterprise_gateway/releases) (e.g. [jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0rc1/jupyter_enterprise_gateway_kernelspecs-2.0.0rc1.tar.gz)) that can be extracted and modified to fit your configuration.

Please find below more details on the specific kernels supported by Enterprise Gateway.  In each of the sections we set the `KERNELS_FOLDER` to `/usr/local/share/jupyter/kernels` since that's one of the default locations searched by the Jupyter framework.  Co-locating kernelspecs hierarchies in the same parent folder is recommended, although not required.

For information about how to build your own kernel-based docker image for use by Enterprise Gateway see [Custom kernel images](docker.html#custom-kernel-images).

You will find in this documentation details on how to install the kernels on various orchestrators:

+ [Hadoop YARN client mode](kern-yarn-client-mode.html)
+ [Hadoop YARN cluster mode](kern-yarn-cluster-mode.html)
+ [Kubernetes](kern-kubernetes.html)
+ [Docker](kern-docker.html)
+ [IBM Conductor](kern-conductor.html)

### Scala kernel (Apache Toree kernel)

We have tested the latest version of [Apache Toree](http://toree.apache.org/) with Scala 2.11 support.  Please note that the Apache Toree kernel is now bundled in the kernelspecs tar file for each of the Scala kernelspecs provided by Enterprise Gateway.

Follow the steps below to install/configure the Toree kernel:

**Install Apache Toree Kernelspecs**

Considering we would like to enable the Scala Kernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_scala_yarn_client** and **spark_scala_yarn_cluster** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0rc1/jupyter_enterprise_gateway_kernelspecs-2.0.0rc1.tar.gz

KERNELS_FOLDER=/usr/local/share/jupyter/kernels

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_scala_yarn_cluster/ spark_scala_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_scala_yarn_client/ spark_scala_yarn_client/

```

For more information about the Scala kernel, please visit the [Apache Toree](http://toree.apache.org/) page.

### Installing support for Python (IPython kernel)

The IPython kernel comes pre-installed with Anaconda and we have tested with its default version of [IPython kernel](http://ipython.readthedocs.io/en/stable/).

**Update the IPython Kernelspecs**

Considering we would like to enable the IPython kernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_python_yarn_client** and **spark_python_yarn_client** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0rc1/jupyter_enterprise_gateway_kernelspecs-2.0.0rc1.tar.gz

KERNELS_FOLDER=/usr/local/share/jupyter/kernels

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_cluster/ spark_python_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_client/ spark_python_yarn_client/
```

For more information about the IPython kernel, please visit the [IPython kernel](http://ipython.readthedocs.io/en/stable/) page.

### Installing support for R (IRkernel)

**Install IRkernel**

Perform the following steps on Jupyter Enterprise Gateway hosting system as well as all YARN workers

```Bash
conda install --yes --quiet -c r r-essentials r-irkernel r-argparse

# Create an R-script to run and install packages and update IRkernel
cat <<'EOF' > install_packages.R
install.packages(c('repr', 'IRdisplay', 'evaluate', 'git2r', 'crayon', 'pbdZMQ',
                   'devtools', 'uuid', 'digest', 'RCurl', 'curl', 'argparse'),
                   repos='http://cran.rstudio.com/')
devtools::install_github('IRkernel/IRkernel@0.8.14')
IRkernel::installspec(user = FALSE)
EOF

# run the package install script
$ANACONDA_HOME/bin/Rscript install_packages.R

# OPTIONAL: check the installed R packages
ls $ANACONDA_HOME/lib/R/library
```

**Update the IRkernel Kernelspecs**

Considering we would like to enable the IRkernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_R_yarn_client** and **spark_R_yarn_client** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0rc1/jupyter_enterprise_gateway_kernelspecs-2.0.0rc1.tar.gz

KERNELS_FOLDER=/usr/local/share/jupyter/kernels

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_R_yarn_cluster/ spark_R_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_R_yarn_client/ spark_R_yarn_client/
```

For more information about the iR kernel, please visit the [IRkernel](https://irkernel.github.io/) page.
