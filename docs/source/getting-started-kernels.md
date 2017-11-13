
## Supported Kernels

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

Please find below more details on specific kernels:

### Scala kernel (Apache Toree kernel)

We have tested the latest version of [Apache Toree](http://toree.apache.org/) with Scala 2.11 support.

Follow the steps below to install/configure the Toree kernel:


**Install Apache Toree**

``` Bash
# pip-install the Apache Toree installer
pip install https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc2/toree-pip/toree-0.2.0.tar.gz

# install a new Toree Scala kernel which will be updated with Enterprise Gateway's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

```

**Update the Apache Toree Kernelspecs**

we have provided sample kernel configurations and launchers as part of the release
[e.g. jupyter_enterprise_gateway_kernelspecs-0.6.0.tar.gz](https://github.com/jupyter-incubator/enterprise_gateway/releases/download/v0.6.0/jupyter_enterprise_gateway_kernelspecs-0.6.0.tar.gz).

Considering we would like to enable the Scala Kernel to run on YARN Cluster and Client mode
we would have to copy the sample configuration folder **spark_2.1_scala_yarn_client** and
**spark_2.1_scala_yarn_client** to where the Jupyter kernels are installed
(e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter-incubator/enterprise_gateway/releases/download/v0.6/enterprise_gateway_kernelspecs.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/ spark_2.1_scala_yarn_cluster/

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_scala_yarn_client/ spark_2.1_scala_yarn_client/

cp $KERNELS_FOLDER/spark_2.1_scala/lib/*.jar  $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/lib
```

For more information about the Scala kernel, please visit the [Apache Toree](http://toree.apache.org/) page.


### Installing support for Python (IPython kernel)

The IPython kernel comes pre-installed with Anaconda and we have tested with its default version of 
[iPython kernel](http://ipython.readthedocs.io/en/stable/).


**Update the iPython Kernelspecs**

we have provided sample kernel configurations and launchers as part of the release
[e.g. jupyter_enterprise_gateway_kernelspecs-0.6.0.tar.gz](https://github.com/jupyter-incubator/enterprise_gateway/releases/download/v0.6.0/jupyter_enterprise_gateway_kernelspecs-0.6.0.tar.gz).

Considering we would like to enable the iPython kernel to run on YARN Cluster and Client mode
we would have to copy the sample configuration folder **spark_2.1_python_yarn_client** and
**spark_2.1_python_yarn_client** to where the Jupyter kernels are installed
(e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter-incubator/enterprise_gateway/releases/download/v0.6/enterprise_gateway_kernelspecs.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_python_yarn_cluster/ spark_2.1_python_yarn_cluster/

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_python_yarn_client/ spark_2.1_python_yarn_client/
```

For more information about the iPython kernel, please visit the [iPython kernel](http://ipython.readthedocs.io/en/stable/) page.

### Installing support for R (IRkernel)


**Install iRKernel**

Perform the following steps on Jupyter Enterprise Gateway hosting system as well as all YARN workers

```Bash
conda install --yes --quiet -c r r-essentials r-irkernel
Rscript -e 'install.packages("argparser", repos="https://cran.rstudio.com")'


# Create an R-script to run and install packages
cat <<'EOF' > install_packages.R
install.packages(c('repr', 'IRdisplay', 'evaluate', 'git2r', 'crayon', 'pbdZMQ',
                   'devtools', 'uuid', 'digest', 'RCurl', 'argparser'),
                   repos='http://cran.rstudio.com/')
devtools::install_github('IRkernel/IRkernel')
IRkernel::installspec(user = FALSE)
EOF

# run the package install script
$ANACONDA_HOME/bin/Rscript install_packages.R

# OPTIONAL: check the installed R packages
ls $ANACONDA_HOME/lib/R/library
```
