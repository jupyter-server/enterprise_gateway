#!/bin/bash

KERNEL_LAUNCHERS_PATH=/usr/local/share/jupyter/kernel-launchers

echo $0 env: `env`

launch_python_kernel() {
    # Launch the python kernel launcher - which embeds the IPython kernel and listens for interrupts
    # and shutdown requests from Enterprise Gateway.

    export JPY_PARENT_PID=$$  # Force reset of parent pid since we're detached

	set -x
	python ${KERNEL_LAUNCHERS_PATH}/python/scripts/launch_ipykernel.py --RemoteProcessProxy.kernel-id ${KERNEL_ID} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
	{ set +x; } 2>/dev/null
}

launch_R_kernel() {
    # Launch the R kernel launcher - which embeds the IRkernel kernel and listens for interrupts
    # and shutdown requests from Enterprise Gateway.

	set -x
	Rscript ${KERNEL_LAUNCHERS_PATH}/R/scripts/launch_IRkernel.R --RemoteProcessProxy.kernel-id ${KERNEL_ID} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
	{ set +x; } 2>/dev/null
}

launch_scala_kernel() {
    # Launch the scala kernel launcher - which embeds the Apache Toree kernel and listens for interrupts
    # and shutdown requests from Enterprise Gateway.  This kernel is currenly always launched using
    # spark-submit, so additional setup is required.

    PROG_HOME=${KERNEL_LAUNCHERS_PATH}/scala
    KERNEL_ASSEMBLY=`(cd "${PROG_HOME}/lib"; ls -1 toree-assembly-*.jar;)`
    TOREE_ASSEMBLY="${PROG_HOME}/lib/${KERNEL_ASSEMBLY}"
    if [ ! -f ${TOREE_ASSEMBLY} ]; then
        echo "Toree assembly '${PROG_HOME}/lib/toree-assembly-*.jar' is missing.  Exiting..."
        exit 1
    fi

    # Toree launcher jar path, plus required lib jars (toree-assembly)
    JARS="${TOREE_ASSEMBLY}"
    # Toree launcher app path
    LAUNCHER_JAR=`(cd "${PROG_HOME}/lib"; ls -1 toree-launcher*.jar;)`
    LAUNCHER_APP="${PROG_HOME}/lib/${LAUNCHER_JAR}"
    if [ ! -f ${LAUNCHER_APP} ]; then
        echo "Scala launcher jar '${PROG_HOME}/lib/toree-launcher*.jar' is missing.  Exiting..."
        exit 1
    fi

    SPARK_OPTS="--name ${KERNEL_USERNAME}-${KERNEL_ID}"
    TOREE_OPTS="--alternate-sigint USR2"

    set -x
    eval exec \
         "${SPARK_HOME}/bin/spark-submit" \
         "${SPARK_OPTS}" \
         --jars "${JARS}" \
         --class launcher.ToreeLauncher \
         "${LAUNCHER_APP}" \
         "${TOREE_OPTS}" \
         "--RemoteProcessProxy.kernel-id ${KERNEL_ID} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
    { set +x; } 2>/dev/null
}

# Invoke appropriate launcher based on KERNEL_LANGUAGE

if [[ "${KERNEL_LANGUAGE}" == "python" ]]
then
    launch_python_kernel
elif [[ "${KERNEL_LANGUAGE}" == "scala" ]]
then
    launch_scala_kernel
elif [[ "${KERNEL_LANGUAGE}" == "r" ]]
then
    launch_R_kernel
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0

