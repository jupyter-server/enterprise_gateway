/**
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

package launcher


import java.util.UUID.randomUUID
import play.api.libs.json._
import scala.util.Random
import launcher.utils.SocketUtils


case class KernelProfile(hb_port : Int,
                         control_port : Int,
                         iopub_port : Int,
                         stdin_port : Int,
                         shell_port : Int,
                         key : String,
                         kernel_name : String,
                         signature_scheme : String,
                         transport : String,
                         ip : String)

object KernelProfile {

  def getUnusedPort(hasPortRange: Boolean = false,
                  portLowerBound: Int = -1,
                  portUpperBound: Int = -1) : Int = {

    if (hasPortRange) {
      return SocketUtils.findPortInRange(portLowerBound, portUpperBound)
    } else {
      return SocketUtils.findRandomPort
    }
  }


  def newKey() : String = randomUUID.toString

  def createJsonProfile(hasPortRange: Boolean = false,
                        portLowerBound: Int = -1,
                        portUpperBound: Int = -1) : String = {

    implicit val writes = Json.writes[KernelProfile]

    val newKernelProfile = new KernelProfile(
      hb_port = getUnusedPort(hasPortRange, portLowerBound, portUpperBound),
      control_port = getUnusedPort(hasPortRange, portLowerBound, portUpperBound),
      iopub_port = getUnusedPort(hasPortRange, portLowerBound, portUpperBound),
      stdin_port = getUnusedPort(hasPortRange, portLowerBound, portUpperBound),
      shell_port = getUnusedPort(hasPortRange, portLowerBound, portUpperBound),
      key = newKey(),
      kernel_name = "Apache Toree Scala", transport = "tcp", ip = "0.0.0.0",
      signature_scheme = "hmac-sha256"
    )
    Json.prettyPrint(Json.toJson(newKernelProfile))
  }
}
