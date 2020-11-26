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

encrypt <- function(json, connection_file) {
  # Ensure that the length of the data that will be encrypted is a
  # multiple of 16 by padding with '%' on the right.
  raw_payload <- str_pad(json, (str_length(json) %/% 16 + 1) * 16, side="right", pad="%")
  message(paste("Raw Payload: ", raw_payload))

  fn <- basename(connection_file)
  tokens <- unlist(strsplit(fn, "kernel-"))
  key <- charToRaw(substr(tokens[2], 1, 16))
  # message(paste("AES Encryption Key: ", rawToChar(key)))

  cipher <- AES(key, mode="ECB")
  encrypted_payload <- cipher$encrypt(raw_payload)
  encoded_payload = base64encode(encrypted_payload)
  return(encoded_payload)
}

# Return connection information
return_connection_info <- function(connection_file, response_addr){

  response_parts <- strsplit(response_addr, ":")

  if (length(response_parts[[1]])!=2){
    cat("Invalid format for response address. Assuming pull mode...")
    return(1)
  }

  response_ip <- response_parts[[1]][1]
  response_port <- response_parts[[1]][2]

  # Read in connection file to send back to JKG
  con <- NULL
  tryCatch(
    {
        con <- socketConnection(host=response_ip, port=response_port, blocking=FALSE, server=FALSE)
        sendme <- read_json(connection_file)
        # Add launcher process id to returned info...
        sendme$pid <- Sys.getpid()
        json <- jsonlite::toJSON(sendme, auto_unbox=TRUE)
        message(paste("JSON Payload: ", json))

        fn <- basename(connection_file)
        if (!grepl("kernel-", fn)) {
          message(paste("Invalid connection file name: ", connection_file))
          return(NA)
        }
        payload <- encrypt(json, connection_file)
        message(paste("Encrypted Payload: ", payload))
        write_resp <- writeLines(payload, con)
    },
    error=function(cond) {
        message(paste("Unable to connect to response address", response_addr ))
        message("Here's the original error message:")
        message(cond)
        # Choose a return value in case of error
        return(NA)
    },
    finally={
        if (!is.null(con)) {
            close(con)
        }
    }
  )
}

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
parser$add_argument("connection_file", nargs='?', help='Connection file to write connection info')
parser$add_argument("--RemoteProcessProxy.kernel-id", nargs='?',
       help="the id associated with the launched kernel")
parser$add_argument("--RemoteProcessProxy.port-range", nargs='?', metavar='<lowerPort>..<upperPort>',
       help="the range of ports impose for kernel ports")
parser$add_argument("--RemoteProcessProxy.response-address", nargs='?', metavar='<ip>:<port>',
      help="the IP:port address of the system hosting Enterprise Gateway and expecting response")
parser$add_argument("--RemoteProcessProxy.spark-context-initialization-mode", nargs='?', default="none",
      help="the initialization mode of the spark context: lazy, eager or none")
parser$add_argument("--customAppName", nargs='?', help="the custom application name to be set")

argv <- parser$parse_args()

if (is.null(argv$connection_file) && is.null(argv$RemoteProcessProxy.kernel_id)){
    message("At least one of the parameters: 'connection_file' or '--RemoteProcessProxy.kernel-id' must be provided!")
    return(NA)
}

# if we have a response address, then deal with items relative to remote support (ports, gateway-socket, etc.)
if (!is.null(argv$RemoteProcessProxy.response_address) && str_length(argv$RemoteProcessProxy.response_address) > 0){

    #If port range argument is passed from kernel json with no value
    if (is.null(argv$RemoteProcessProxy.port_range)){
        argv$RemoteProcessProxy.port_range <- NA
    }

    #  If there is a response address, use pull socket mode
    connection_file <- determine_connection_file(argv$RemoteProcessProxy.kernel_id)

    # if port-range was provided, validate the range and determine bounds
    lower_port = 0
    upper_port = 0
    if (!is.na(argv$RemoteProcessProxy.port_range)){
        range <- validate_port_range(argv$RemoteProcessProxy.port_range)
        if (length(range) > 1){
            lower_port = range$lower_port
            upper_port = range$upper_port
        }
    }

    # Get the pid of the launcher so the listener thread (process) can detect its
    # presence to know when to shutdown.
    pid <- Sys.getpid()

    # Hoop to jump through to get the directory this script resides in so that we can
    # load the co-located python gateway_listener.py file.  This code will not work if
    # called directly from within RStudio.
    # https://stackoverflow.com/questions/1815606/rscript-determine-path-of-the-executing-script
    launch_args <- commandArgs(trailingOnly = FALSE)
    file_option <- "--file="
    script_path <- sub(file_option, "", launch_args[grep(file_option, launch_args)])
    listener_file <- paste(sep="/", dirname(script_path), "gateway_listener.py")

    # Launch the gateway listener logic in an async manner and poll for the existence of
    # the connection file before continuing.  Should there be an issue, Enterprise Gateway
    # will terminate the launcher, so there's no need for a timeout.
    python_cmd <- Sys.getenv("PYSPARK_PYTHON", "python")  # If present, use the same python specified for Spark

    gw_listener_cmd <- stringr::str_interp(gsub("\n[:space:]*" , "",
                paste(python_cmd,"-c \"import os, sys, imp;
                gl = imp.load_source('setup_gateway_listener', '${listener_file}');
                gl.setup_gateway_listener(fname='${connection_file}', parent_pid='${pid}', lower_port=${lower_port},
                    upper_port=${upper_port})\"")))
    system(gw_listener_cmd, wait=FALSE)

    while (!file.exists(connection_file)) {
        Sys.sleep(0.5)
    }

    return_connection_info(connection_file, argv$RemoteProcessProxy.response_address)
} else {
    # already provided
    connection_file = argv$connection_file
}

# If spark context creation is desired go ahead and initialize the session/context
# Otherwise, skip spark context creation if set to none or not provided
if (!is.na(argv$RemoteProcessProxy.spark_context_initialization_mode)){
    if (!identical(argv$RemoteProcessProxy.spark_context_initialization_mode, "none")){
        # Add custom application name (spark.app.name) spark config if available, else default to kernel_id
        if (!is.null(argv$customAppName) && str_length(argv$customAppName) > 0){
            sparkConfigList[['spark.app.name']] <- argv$customAppName
        } else {
            sparkConfigList[['spark.app.name']] <- argv$RemoteProcessProxy.kernel_id
        }
        initialize_spark_session(argv$RemoteProcessProxy.spark_context_initialization_mode)
    }
}

# Start the kernel
IRkernel::main(connection_file)

# Only unlink the connection file if we're launched for remote behavior.
if (!is.na(argv$RemoteProcessProxy.response_address)){
    unlink(connection_file)
}

# Stop the context and exit
if (!identical(argv$RemoteProcessProxy.spark_context_initialization_mode, "none")){
    sparkR.session.stop()
}
