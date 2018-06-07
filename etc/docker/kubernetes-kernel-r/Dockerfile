FROM jupyter/r-notebook

# Additional package needed by launcher
RUN conda install --quiet --yes \
    'r-argparser=0.4*' && \
    conda clean -tipsy && \
    fix-permissions $CONDA_DIR

# Install OOTB kernelspecs
ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

# Use our bootstrap file.  Kubernetes kernel yaml will reference this file
# as the image's CMD in the k8s context.
COPY bootstrap-kernel.sh /etc/
