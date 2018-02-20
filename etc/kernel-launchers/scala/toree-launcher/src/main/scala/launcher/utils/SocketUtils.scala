/**
  * Copyright (c) Jupyter Development Team.
  * Distributed under the terms of the Modified BSD License.
  */

package launcher.utils

import java.io.PrintStream
import java.net.{InetAddress, ServerSocket, Socket}

import scala.util.Random


object SocketUtils {
  val PORT_DEFAULT_LOWER_BOUND: Int = 1024
  val PORT_DEFAULT_UPPER_BOUND: Int = 65535
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

  def findRandomPort(): Int = {
    val socket = new ServerSocket(0)
    val port = socket.getLocalPort

    // now Close the port
    socket.close()
    println("Port %s closed...".format(port)) // scalastyle:off

    return port
  }

  def findPortInRange(portLowerBound: Int = PORT_DEFAULT_LOWER_BOUND,
                      portUpperBound: Int = PORT_DEFAULT_UPPER_BOUND): Int = {

    var foundAvailable: Boolean = false
    var port = -1

    while (foundAvailable == false) {

      val randomPort = getRandomPortInRange(portLowerBound, portUpperBound)

      try {

        // try a randomPort
        println("Trying port %s ...".format(randomPort)) // scalastyle:off
        val socket = new ServerSocket(randomPort)
        println("port %s is available".format(randomPort)) // scalastyle:off

        // now Close the port
        socket.close()
        println("Port %s closed...".format(randomPort)) // scalastyle:off

        // return the port to be used
        port = randomPort
        foundAvailable = true

      } catch {
        case _ : Throwable => println("port %s is in use".format(randomPort)) // scalastyle:off
      }
    }

    return port
  }

  private def getRandomPortInRange(portLowerBound: Int = PORT_DEFAULT_LOWER_BOUND,
                                   portUpperBound: Int = PORT_DEFAULT_UPPER_BOUND): Int = {

    val portRange = portUpperBound - portLowerBound
    val randomPort = random.nextInt(portRange)
    val port = portLowerBound + randomPort

    return port
  }
}
