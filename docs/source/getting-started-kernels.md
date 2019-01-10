
## Supported Kernels

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

We provide sample kernel configuration and launcher tar files as part of [each release](https://github.com/jupyter/enterprise_gateway/releases)
(e.g. [jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev0/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz))
that can be extracted and modified to fit your configuration.

Please find below more details on specific kernels:

### Scala kernel (Apache Toree kernel)

We have tested the latest version of [Apache Toree](http://toree.apache.org/) with Scala 2.11 support.

Follow the steps below to install/configure the Toree kernel:


**Install Apache Toree**

``` Bash
# pip-install the Apache Toree installer
pip install https://dist.apache.org/repos/dist/release/incubator/toree/0.3.0-incubating/toree-pip/toree-0.3.0.tar.gz

# install a new Toree Scala kernel which will be updated with Enterprise Gateway's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.x" --interpreters="Scala"

```

**Update the Apache Toree Kernelspecs**

Considering we would like to enable the Scala Kernel to run on YARN Cluster and Client mode
we would have to copy the sample configuration folder **spark_scala_yarn_client** and
**spark_scala_yarn_cluster** to where the Jupyter kernels are installed
(e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev0/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_scala_yarn_cluster/ spark_scala_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_scala_yarn_client/ spark_scala_yarn_client/

cp $KERNELS_FOLDER/spark_scala/lib/*.jar  $KERNELS_FOLDER/spark_scala_yarn_cluster/lib
```

For more information about the Scala kernel, please visit the [Apache Toree](http://toree.apache.org/) page.


### Installing support for Python (IPython kernel)

The IPython kernel comes pre-installed with Anaconda and we have tested with its default version of
[IPython kernel](http://ipython.readthedocs.io/en/stable/).


**Update the IPython Kernelspecs**

Considering we would like to enable the IPython kernel to run on YARN Cluster and Client mode
we would have to copy the sample configuration folder **spark_python_yarn_client** and
**spark_python_yarn_client** to where the Jupyter kernels are installed
(e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev0/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_cluster/ spark_python_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_client/ spark_python_yarn_client/
```

For more information about the IPython kernel, please visit the [IPython kernel](http://ipython.readthedocs.io/en/stable/) page.

### Installing support for R (IRkernel)


**Install iRKernel**

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
**Update the iR Kernelspecs**

Considering we would like to enable the iR kernel to run on YARN Cluster and Client mode
we would have to copy the sample configuration folder **spark_R_yarn_client** and
**spark_R_yarn_client** to where the Jupyter kernels are installed
(e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev0/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_R_yarn_cluster/ spark_R_yarn_cluster/

tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev0.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_R_yarn_client/ spark_R_yarn_client/
```

For more information about the iR kernel, please visit the [iR kernel](https://irkernel.github.io/) page.
