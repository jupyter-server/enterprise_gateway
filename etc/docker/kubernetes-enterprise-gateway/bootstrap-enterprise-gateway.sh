#!/bin/bash

# This file is a copy of /etc/bootstrap.sh but invokes Jupyter Enterprise Gateway in its "deamon" case.
# It also checks for --help or no options before starting anything...


CMD=${1:-"--help"}
if [[ "$CMD" == "--help" ]];
then
	echo ""
	echo "usage: docker run -h <container-hostname> -p 8888:8888 -p 8088:8088 -p 8042:8042 <docker-opts> <docker-image> <command>"
	echo ""
	echo "where <command> is:"
	echo "    --elyra ... Invokes Enterprise Gateway as user 'elyra' directly.  Useful for daemon behavior."
	echo "    --help  ... Produces this message."
	echo "    <other> ... Invokes '/bin/bash -c <other>'.  Use <other>='bash' to explore within the container."
	echo ""
	echo "NOTE: It is advised that port '8888' be mapped to a host port, although the host port number is not"
	echo "      required to be '8888'.  Mapping of ports '8088' and '8042' is also strongly recommended"
	echo "      for YARN application monitoring."
	exit 0
fi

sed s/HOSTNAME/$HOSTNAME/ /usr/local/share/jupyter/start-enterprise-gateway.sh.template > /usr/local/share/jupyter/start-enterprise-gateway.sh
chmod 0755 /usr/local/share/jupyter/start-enterprise-gateway.sh

if [[ "$CMD" == "--elyra" ]];
then
	/usr/local/share/jupyter/start-enterprise-gateway.sh
else
	echo ""
	/bin/bash -c "$*"
fi
exit 0