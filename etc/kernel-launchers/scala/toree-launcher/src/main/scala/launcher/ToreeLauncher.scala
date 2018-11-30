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

// scalastyle:off println

object ToreeLauncher {

  val minPortRangeSize = sys.env.getOrElse("EG_MIN_PORT_RANGE_SIZE", "1000").toInt
  val kernelTempDir : String = "eg-kernel"
  var profilePath : String = _
  var portLowerBound : Int = -1
  var portUpperBound : Int = -1
  var responseAddress : String = _
  var alternateSigint : String = _
  var initMode : String = "lazy"
  var disableGatewaySocket : Boolean = false
  var toreeArgs = ArrayBuffer[String]()

  private def isPathExist(filePath : String) : Boolean = Files.exists(Paths.get(filePath))

  private def writeToFile(outputPath : String, content : String): Unit = {
    val file = new File(outputPath)
    if(!isPathExist(file.getParentFile.toString)) {
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
      ports.foreach(println)
      this.portLowerBound = ports(0).toInt
      this.portUpperBound = ports(1).toInt

      if (this.portLowerBound != this.portUpperBound) {  // Range of zero disables port restrictions
         if (this.portLowerBound < 0 || this.portUpperBound < 0 ||
            (this.portUpperBound - this.portLowerBound < minPortRangeSize)) {
            println("Invalid port range, use --port-range <LowerBound>..<UpperBound>, range must "
              + "be >= EG_MIN_PORT_RANGE_SIZE ($minPortRangeSize)")
            sys.exit(-1)
         }
      }

  }

  private def initArguments(args: Array[String]): Unit = {

    println("Toree launcher arguments (initial):")
    args.foreach(println)
    println("---------------------------")

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
          toreeArgs += profilePath  // This will be replaced in determineConnectionFile()

        // Alternate sigint is a straight pass-thru to toree
        case "--alternate-sigint" =>
          i += 1
          alternateSigint = args(i).trim
          toreeArgs += arg
          toreeArgs += alternateSigint

        // Initialization mode requires massaging for toree
        case "--RemoteProcessProxy.spark-context-initialization-mode" =>
          i += 1
          initMode = args(i).trim
          initMode match {
            case "none" =>
              toreeArgs += "--nosparkcontext"
            case _ =>
              toreeArgs += "--spark-context-initialization-mode"
              toreeArgs += initMode
          }

        // Port range doesn't apply to toree
        case "--RemoteProcessProxy.port-range" =>
          i += 1
          initPortRange(args(i).trim)

        // Response address doesn't apply to toree
        case "--RemoteProcessProxy.response-address" =>
          i += 1
          responseAddress = args(i).trim

        // Disable gateway socket doesn't apply to toree
        case "--RemoteProcessProxy.disable-gateway-socket" => disableGatewaySocket = true

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

  private def determineConnectionFile(connectionFile: String): String = {
    // See if parent directory exists, if so use connectionFile as is, else create a temporary
    // directory and replace the parent path with that value (preserving the filename). If
    // creation of the temporary directory is necessary, locate the original connection
    // file argument and replace with new value.

    var newConnectionFile = connectionFile
    val file = new File(connectionFile)
    if(!isPathExist(file.getParentFile.toString)) {
      // Directory does not exist, so create temp directory instead.
      val tmpPath = Files.createTempDirectory(kernelTempDir)
      // tmpPath.toFile.deleteOnExit() doesn't appear to work, use system hook
      sys.addShutdownHook{
        deleteDirRecur(tmpPath.toFile)
      }
      val fileName = Paths.get(connectionFile).getFileName.toString
      val newPath = Paths.get(tmpPath.toString, fileName)
      newConnectionFile = newPath.toString
      // Locate --profile and replace next element with new name
      toreeArgs(toreeArgs.indexOf("--profile") + 1) = newConnectionFile
    }
    newConnectionFile
  }

  private def getPID : String = {
    // Return the current process ID. If not an integer string, gateway will ignore.
    ManagementFactory.getRuntimeMXBean.getName.split('@')(0)
  }

  private def initProfile(args : Array[String]): ServerSocket = {

    var gatewaySocket : ServerSocket = null

    initArguments(args)

    if(profilePath == null){
      println("Invalid --profile argument, now exit")
      sys.exit(-1)
    }


    if (!isPathExist(profilePath)) {
      profilePath = determineConnectionFile(profilePath)

      println("The profile %s doesn't exist, now creating it...".format(profilePath))

      val content = KernelProfile.createJsonProfile(this.portLowerBound, this.portUpperBound)
      writeToFile(profilePath, content)

      if (isPathExist(profilePath)) {
        println("%s saved".format(profilePath))
      } else {
        println("Failed to create: %s".format(profilePath))
        sys.exit(-1)
      }

      // Now need to also return the PID info in connection JSON
      val connectionJson = Json.parse(content)

      val pidJson = connectionJson.as[JsObject] ++ Json.obj("pid" -> getPID)

      var jsonContent : String = null

      if (!disableGatewaySocket) {
        // Enterprise Gateway wants to establish socket communication. Create socket and
        // convey port number back to gateway.
        gatewaySocket = SocketUtils.findSocket(this.portLowerBound, this.portUpperBound)
        val gsJson = pidJson ++ Json.obj("comm_port" -> gatewaySocket.getLocalPort)
        jsonContent = Json.toJson(gsJson).toString()
      }
      else {
        jsonContent = Json.toJson(pidJson).toString()
      }

      if (responseAddress != null){
        println("JSON Payload: '%s'".format(jsonContent))
        val payload = SecurityUtils.encrypt(profilePath, jsonContent)
        println("Encrypted Payload: '%s'".format(payload))
        SocketUtils.writeToSocket(responseAddress, payload)
      }
    }
    gatewaySocket
  }

  private def getGatewayRequest(gatewaySocket : ServerSocket): String = {
    val s = gatewaySocket.accept()
    val data = new BufferedSource(s.getInputStream).getLines.mkString
    s.close()
    data
  }

  private def getReconciledSignalName(sigNum: Int): String = {
    // To raise the signal, we must map the signal number back to the appropriate
    // name as follows:  Take the common case and assume interrupt and check if an
    // alternate interrupt signal has been given. If sigNum = 9, use "KILL", else
    // if no alternate has been provided use "INT".  Note that use of SIGINT won't
    // get received because the JVM won't propagate to background threads, buy it's
    // the best we can do.  We'll still issue a warning in the log.

    require(sigNum > 0, "sigNum must be greater than zero")

    if (sigNum == 9) "KILL"
    else {
      if (alternateSigint == null) {
        println("WARNING: --alternate-sigint is not defined and signum %d has been " +
                 "requested.  Using SIGINT, which probably won't get received due to JVM " +
                 "preventing interrupts on background processes.  " +
                 "Define --alternate-sigint using __TOREE_OPTS__."
                   .format(sigNum))
        "INT"
      }
      else alternateSigint
    }
  }

  private def gatewayListener(gatewaySocket : ServerSocket): Unit = {
    var stop = false
    while (!stop) {
      val requestData = getGatewayRequest(gatewaySocket)

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
          println("Gateway listener raising signal: '%s' %d".
                   format(sigToRaise.getName, sigToRaise.getNumber))
          Signal.raise(sigToRaise)
        }
      }
      // Stop the listener...
      if ( requestJson.contains("shutdown")) {
        val shutdown = requestJson("shutdown").asInstanceOf[JsNumber].value.toInt
        if ( shutdown == 1 ) {
          // Enterprise gateway has been instructed to shutdown the kernel, so let's stop
          // the listener so that it doesn't interfere with poll() calls.
          println("Stopping gateway listener.")
          stop = true
        }
      }
    }
  }

  def main(args: Array[String]) {
    val gatewaySocket = initProfile(args)

    // if gatewaySocket is not null, start a thread to listen on socket
    if ( gatewaySocket != null ){
      val gatewayListenerThread = new Thread {
        override def run() {
          gatewayListener(gatewaySocket)
        }
      }
      println("Starting gateway listener...")
      gatewayListenerThread.start()
    }

    println("Toree kernel arguments (final):")
    toreeArgs.foreach(println)
    println("+++++++++++++++++++++++++++")
    Main.main(toreeArgs.toArray)
  }
}
// scalastyle:on println
