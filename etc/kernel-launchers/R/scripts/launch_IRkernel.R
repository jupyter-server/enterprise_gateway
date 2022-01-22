library(argparse)
library(jsonlite)

require("SparkR")
require("base64enc")
require("digest")
require("stringr")

r_libs_user <- Sys.getenv("R_LIBS_USER")

sparkConfigList <- list(
spark.executorEnv.R_LIBS_USER=r_libs_user,
spark.rdd.compress="true")

min_port_range_size = Sys.getenv("MIN_PORT_RANGE_SIZE")
if ( is.null(min_port_range_size) )
    min_port_range_size = Sys.getenv("EG_MIN_PORT_RANGE_SIZE")
if ( is.null(min_port_range_size) )
    min_port_range_size = 1000

# Initializes the Spark session/context and SQL context
initialize_spark_session <- function(mode) {
    # Make sure SparkR package is loaded last; this is necessary
    # to avoid the need to fully qualify package namespace (using ::)
    old <- getOption("defaultPackages")
    options(defaultPackages = c(old, "SparkR"))

    if (identical(mode, "eager")) {
        # Start the spark context immediately if set to eager
        spark <- SparkR::sparkR.session(enableHiveSupport = FALSE, sparkConfig=sparkConfigList)
        assign("spark", spark, envir = .GlobalEnv)
        sc <- SparkR:::callJStatic("org.apache.spark.sql.api.r.SQLUtils", "getJavaSparkContext", spark)
        sqlContext <<- SparkR::sparkRSQL.init(sc)
        assign("sc", sc, envir = .GlobalEnv)

    } else {
        # Keep lazy evaluation as default starting mode if initialization mode is lazy or not set at all
        makeActiveBinding(".sparkRsession", sparkSessionFn, SparkR:::.sparkREnv)
        makeActiveBinding(".sparkRjsc", sparkContextFn, SparkR:::.sparkREnv)

        delayedAssign("spark", {get(".sparkRsession", envir=SparkR:::.sparkREnv)}, assign.env=.GlobalEnv)

        # backward compatibility for Spark 1.6 and earlier notebooks
        delayedAssign("sc", {get(".sparkRjsc", envir=SparkR:::.sparkREnv)}, assign.env=.GlobalEnv)
        delayedAssign("sqlContext", {spark}, assign.env=.GlobalEnv)
    }
}

sparkSessionFn <- local({
     function(v) {
       if (missing(v)) {
         # get SparkSession

         # create a new sparkSession
         rm(".sparkRsession", envir=SparkR:::.sparkREnv) # rm to ensure no infinite recursion

         get("sc", envir=.GlobalEnv)

         sparkSession <- SparkR::sparkR.session(
                                        sparkHome=Sys.getenv("SPARK_HOME"),
                                        sparkConfig=sparkConfigList);
         sparkSession
       }
     }
   })

sparkContextFn <- local({
    function(v) {
      if (missing(v)) {
        # get SparkContext

        # create a new sparkContext
        rm(".sparkRjsc", envir=SparkR:::.sparkREnv) # rm to ensure no infinite recursion

        message ("Obtaining Spark session...")

        sparkContext <- SparkR:::sparkR.sparkContext(
                                          sparkHome=Sys.getenv("SPARK_HOME"),
                                          sparkEnvirMap=SparkR:::convertNamedListToEnv(sparkConfigList))

        message ("Spark session obtained.")
        sparkContext
      }
    }
  })

# Figure out the connection_file to use
determine_connection_file <- function(kernel_id){
    base_file = paste("kernel-", kernel_id, sep="")
    temp_file = tempfile(pattern=paste(base_file,"_",sep=""), fileext=".json")
    cat(paste("Using connection file ",temp_file," \n",sep="'"))
    return(temp_file)
}

validate_port_range <- function(port_range){
    port_ranges = strsplit(port_range, "..", fixed=TRUE)
    lower_port = as.integer(port_ranges[[1]][1])
    upper_port = as.integer(port_ranges[[1]][2])

    port_range_size = upper_port - lower_port
    if (port_range_size != 0) {
        if (port_range_size < min_port_range_size){
            message(paste("Port range validation failed for range:", port_range, ". Range size must be at least",
                min_port_range_size, "as specified by env EG_MIN_PORT_RANGE_SIZE"))
            return(NA)
        }
    }
    return(list("lower_port"=lower_port, "upper_port"=upper_port))
}

# Check arguments
parser <- argparse::ArgumentParser(description="Parse Arguments for R Launcher")
parser$add_argument("--kernel-id", nargs='?',
       help="the id associated with the launched kernel")
parser$add_argument("--port-range", nargs='?', metavar='<lowerPort>..<upperPort>',
       help="the range of ports impose for kernel ports")
parser$add_argument("--response-address", nargs='?', metavar='<ip>:<port>',
      help="the IP:port address of the system hosting the server and expecting response")
parser$add_argument("--public-key", nargs='?',
      help="the public key used to encrypt connection information")
parser$add_argument("--spark-context-initialization-mode", nargs='?',
      help="the initialization mode of the spark context: lazy, eager or none")
parser$add_argument("--customAppName", nargs='?', help="the custom application name to be set")

# The following arguments are deprecated and will be used only if their mirroring arguments have no value.
# This means that the default value for --spark-context-initialization-mode (none) will need to come from
# the mirrored args' default until deprecated items have been removed.

