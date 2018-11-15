# FIXME: This image is from April 8 (https://github.com/jupyter/docker-stacks/commit/8a1b90cbcba5355e6174a9fc24fe225813befe92)
# Attempts to use newer versions - within a couple months of 9/18/2018 - were encountering this issue:
# https://github.com/jupyter/docker-stacks/issues/679 - r-notebook kernel crashes because of png support
FROM jupyter/r-notebook:8a1b90cbcba5

# Additional package needed by launcher, update IRkernel to fix kernel shutdown.
RUN conda install --quiet --yes \
    'r-argparser=0.4*' && \
     Rscript --slave --no-save --no-restore-history \
        -e "options(unzip = 'internal')" \
        -e "Sys.setenv(TAR = '/bin/tar')" \
        -e "devtools::install_github('IRkernel/IRkernel@0.8.14')" && \
    conda clean -tipsy && \
    fix-permissions $CONDA_DIR

# Install OOTB kernelspecs
COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

# Use our bootstrap file.  Kubernetes kernel yaml will reference this file
# as the image's CMD in the k8s context.
COPY bootstrap-kernel.sh /etc/

# Switch back to root to create the kernel user
USER root

RUN addgroup --system --gid 620 eg-kernel && adduser --system --uid 620 --gid 620 eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter

USER eg-kernel

