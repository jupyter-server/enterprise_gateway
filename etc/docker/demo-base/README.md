# What this image Gives You

- Debian-based miniconda image (`continuumio/miniconda3:24.1.2-0`)
- Hadoop `3.3.1`
- Apache Spark `3.2.1` — version controlled by `SPARK_VERSION` in the top-level `Makefile` (currently `3.2.1`);
- OpenJDK 11 runtime (`openjdk-11-jdk-headless`)
- miniconda 24.1.2 (Python 3.11) with R packages (`r-devtools`, `r-stringr`, `r-argparse`)
- Apache Toree `0.5.0-incubating`
- `jovyan` service user (UID `1000`, matching upstream Jupyter images), with system users `elyra`, `bob`, and `alice`
- Password-less SSH for the `jovyan` service user
- HDFS home directories created at container startup for each system user

# Basic Use

As of the 0.9.0 release of [Jupyter Enterprise Gateway](https://github.com/jupyter-server/enterprise_gateway/releases)
this image can be started as a separate YARN cluster to better demonstrate remote kernel capabilities. See section
[Dual Mode](https://hub.docker.com/r/elyra/enterprise-gateway/#dual_mode) on the enterprise-gateway page for command
usage.

# Pinned dependencies

This image's conda/mamba environment pins `ipykernel<7` to keep kernel idle/busy transitions working under the Enterprise Gateway process-proxy model.
