# Installing supported kernels (common)

Enterprise Gateway includes kernel specifications that support the following kernels:

- IPython kernel (Python)
- Apache Toree (Scala)
- IRKernel (R)

Refer to the following for instructions on installing the respective kernels. For cluster-based environments, these steps should be performed on each applicable node of the cluster, unless noted otherwise.

## Python Kernel (IPython kernel)

The IPython kernel comes pre-installed with Anaconda and we have tested with its default version of [IPython kernel](https://ipython.readthedocs.io/en/stable/).

```{admonition} Important!
:class: warning
For proper operation across the cluster, the Python kernel package (not the kernel specification) must be installed on every node of the cluster available to Enterprise Gateway.  For example, run `pip install ipykernel` on each applicable node.

This step is also required for the IRkernel (see below).  However, it is **not** required for the Scala (Apache Toree) Kernel as that can be expressed as a dependency in the `spark_submit` invocation.
```

## Scala Kernel (Apache Toree)

We have tested the latest version of [Apache Toree](https://toree.apache.org/) with Scala 2.11 support. Please note that the Apache Toree kernel is now bundled in the kernelspecs tar file for each of the Scala kernelspecs provided by Enterprise Gateway.

The sample kernel specifications included in Enterprise Gateway include the necessary Apach Toree libraries so its installation is not necessary. In addition, because Apache Toree targets Spark installations, its distribution can be achieved via `spark-submit` and its installation is not necessary on worker nodes - except for [distributed deployments](deploy-distributed.md).

## R Kernel (IRkernel)

Perform the following steps on Jupyter Enterprise Gateway hosting system as well as all worker nodes. Please refer to the [IRKernel documentation](https://irkernel.github.io/) for further details.

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
