/**
  * Copyright (c) Jupyter Development Team.
  * Distributed under the terms of the Modified BSD License.
  */

package launcher.utils

import java.nio.charset.StandardCharsets
import java.security.Key
import java.util.Base64

import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec

import org.apache.toree.utils.LogLike

object SecurityUtils extends LogLike {

  def encrypt(profilePath: String, value: String): String = {
    if (profilePath.indexOf("kernel-") == -1) {
      logger.error("Invalid connection file name '%s', now exit.".format(profilePath)) // scalastyle:off
      sys.exit(-1)
    }

    val clearText = getClearText(value)
    val cipher: Cipher = Cipher.getInstance("AES")
    val file = new java.io.File(profilePath)
    val fileName = file.getName()
    val tokens = fileName.split("kernel-")
    val key = tokens(1).substring(0, 16)
    val aesKey: Key = new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "AES")

    logger.info("Raw Payload: '%s'".format(clearText))
    // logger.info("AES Key: '%s'".format(key))
    cipher.init(Cipher.ENCRYPT_MODE, aesKey)
    Base64.getEncoder.encodeToString(cipher.doFinal(clearText.getBytes(StandardCharsets.UTF_8)))
  }

  private def getClearText(value: String): String = {
    val len = value.length()

    if (len % 16 == 0) {
      // If the length of the string is already a multiple of 16, then
      // just return it.
      value
    }
    else {
      // Ensure that the length of the data that will be encrypted is a
      // multiple of 16 by padding with '%' on the right.
      //
      // Note that the padding is not needed in Scala but Python and R
      // need padding. In order to keep things consistent across all the
      // languages(so that EG on the receiving end can behave the same
      // way regardless of the language), we are also padding for Scala.
      val targetLength = (len / 16 + 1) * 16
      val clearText = value.padTo(targetLength, "%").mkString
      clearText
    }
  }
}
