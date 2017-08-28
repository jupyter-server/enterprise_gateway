library(SparkR)
library(argparser)

r_libs_user <- Sys.getenv("R_LIBS_USER")

sparkConfigList <- list(
spark.executorEnv.R_LIBS_USER=r_libs_user,
spark.rdd.compress="true",
spark.serializer.objectStreamReset="100")

# Initializes the Spark session/context and SQL context
initialize_spark_session <- function() {
    # Make sure SparkR package is loaded last; this is necessary
    # to avoid the need to fully qualify package namspace (using ::)
    old <- getOption("defaultPackages")
    options(defaultPackages = c(old, "SparkR"))

    makeActiveBinding(".sparkRsession", sparkSessionFn, SparkR:::.sparkREnv)
    makeActiveBinding(".sparkRjsc", sparkContextFn, SparkR:::.sparkREnv)

    delayedAssign("spark", {get(".sparkRsession", envir=SparkR:::.sparkREnv)}, assign.env=.GlobalEnv)

    # backward compatibility for Spark 1.6 and earlier notebooks
    delayedAssign("sc", {get(".sparkRjsc", envir=SparkR:::.sparkREnv)}, assign.env=.GlobalEnv)
    delayedAssign("sqlContext", {spark}, assign.env=.GlobalEnv)
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

# Return connection information
return_connection_info <- function(connection_file, ip, response_addr){

  response_parts <- strsplit(response_addr, ":")

  if (length(response_parts[[1]])!=2){
    cat("Invalid format for response address. Assuming pull mode...")
    return(1)
  }

  response_ip <- response_parts[[1]][1]
  response_port <- response_parts[[1]][2]

  # Read in connection file to send back to JKG
  tryCatch(
    {
      con <- socketConnection(host=response_ip, port=response_port, blocking=FALSE, server=FALSE)
      sendme <- readLines(con = connection_file, encoding = "UTF-8")
      write_resp <- writeLines(sendme, con)
    },
    error=function(cond) {
            message(paste("Unable to connect to response address", response_addr ))
            message("Here's the original error message:")
            message(cond)
            # Choose a return value in case of error
            return(NA)
    },
    finally={
      close(con)
    }
  )
}

# Figure out the connection_file to use
determine_connection_file <- function(connection_file){
    # If the directory of the given connection_file exists, use it.
    if (dir.exists(dirname(connection_file))) {
        return(connection_file)
    }
    # Else, create a temporary filename and return that.
    base_file = tools::file_path_sans_ext(basename(connection_file))
    temp_file = tempfile(pattern=paste(base_file,"_",sep=""), fileext=".json")
    cat(paste("Using connection file ",temp_file," instead of ",connection_file,"",sep="'"))
    return(temp_file)
}

local_ip <- "0.0.0.0"

# Check arguments
parser <- arg_parser('R-kernel-launcher')
parser <- add_argument(parser, "--RemoteProcessProxy.response-address",
       help="the IP:port address of the system hosting JKG and expecting response")
parser <- add_argument(parser, "connection_file",
       help="Connection file name to be used; dictated by JKG")

argv <- parse_args(parser)

# If connection file does not exist on local FS, create it.
#  If there is a response address, use pull socket mode
connection_file <- argv$connection_file
if (!file.exists(connection_file)){
    key <- uuid::UUIDgenerate()
    connection_file <- determine_connection_file(connection_file)

    python_cmd <- stringr::str_interp(gsub("\n[:space:]*" , "",
               "python -c \"from jupyter_client.connect import write_connection_file;
                write_connection_file(fname='${connection_file}', ip='${local_ip}', key='${key}')\""))

    system(python_cmd)

    if (length(argv$RemoteProcessProxy.response_address)){
      return_connection_info(connection_file, local_ip, argv$RemoteProcessProxy.response_address)
    }
}

initialize_spark_session()

# Start the kernel
IRkernel::main(connection_file)

unlink(connection_file)

# Stop the context and exit
sparkR.session.stop()
