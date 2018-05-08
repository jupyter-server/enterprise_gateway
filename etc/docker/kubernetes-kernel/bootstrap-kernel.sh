#!/bin/bash

echo language=${KERNEL_LANGUAGE}
echo reponse-addr=${EG_RESPONSE_ADDRESS}

#CMD=${1:-"--help"}
#if [[ "$CMD" == "--help" ]];
#then
#	echo ""
#	echo "usage: docker run <language>"
#	echo ""
#	echo "where <language> is:"
#	echo "    --scala  ... Invokes the Toree kernel."
#	echo "    --r      ... Invokes the IR kernel."
#	echo "    --help   ... Produces this message."
#	echo "    <other>  ... Invokes '/bin/bash -c <other>'.  Use <other>='bash' to explore within the container."
#	echo ""
#fi


if [[ "${KERNEL_LANGUAGE}" == "python" ]];
then
	echo "python /opt/elyra/bin/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.no-spark-context"
	python /opt/elyra/bin/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.no-spark-context
else
	echo ""
	echo "Starting bash with '$*'"
	/bin/bash -c "$*"
fi
exit 0
