/**
 * Copyright (c) Jupyter Development Team.
 * Distributed under the terms of the Modified BSD License.
 */

package launcher

import java.net.ServerSocket
import java.util.UUID.randomUUID
import play.api.libs.json._


case class KernelProfile(hb_port : Int, control_port : Int,
                         iopub_port : Int, stdin_port : Int,
                         shell_port : Int, key : String,
                         kernel_name : String, signature_scheme : String,
                         transport : String, ip : String)

object KernelProfile{

  def getFivePort() : Array[Int] = {
    val total = 5
    val portArray = new Array[Int](total)
    val socketArray = new Array[ServerSocket](total)

    for(i <- 0 until total){
      socketArray(i) = new ServerSocket(0)
      portArray(i) = socketArray(i).getLocalPort
    }
    // Now close all sockets
    for(i <- 0 until total){
      val temp = socketArray(i).getLocalPort
      socketArray(i).close()
      println("Port %s closed...".format(temp))
    }
    portArray
  }


  def newKey() : String = randomUUID.toString

  def createJsonProfile() : String = {

    implicit val writes = Json.writes[KernelProfile]

    val fivePorts = getFivePort()

    val newKernelProfile = new KernelProfile(
      hb_port = fivePorts(0), control_port = fivePorts(1), iopub_port = fivePorts(2),
      stdin_port = fivePorts(3), shell_port = fivePorts(4), key = newKey(),
      kernel_name = "Apache Toree Scala", transport = "tcp", ip = "0.0.0.0",
      signature_scheme = "hmac-sha256"
    )
    Json.prettyPrint(Json.toJson(newKernelProfile))
  }
}
