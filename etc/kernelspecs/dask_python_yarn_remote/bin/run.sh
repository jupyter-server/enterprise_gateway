#!/usr/bin/env bash

if [ "${EG_IMPERSONATION_ENABLED}" = "True" ]; then
    IMPERSONATION_OPTS="--user ${KERNEL_USERNAME:-UNSPECIFIED}"
    USER_CLAUSE="as user ${KERNEL_USERNAME:-UNSPECIFIED}"
else
    IMPERSONATION_OPTS=""
    USER_CLAUSE="on behalf of user ${KERNEL_USERNAME:-UNSPECIFIED}"
fi

echo
echo "Starting IPython kernel for Dask ${USER_CLAUSE}"
echo

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

set -x
eval exec \
     "${DASK_YARN_EXE}" submit \
     "${DASK_OPTS}" \
     "${IMPERSONATION_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
