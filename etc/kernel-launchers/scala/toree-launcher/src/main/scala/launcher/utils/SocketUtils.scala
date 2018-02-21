/**
  * Copyright (c) Jupyter Development Team.
  * Distributed under the terms of the Modified BSD License.
  */

package launcher.utils

import java.io.PrintStream
import java.net.{InetAddress, ServerSocket, Socket}

import scala.util.Random


object SocketUtils {

  val random: Random = new Random (System.currentTimeMillis)

  def writeToSocket(socketAddress : String, content : String): Unit = {
    val ipPort = socketAddress.split(":")
    if (ipPort.length == 2) {
      println("Sending connection info to gateway at %s\n%s".format(socketAddress, content)) // scalastyle:off
      val ip = ipPort(0)
      val port = ipPort(1).toInt
      val s = new Socket(InetAddress.getByName(ip), port)
      val out = new PrintStream(s.getOutputStream)
      try {
        out.append(content)
        out.flush()
      } finally {
        s.close()
      }
    } else {
      println("Invalid format for response address '%s'!".format(socketAddress)) // scalastyle:off
    }
  }

  def findPort(portLowerBound: Int, portUpperBound: Int): Int = {

    val socket = findSocket(portLowerBound, portUpperBound)
    val port = socket.getLocalPort
    println("port %s is available".format(port)) // scalastyle:off

    // now Close the socket/port
    socket.close()
    println("Port %s closed...".format(port)) // scalastyle:off

    port
  }

  def findSocket(portLowerBound: Int, portUpperBound: Int): ServerSocket = {

    var foundAvailable: Boolean = false
    var socket: ServerSocket = null

    while (foundAvailable == false) {

      val candidatePort = getCandidatePort(portLowerBound, portUpperBound)

      // try candidatePort - only display 'Trying...' if in range
      if ( candidatePort > 0 )
        println("Trying port %s ...".format(candidatePort)) // scalastyle:off

      try {
        socket = new ServerSocket(candidatePort)
        // return the socket to be used
        foundAvailable = true
      } catch {
        case _ : Throwable => println("port %s is in use".format(candidatePort)) // scalastyle:off
        socket = null
      }
    }

    socket
  }

  private def getCandidatePort(portLowerBound: Int, portUpperBound: Int): Int = {

    val portRange = portUpperBound - portLowerBound
    if ( portRange <= 0 )
        return 0

    val port = portLowerBound + random.nextInt(portRange)

    port
  }
}
