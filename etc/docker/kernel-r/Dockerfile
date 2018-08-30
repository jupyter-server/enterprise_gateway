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

# Switch back to root to create the kernel user
USER root

RUN addgroup --system --gid 620 eg-kernel && adduser --system --uid 620 --gid 620 eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter

USER eg-kernel

