library(IRkernel)
library(SparkR)

# Take in command line arguments (connection file)
args <- commandArgs(trailingOnly = TRUE)

# Make sure SparkR package is loaded at the last this is necessary
# to avoid the need to fully qualify package namspace (using ::)
old <- getOption("defaultPackages")
options(defaultPackages = c(old, "SparkR"))

# Initialize a new spark Session
# Default to without Hive support for backward compatibility.
spark <- SparkR::sparkR.session(enableHiveSupport = FALSE)
assign("spark", spark, envir = .GlobalEnv)

# Initialize spark context and sql context
sc <- SparkR:::callJStatic("org.apache.spark.sql.api.r.SQLUtils", "getJavaSparkContext", spark)
sqlContext <<- SparkR::sparkRSQL.init(sc);
assign("sc", sc, envir = .GlobalEnv)

# Pass in kernel connection file to R kernel
IRkernel::main(args[1])

# Stop the context and exit
sparkR.session.stop()
