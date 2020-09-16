/**
  * Copyright (c) Jupyter Development Team.
  * Distributed under the terms of the Modified BSD License.
  */

package launcher.utils
import scala.util.Random
import java.nio.charset.StandardCharsets
import java.security.Key
import java.security.KeyFactory
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.SecretKeySpec
import play.api.libs.json._
import org.apache.toree.utils.LogLike


case class Payload(key : String, conn_info : String, version : Int = 1)

object Payload {

  def createJson(key: String, conn_info: String) : String = {
    implicit val writes = Json.writes[Payload]
    val newPayload = new Payload(key = key, conn_info = conn_info)
    Json.prettyPrint(Json.toJson(newPayload))
  }
}


object SecurityUtils extends LogLike {

  def encrypt(publicKey: String, jsonContent: String): String = {
    logger.info("publicKey: %s".format(publicKey))
    // val encodedKey = Base64.decodeBase64(publicKey)


    // val key: PublicKey = KeyFactory.getInstance(ALGORITHM)
    //  .generatePublic(new X509EncodedKeySpec(publicKey.getBytes(StandardCharsets.UTF_8)));

    // Generate an AES key and encrypt the connection information...
    val random: Random = new Random()
    val preKey: Array[Byte] = new Array[Byte](16)
    random.nextBytes(preKey)
    logger.info("aes_key: '%s'".format(preKey))
    val aesKey: Key = new SecretKeySpec(preKey, "AES")
    val aesCipher: Cipher = Cipher.getInstance("AES")
    aesCipher.init(Cipher.ENCRYPT_MODE, aesKey)
    val connInfo = Base64.getEncoder.encodeToString(aesCipher.doFinal(jsonContent.getBytes(StandardCharsets.UTF_8)))

    // Encrypt the AES key using the public key...
    val encodedPK: Array[Byte] = publicKey.getBytes(StandardCharsets.UTF_8)
    val b64Key = Base64.getDecoder.decode(encodedPK)
    val keySpec: X509EncodedKeySpec = new X509EncodedKeySpec(b64Key)
    val keyFactory: KeyFactory = KeyFactory.getInstance("RSA")
    val rsaKey: PublicKey = keyFactory.generatePublic(keySpec)

    val rsaCipher: Cipher = Cipher.getInstance("RSA")
    rsaCipher.init(Cipher.ENCRYPT_MODE, rsaKey)
    val key = Base64.getEncoder.encodeToString(rsaCipher.doFinal(aesKey.getEncoded()))
    Base64.getEncoder.encodeToString(Payload.createJson(key, connInfo).getBytes(StandardCharsets.UTF_8))
    /*
    val file = new java.io.File(profilePath)
    val fileName = file.getName()
    val tokens = fileName.split("kernel-")
    val key = tokens(1).substring(0, 16)
    val aesKey: Key = new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "AES")

    logger.info("Raw Payload: '%s'".format(clearText))
    // logger.info("AES Key: '%s'".format(key))
    cipher.init(Cipher.ENCRYPT_MODE, aesKey)
    Base64.getEncoder.encodeToString(cipher.doFinal(clearText.getBytes(StandardCharsets.UTF_8)))
     */
  }
/*
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
 */
}
