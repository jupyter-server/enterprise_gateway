/**
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

package launcher

import java.io.{BufferedWriter, File, FileWriter, PrintStream}
import java.nio.file.{Files, Paths}
import java.net.{InetAddress, ServerSocket, Socket}

import org.apache.toree.Main
import play.api.libs.json._
import java.lang.management.ManagementFactory

import scala.io.BufferedSource
import scala.collection.mutable.ArrayBuffer

import sun.misc.Signal

import launcher.utils.{SecurityUtils, SocketUtils}

import org.apache.toree.utils.LogLike


object ToreeLauncher extends LogLike {

  val minPortRangeSize = sys.env.getOrElse("MIN_PORT_RANGE_SIZE", sys.env.getOrElse("EG_MIN_PORT_RANGE_SIZE", "1000")).toInt
  val kernelTempDir : String = "jupyter-kernel"
  var profilePath : String = _
  var kernelId : String = _
  var portLowerBound : Int = -1
  var portUpperBound : Int = -1
  var responseAddress : String = _
  var publicKey : String = _
  var alternateSigint : String = _
  var initMode : String = "lazy"
  var toreeArgs = ArrayBuffer[String]()

  private def pathExists(filePath : String) : Boolean =
    if (filePath == null) false
    else Files.exists(Paths.get(filePath))

  private def writeToFile(outputPath : String, content : String): Unit = {
    val file = new File(outputPath)
    if(!pathExists(file.getParentFile.toString)) {
      file.getParentFile.mkdirs // mkdir if not exists
    }
    val bw = new BufferedWriter(new FileWriter(file))
    try{
      bw.write(content)
    } finally {
      bw.close()
    }
  }

  private def initPortRange(portRange: String): Unit = {
      val ports = portRange.split("\\.\\.")

      this.portLowerBound = ports(0).toInt
      this.portUpperBound = ports(1).toInt

      logger.info("Port Range: lower bound ( %s ) / upper bound ( %s )"
        .format(this.portLowerBound, this.portUpperBound))

      if (this.portLowerBound != this.portUpperBound) {  // Range of zero disables port restrictions
         if (this.portLowerBound < 0 || this.portUpperBound < 0 ||
            (this.portUpperBound - this.portLowerBound < minPortRangeSize)) {
            logger.error("Invalid port range, use --port-range <LowerBound>..<UpperBound>, " +
              "range must be >= MIN_PORT_RANGE_SIZE ($minPortRangeSize)")
            sys.exit(-1)
         }
      }
  }

  private def initArguments(args: Array[String]): Unit = {

    logger.info("Toree launcher arguments (initial):")
    args.foreach(logger.info(_))
    logger.info("---------------------------")

    // Walk the arguments, collecting launcher options along the way and buildup a
    // new toree arguments list.  There's got to be a better way to do this.
    var i = 0
    while ( i < args.length ) {
      var arg: String = args(i)
      arg match {

        // Profile is a straight pass-thru to toree
        case "--profile" =>
          i += 1
          profilePath = args(i).trim
          toreeArgs += arg
          toreeArgs += profilePath

        // Alternate sigint is a straight pass-thru to toree
        case "--alternate-sigint" =>
          i += 1
          alternateSigint = args(i).trim
          toreeArgs += arg
          toreeArgs += alternateSigint

        // Initialization mode requires massaging for toree
        case "--spark-context-initialization-mode" | "--RemoteProcessProxy.spark-context-initialization-mode" =>
          i += 1
          initMode = args(i).trim
          initMode match {
            case "none" =>
              toreeArgs += "--nosparkcontext"
            case _ =>
              toreeArgs += "--spark-context-initialization-mode"
              toreeArgs += initMode
          }

        // Port range doesn't apply to toree, consume here
        case "--port-range" | "--RemoteProcessProxy.port-range" =>
          i += 1
          initPortRange(args(i).trim)

        // Response address doesn't apply to toree, consume here
        case "--response-address" | "--RemoteProcessProxy.response-address" =>
          i += 1
          responseAddress = args(i).trim

        // kernel id doesn't apply to toree, consume here
        case "--kernel-id" | "--RemoteProcessProxy.kernel-id" =>
          i += 1
          kernelId = args(i).trim

        // Public key doesn't apply to toree, consume here
        case "--public-key" | "--RemoteProcessProxy.public-key" =>
          i += 1
          publicKey = args(i).trim

        // All other arguments should pass-thru to toree
        case _ => toreeArgs += args(i).trim
      }
      i += 1
    }
  }

  // Borrowed from toree to avoid dependency
  private def deleteDirRecur(file: File): Unit = {
    // delete directory recursively
    if (file != null){
      if (file.isDirectory){
        file.listFiles.foreach(deleteDirRecur)
      }
      if (file.exists){
        file.delete
      }
    }
  }

  private def determineConnectionFile(connectionFile: String, kernelId: String): String = {
    // We know the connection file does not exist, so create a temporary directory
    // and derive the filename from kernelId, if not null.
    // If kernelId is null, then use the filename in the connectionFile.

    val tmpPath = Files.createTempDirectory(kernelTempDir)
    // tmpPath.toFile.deleteOnExit() doesn't appear to work, use system hook
    sys.addShutdownHook{
      deleteDirRecur(tmpPath.toFile)
    }
    val fileName = if (kernelId != null) "kernel-" + kernelId + ".json"
      else Paths.get(connectionFile).getFileName.toString
    val newPath = Paths.get(tmpPath.toString, fileName)
    val newConnectionFile = newPath.toString
    // Locate --profile and replace next element with new name.  If it doesn't exist, add both.
    val profileIndex = toreeArgs.indexOf("--profile")
    if (profileIndex >= 0) {
      toreeArgs(profileIndex + 1) = newConnectionFile
    } else {
        toreeArgs += "--profile"
        toreeArgs += newConnectionFile
    }

    newConnectionFile
  }

  private def getPID : String = {
    // Return the current process ID. If not an integer string, server will ignore.
    ManagementFactory.getRuntimeMXBean.getName.split('@')(0)
  }

  private def initProfile(args : Array[String]): ServerSocket = {

    var commSocket : ServerSocket = null

    initArguments(args)

    if (profilePath == null && kernelId == null){
      logger.error("At least one of '--profile' or '--kernel-id' " +
        "must be provided - exiting!")
      sys.exit(-1)
    }

    if (kernelId == null) {
      logger.error("Parameter '--kernel-id' must be provided - exiting!")
      sys.exit(-1)
    }

    if (publicKey == null) {
      logger.error("Parameter '--public-key' must be provided - exiting!")
      sys.exit(-1)
    }

    if (!pathExists(profilePath)) {
      profilePath = determineConnectionFile(profilePath, kernelId)

      logger.info("The profile %s doesn't exist, now creating it...".format(profilePath))

      val content = KernelProfile.createJsonProfile(this.portLowerBound, this.portUpperBound)
      writeToFile(profilePath, content)

      if (pathExists(profilePath)) {
        logger.info("%s saved".format(profilePath))
      } else {
        logger.error("Failed to create: %s".format(profilePath))
        sys.exit(-1)
      }

      var connectionJson = Json.parse(content)

      // Now need to also return the PID info in connection JSON
      connectionJson = connectionJson.as[JsObject] ++ Json.obj("pid" -> getPID)

      // Add kernelId
      connectionJson = connectionJson.as[JsObject] ++ Json.obj("kernel_id" -> kernelId)

      // Server wants to establish socket communication. Create socket and
      // convey port number back to the server.
      commSocket = SocketUtils.findSocket(this.portLowerBound, this.portUpperBound)
      connectionJson = connectionJson.as[JsObject] ++ Json.obj("comm_port" -> commSocket.getLocalPort)
      val jsonContent = Json.toJson(connectionJson).toString()

      if (responseAddress != null){
        logger.info("JSON Payload: '%s'".format(jsonContent))
        val payload = SecurityUtils.encrypt(publicKey, jsonContent)
        logger.info("Encrypted Payload: '%s'".format(payload))
        SocketUtils.writeToSocket(responseAddress, payload)
      }
    }
    commSocket
  }

  private def getServerRequest(commSocket : ServerSocket): String = {
    val s = commSocket.accept()
    val data = new BufferedSource(s.getInputStream).getLines.mkString
    s.close()
    data
  }

  private def getReconciledSignalName(sigNum: Int): String = {
    // To raise the signal, we must map the signal number back to the appropriate
    // name as follows:  Take the common case and assume interrupt and check if an
    // alternate interrupt signal has been given. If sigNum = 9, use "TERM", else
    // if no alternate has been provided use "INT".  Note that use of SIGINT won't
    // get received because the JVM won't propagate to background threads, buy it's
    // the best we can do.  We'll still issue a warning in the log.

    require(sigNum > 0, "sigNum must be greater than zero")

    if (sigNum == 9) "TERM"
    else {
      if (alternateSigint == null) {
        logger.warn("--alternate-sigint is not defined and signum %d has been " +
                 "requested.  Using SIGINT, which probably won't get received due to JVM " +
                 "preventing interrupts on background processes.  " +
                 "Define --alternate-sigint using __TOREE_OPTS__."
                   .format(sigNum))
        "INT"
      }
      else alternateSigint
    }
  }

  private def serverListener(commSocket : ServerSocket): Unit = {
    var stop = false
    while (!stop) {
      val requestData = getServerRequest(commSocket)

      // Handle each of the requests.  Note that we do not make an assumption that these are
      // mutually exclusive - although that will probably be the case for now.  Over time,
      // this should probably get refactored into a) better scala and b) token/classes for
      // each request.

      val requestJson = Json.parse(requestData).as[JsObject].value

      // Signal the kernel...
      if ( requestJson.contains("signum")) {
        val sigNum = requestJson("signum").asInstanceOf[JsNumber].value.toInt
        if ( sigNum > 0 ) {
          // If sigNum anything but 0 (for poll), use Signal.raise(signal) to signal the kernel.
          val sigName = getReconciledSignalName(sigNum)
          val sigToRaise = new Signal(sigName)
          logger.info("Server listener raising signal: '%s' (%d) for signum: %d".
                   format(sigToRaise.getName, sigToRaise.getNumber, sigNum))
          Signal.raise(sigToRaise)
        }
      }
      // Stop the listener...
      if ( requestJson.contains("shutdown")) {
        val shutdown = requestJson("shutdown").asInstanceOf[JsNumber].value.toInt
        if ( shutdown == 1 ) {
          // The server has been instructed to shutdown the kernel, so let's stop
          // the listener so that it doesn't interfere with poll() calls.
          logger.info("Stopping server listener.")
          stop = true
        }
      }
    }
  }

  def main(args: Array[String]) {
    val commSocket = initProfile(args)

    // if commSocket is not null, start a thread to listen on socket
    if ( commSocket != null ){
      val serverListenerThread = new Thread {
        override def run() {
          serverListener(commSocket)
        }
      }
      logger.info("Starting server listener...")
      serverListenerThread.start()
    }

    logger.info("Toree kernel arguments (final):")
    toreeArgs.foreach(logger.info(_))
    logger.info("---------------------------")
    Main.main(toreeArgs.toArray)
  }
}
