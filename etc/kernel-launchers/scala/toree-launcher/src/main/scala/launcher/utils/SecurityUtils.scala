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
    // Generate an AES key and encrypt the connection information...
    logger.info("publicKey: %s".format(publicKey))
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
  }
}
