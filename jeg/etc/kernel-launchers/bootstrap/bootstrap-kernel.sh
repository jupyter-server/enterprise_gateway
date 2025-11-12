#!/bin/bash

PORT_RANGE=${PORT_RANGE:-${EG_PORT_RANGE:-0..0}}
RESPONSE_ADDRESS=${RESPONSE_ADDRESS:-${EG_RESPONSE_ADDRESS}}
PUBLIC_KEY=${PUBLIC_KEY:-${EG_PUBLIC_KEY}}
KERNEL_LAUNCHERS_DIR=${KERNEL_LAUNCHERS_DIR:-/usr/local/bin/kernel-launchers}
KERNEL_SPARK_CONTEXT_INIT_MODE=${KERNEL_SPARK_CONTEXT_INIT_MODE:-none}
KERNEL_CLASS_NAME=${KERNEL_CLASS_NAME}

echo $0 env: `env`

launch_python_kernel() {
  # Launch the python kernel launcher - which embeds the IPython kernel and listens for interrupts
  # and shutdown requests from Enterprise Gateway.

  export JPY_PARENT_PID=$$  # Force reset of parent pid since we're detached

  if [ -z "${KERNEL_CLASS_NAME}" ]
  then
    kernel_class_option=""
  else
    kernel_class_option="--kernel-class-name ${KERNEL_CLASS_NAME}"
  fi

	set -x
	python ${KERNEL_LAUNCHERS_DIR}/python/scripts/launch_ipykernel.py --kernel-id ${KERNEL_ID} \
	      --port-range ${PORT_RANGE} --response-address ${RESPONSE_ADDRESS} --public-key ${PUBLIC_KEY} \
	      --spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE} ${kernel_class_option}
	{ set +x; } 2>/dev/null
}

launch_R_kernel() {
    # Launch the R kernel launcher - which embeds the IRkernel kernel and listens for interrupts
    # and shutdown requests from Enterprise Gateway.

	set -x
	Rscript ${KERNEL_LAUNCHERS_DIR}/R/scripts/launch_IRkernel.R --kernel-id ${KERNEL_ID} --port-range ${PORT_RANGE} --response-address ${RESPONSE_ADDRESS} --public-key ${PUBLIC_KEY} --spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
	{ set +x; } 2>/dev/null
}

launch_scala_kernel() {
    # Launch the scala kernel launcher - which embeds the Apache Toree kernel and listens for interrupts
    # and shutdown requests from Enterprise Gateway.  This kernel is currenly always launched using
    # spark-submit, so additional setup is required.

    PROG_HOME=${KERNEL_LAUNCHERS_DIR}/scala
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
         "--kernel-id ${KERNEL_ID} --port-range ${PORT_RANGE} --response-address ${RESPONSE_ADDRESS} --public-key ${PUBLIC_KEY} --spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
    { set +x; } 2>/dev/null
}

# Ensure that required envs are present, check language before the dynamic values
if [ -z "${KERNEL_LANGUAGE+x}" ]
then
    echo "KERNEL_LANGUAGE is required.  Set this value in the image or when starting container."
    exit 1
fi
if [ -z "${KERNEL_ID+x}" ] || [ -z "${RESPONSE_ADDRESS+x}" ] || [ -z "${PUBLIC_KEY+x}" ]
then
    echo "Environment variables, KERNEL_ID, RESPONSE_ADDRESS, and PUBLIC_KEY are required."
    exit 1
fi

# Invoke appropriate launcher based on KERNEL_LANGUAGE (case-insensitive)

if [[ "${KERNEL_LANGUAGE,,}" == "python" ]]
then
    launch_python_kernel
elif [[ "${KERNEL_LANGUAGE,,}" == "scala" ]]
then
    launch_scala_kernel
elif [[ "${KERNEL_LANGUAGE,,}" == "r" ]]
then
    launch_R_kernel
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
