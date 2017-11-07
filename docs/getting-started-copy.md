
#### Installing support for Scala (Apache Toree kernel)

We have tested the latest version of Apache Toree for Scala 2.11 support, and to enable that support, please do the following steps:


* Install Apache Toree

``` Bash
# pip-install the Apache Toree installer
pip install https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc1/toree-pip/toree-0.2.0.tar.gz

# install a new Toree Scala kernel which will be updated with Enterprise Gateway's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

```

* Update the Apache Toree Kernelspecs

We have provided some customized kernelspecs as part of the Jupyter Enterprise Gateway releases.
These kernelspecs come pre-configured with YARN client and/or cluster mode. Please use the steps below
as an example on how to update/customize your kernelspecs:

``` Bash
wget https://github.com/jupyter-incubator/enterprise_gateway/releases/download/v0.6/enterprise_gateway_kernelspecs.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/ spark_2.1_scala_yarn_cluster/

cp $KERNELS_FOLDER/spark_2.1_scala/lib/*.jar  $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/lib
```

#### Installing support for Python (IPython kernel)

The IPython kernel comes pre-installed.

#### Installing support for R (IRkernel)

```Bash
# Perform the following steps on Jupyter Enterprise Gateway hosting system as well as all YARN workers

yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y git openssl-devel.x86_64 libcurl-devel.x86_64

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

Next copy the R kernelspecs to all YARN workers
[ ENTERPRISE_GATEWAY ] is the root directory of the JEG github repository
cp -r [ ENTERPRISE_GATEWAY ]/etc/kernelspecs/spark_2.1_R* /usr/local/share/jupyter/kernels/
cp -r [ ENTERPRISE_GATEWAY ]/etc/kernel-launchers/R/scripts /usr/local/share/jupyter/kernels/spark_2.1_R_yarn_client/
cp -r [ ENTERPRISE_GATEWAY ]/etc/kernel-launchers/R/scripts /usr/local/share/jupyter/kernels/spark_2.1_R_yarn_cluster/

```

### Installing Required Packages on YARN Worker Nodes
To support IPython and R kernels, run the following commands on all YARN worker nodes.

###### IPython Kernels
```Bash
yum -y install "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y python2-pip.noarch

# upgrade pip
python -m pip install --upgrade --force pip

# install IPython kernel packages
pip install ipykernel 'ipython<6.0'

# OPTIONAL: check installed packages
pip list | grep -E "ipython|ipykernel"
```

###### R Kernels
```Bash
yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y R git openssl-devel.x86_64 libcurl-devel.x86_64

# create a install script
cat <<'EOF' > install_packages.R
install.packages('git2r', repos='http://cran.rstudio.com/')
install.packages('devtools', repos='http://cran.rstudio.com/')
install.packages('RCurl', repos='http://cran.rstudio.com/')
library('devtools')
install_github('IRkernel/repr', repos='http://cran.rstudio.com/')
install_github('IRkernel/IRdisplay', repos='http://cran.rstudio.com/')
install_github('IRkernel/IRkernel', repos='http://cran.rstudio.com/')
EOF

# run the package install script in the background
R CMD BATCH install_packages.R &

# OPTIONAL: tail the progress of the installation
tail -F install_packages.Rout

# OPTIONAL: check the installed packages
ls /usr/lib64/R/library/
```



### Adding modes of distribution
By default, without kernelspec modifications, all kernels run local to Enterprise Gateway.  This is
what is referred to as *LocalProcessProxy* mode.  Enterprise Gateway provides two additional modes
out of the box, which are reflected in modified kernelspec files.  These modes are *YarnClusterProcessProxy*
and *DistributedProcessProxy*.  The [system architecture](system-architecture.html) page provides more
details regarding process proxies.

##### YarnClusterProcessProxy
YarnClusterProcessProxy mode launches the kernel as a *managed resource* within YARN as noted above.
This launch mode requires that the command-line option `--EnterpriseGatewayApp.yarn_endpoint` be provided
or the environment variable `EG_YARN_ENDPOINT` be defined.  If neither value exists, the default
value of `http://localhost:8088/ws/v1/cluster` will be used.

##### DistributedProcessProxy
DistributedProcessProxy provides for a simple, round-robin remoting mechanism where each successive
kernel is launched on a different host.  It requires that **each of the kernelspec files reside in
the same path on each node and that password-less ssh has been established between nodes**.

When launched, the kernel runs as a YARN *client* - meaning that the kernel process itself is
not managed by the YARN resource manager.  This mode allows for the distribution of kernel
(spark driver) processes across the cluster.

To use this form of distribution, the command-line option `--EnterpriseGatewayApp.remote_hosts=`
should be set.  It should be noted that this command-line option is a **list**, so values are
indicated via bracketed strings: `['host1','host2','host3']`.  These values can also be set via
the environment variable `EG_REMOTE_HOSTS`, in which case a simple comma-separated value is
sufficient.  If neither value is provided and DistributedProcessProxy kernels are invoked,
Enterprise Gateway defaults this option to `localhost`.
