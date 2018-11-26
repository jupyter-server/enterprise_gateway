#!/bin/bash

# This file is a copy of /usr/local/bin/bootstrap.sh but invokes Jupyter Enterprise Gateway in its "deamon" case.
# It also checks for --help or no options before starting anything...


CMD=${1:-"--help"}
if [[ "$CMD" == "--help" ]];
then
	echo ""
	echo "usage: docker run <docker-opts> <docker-image> <command>"
	echo ""
	echo "where <command> is:"
	echo "    --jovyan ... Invokes Enterprise Gateway directly.  Useful for daemon behavior."
	echo "    --help  ... Produces this message."
	echo "    <other> ... Invokes '/bin/bash -c <other>'.  Use <other>='bash' to explore within the container."
	echo ""

	exit 0
fi

chmod 0755 /usr/local/bin/start-enterprise-gateway.sh

if [[ "$CMD" == "--jovyan" ]];
then
	/usr/local/bin/start-enterprise-gateway.sh
else
	echo ""
	/bin/bash -c "$*"
fi
exit 0
