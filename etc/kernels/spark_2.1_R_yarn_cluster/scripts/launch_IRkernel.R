library(SparkR)
library(argparser)

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

local_ip <- "0.0.0.0"

# Check arguments
parser <- arg_parser('R-kernel-launcher')
parser <- add_argument(parser, "--response-address",
       help="the IP:port address of the system hosting JKG and expecting response")
parser <- add_argument(parser, "connection_file",
       help="Connection file name to be used; dictated by JKG")

argv <- parse_args(parser)

# Make sure SparkR package is loaded last; this is necessary
# to avoid the need to fully qualify package namspace (using ::)
old <- getOption("defaultPackages")
options(defaultPackages = c(old, "SparkR"))

# Initialize a new spark Session
spark <- SparkR::sparkR.session(enableHiveSupport = FALSE)
assign("spark", spark, envir = .GlobalEnv)

# Initialize spark context and sql context
sc <- SparkR:::callJStatic("org.apache.spark.sql.api.r.SQLUtils", "getJavaSparkContext", spark)
sqlContext <<- SparkR::sparkRSQL.init(sc)
assign("sc", sc, envir = .GlobalEnv)

# If connection file does not exist on local FS, create it.
#  If there is a response address, use pull socket mode
if (!file.exists(argv$connection_file)){
    key <- uuid::UUIDgenerate()
    connection_file <- argv$connection_file
    
    python_cmd <- stringr::str_interp(gsub("\n[:space:]*" , "",
               "python -c \"from jupyter_client.connect import write_connection_file;
                write_connection_file(fname='${connection_file}', ip='${local_ip}', key='${key}')\""))

    system(python_cmd)

    if (length(argv$response_address){
      return_connection_info(argv$connection_file, local_ip, argv$response_address)
    }
}

# Start the kernel
IRkernel::main(argv$connection_file)

# Stop the context and exit
sparkR.session.stop()
