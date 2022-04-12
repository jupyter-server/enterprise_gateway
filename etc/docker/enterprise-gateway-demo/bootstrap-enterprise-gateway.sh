#!/bin/bash

# This file is a copy of /etc/bootstrap.sh but invokes Jupyter Enterprise Gateway in its "deamon" case.
# It also checks for --help or no options before starting anything...


CMD=${1:-"--help"}
if [[ "$CMD" == "--help" ]]; then
	echo ""
	echo "usage: docker run -it[d] --rm -h <container-hostname> -p 8888:8888 [-p 8088:8088 -p 8042:8042] <docker-opts> <docker-image> <command>"
	echo ""
	echo "where <command> is:"
	echo "    --gateway ... Invokes Enterprise Gateway as user 'jovyan' directly.  Useful for daemon behavior."
	echo "    --yarn  ... Runs container as standalone YARN master - no Enterprise Gateway is started."
	echo "    --help  ... Produces this message."
	echo "    <other> ... Invokes '<other>'.  Use <other>='/bin/bash' to explore within the container."
	echo ""
	echo "Tips:"
	echo "1) You can target a different YARN cluster by using '-e YARN_HOST=<myOtherYarnMaster>'"
	echo "2) You can \"bring your own kernels\" by mounting to /tmp/byok/kernels (e.g., -v my-kernels-dir:/tmp/byok/kernels)"
	echo "3) It is advised that port '8888' be mapped to a host port, although the host port number is not"
	echo "   required to be '8888'.  Mapping of ports '8088' and '8042' is also strongly recommended"
	echo "   for YARN application monitoring if running standalone."
	exit 0
elif [[ "$CMD" != "--gateway" && "$CMD" != "--yarn" ]]; then  # invoke <other> w/o starting YARN
    "$*"
    exit 0
fi

: ${YARN_HOST:=$HOSTNAME}
export FROM="EG"
/usr/local/bin/bootstrap-yarn-spark.sh $*

# Note that '--yarn' functionality is a subset of '--gateway' functionality

if [[ "$CMD" == "--gateway" ]];
then
    sudo sed -i "s/HOSTNAME/$YARN_HOST/" /usr/local/bin/start-enterprise-gateway.sh
    /usr/local/bin/start-enterprise-gateway.sh
fi

exit 0