parser$add_argument("connection_file", nargs='?', help='Connection file to write connection info')
parser$add_argument("--RemoteProcessProxy.kernel-id", nargs='?',
       help="the id associated with the launched kernel (deprecated)")
parser$add_argument("--RemoteProcessProxy.port-range", nargs='?', metavar='<lowerPort>..<upperPort>',
       help="the range of ports impose for kernel ports (deprecated)")
parser$add_argument("--RemoteProcessProxy.response-address", nargs='?', metavar='<ip>:<port>',
      help="the IP:port address of the system hosting the server and expecting response (deprecated)")
parser$add_argument("--RemoteProcessProxy.public-key", nargs='?',
      help="the public key used to encrypt connection information (deprecated)")
parser$add_argument("--RemoteProcessProxy.spark-context-initialization-mode", nargs='?', default="none",
      help="the initialization mode of the spark context: lazy, eager or none (deprecated)")

argv <- parser$parse_args()

kernel_id <- argv$kernel_id
if (is.null(kernel_id)) {
    kernel_id <- argv$RemoteProcessProxy.kernel_id
}

port_range <- argv$port_range
if (is.null(port_range)) {
    port_range <- argv$RemoteProcessProxy.port_range
}

response_address <- argv$response_address
if (is.null(response_address)) {
    response_address <- argv$RemoteProcessProxy.response_address
}

public_key <- argv$public_key
if (is.null(public_key)) {
    public_key <- argv$RemoteProcessProxy.public_key
}

spark_context_initialization_mode <- argv$spark_context_initialization_mode
if (is.null(spark_context_initialization_mode)) {
    spark_context_initialization_mode <- argv$RemoteProcessProxy.spark_context_initialization_mode
}


if (is.null(argv$connection_file) && is.null(kernel_id)){
    message("At least one of the parameters: 'connection_file' or '--kernel-id' must be provided!")
    return(NA)
}

if (is.null(kernel_id)){
    message("Parameter '--kernel-id' must be provided!")
    return(NA)
}

if (is.null(public_key)){
    message("Parameter '--public-key' must be provided!")
    return(NA)
}

# if we have a response address, then deal with items relative to remote support (ports, comm-socket, etc.)
if (!is.null(response_address) && str_length(response_address) > 0){

    #If port range argument is passed from kernel json with no value
    if (is.null(port_range)){
        port_range <- NA
    }

    #  If there is a response address, use pull socket mode
    connection_file <- determine_connection_file(kernel_id)

    # if port-range was provided, validate the range and determine bounds
    lower_port = 0
    upper_port = 0
    if (!is.na(port_range)){
        range <- validate_port_range(port_range)
        if (length(range) > 1){
            lower_port = range$lower_port
            upper_port = range$upper_port
        }
    }

    # Get the pid of the launcher so the listener thread (process) can detect its
    # presence to know when to shutdown.
    pid <- Sys.getpid()

    # Hoop to jump through to get the directory this script resides in so that we can
    # load the co-located python server_listener.py file.  This code will not work if
    # called directly from within RStudio.
    # https://stackoverflow.com/questions/1815606/rscript-determine-path-of-the-executing-script
    launch_args <- commandArgs(trailingOnly = FALSE)
    file_option <- "--file="
    script_path <- sub(file_option, "", launch_args[grep(file_option, launch_args)])
    listener_file <- paste(sep="/", dirname(script_path), "server_listener.py")

    # Launch the server listener logic in an async manner and poll for the existence of
    # the connection file before continuing.  Should there be an issue, the server
    # will terminate the launcher, so there's no need for a timeout.
    python_cmd <- Sys.getenv("PYSPARK_PYTHON", "python")  # If present, use the same python specified for Spark

    svr_listener_cmd <- stringr::str_interp(gsub("\n[:space:]*" , "",
                paste(python_cmd,"-c \"import os, sys, imp;
                gl = imp.load_source('setup_server_listener', '${listener_file}');
                gl.setup_server_listener(conn_filename='${connection_file}', parent_pid='${pid}',
                lower_port=${lower_port}, upper_port=${upper_port},
                response_addr='${response_address}', kernel_id='${kernel_id}', public_key='${public_key}')\"")))
    system(svr_listener_cmd, wait=FALSE)

    while (!file.exists(connection_file)) {
        Sys.sleep(0.5)
    }

} else {
    # already provided
    connection_file = argv$connection_file
}

# If spark context creation is desired go ahead and initialize the session/context
# Otherwise, skip spark context creation if set to none or not provided
if (!is.na(spark_context_initialization_mode)){
    if (!identical(spark_context_initialization_mode, "none")){
        # Add custom application name (spark.app.name) spark config if available, else default to kernel_id
        if (!is.null(argv$customAppName) && str_length(argv$customAppName) > 0){
            sparkConfigList[['spark.app.name']] <- argv$customAppName
        } else {
            sparkConfigList[['spark.app.name']] <- kernel_id
        }
        initialize_spark_session(spark_context_initialization_mode)
    }
}

# Start the kernel
IRkernel::main(connection_file)

# Only unlink the connection file if we're launched for remote behavior.
if (!is.na(response_address)){
    unlink(connection_file)
}

# Stop the context and exit
if (!identical(spark_context_initialization_mode, "none")){
    sparkR.session.stop()
}
