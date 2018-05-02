#!/bin/bash

echo language=${ENV_LANGUAGE}
echo reponse-addr=${ENV_RESPONSE_ADDRESS}

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


if [[ "${ENV_LANGUAGE}" == "python" ]];
then
	echo "python /opt/elyra/bin/launch_ipykernel.py /opt/elyra/conf/connection.json --RemoteProcessProxy.response-address ${ENV_RESPONSE_ADDRESS} --RemoteProcessProxy.context k8s"
	python /opt/elyra/bin/launch_ipykernel.py /opt/elyra/conf/connection.json --RemoteProcessProxy.response-address ${ENV_RESPONSE_ADDRESS} --RemoteProcessProxy.context k8s
else
	echo ""
	echo "Note: Enterprise Gateway can be manually started using 'sudo -u elyra /usr/local/share/jupyter/start-enterprise-gateway.sh'..."
	echo "      YARN application logs can be found at '/usr/local/hadoop-2.7.1/logs/userlogs'"
	/bin/bash -c "$*"
fi
exit 0
