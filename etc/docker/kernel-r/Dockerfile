# FIXME: This image is from April 8 (https://github.com/jupyter/docker-stacks/commit/8a1b90cbcba5355e6174a9fc24fe225813befe92)
# Attempts to use newer versions - within a couple months of 9/18/2018 - were encountering this issue:
# https://github.com/jupyter/docker-stacks/issues/679 - r-notebook kernel crashes because of png support
# Ubuntu 16.04.4 LTS - Xenial
FROM jupyter/r-notebook:8a1b90cbcba5

# Additional package needed by launcher, update IRkernel to fix kernel shutdown.
RUN Rscript --slave --no-save --no-restore-history \
        -e "install.packages('IRkernel', repos='http://cran.cnr.berkeley.edu/')" && \
    conda clean -tipsy && \
    fix-permissions $CONDA_DIR

# Install OOTB kernelspecs
COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

# Use our bootstrap file.  Kubernetes kernel yaml will reference this file
# as the image's CMD in the k8s context.
COPY bootstrap-kernel.sh /usr/local/bin/

# Switch back to root to create the kernel user
USER root

RUN chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/share/jupyter

USER jovyan

