package com.egi.app.mesh

import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Pure-JVM crypto primitives for the mesh's per-connection encryption. Deliberately
 * built only on `java.security` + `javax.crypto` (no Android-only APIs) so the whole
 * thing is exercisable from plain JVM unit tests.
 *
 * The model: each side generates an ephemeral EC (secp256r1) key pair per GATT
 * connection, swaps public keys, and runs ECDH to agree on a shared secret. The
 * secret is hashed (SHA-256) into a 32-byte AES-256 key used with AES/GCM/NoPadding
 * for every record payload that crosses the link. Keys are never persisted; they die
 * with the connection.
 */
object MeshCrypto {

    private const val EC_ALGORITHM = "EC"
    private const val EC_CURVE = "secp256r1"
    private const val ECDH_ALGORITHM = "ECDH"
    private const val HASH_ALGORITHM = "SHA-256"
    private const val AES_ALGORITHM = "AES"
    private const val AES_TRANSFORM = "AES/GCM/NoPadding"

    /** ECDSA over SHA-256 for plan-25 record signing (separate from the ECDH path). */
    private const val SIGNATURE_ALGORITHM = "SHA256withECDSA"

    /** 96-bit nonce is the GCM-recommended size; 128-bit auth tag is the standard. */
    private const val GCM_IV_BYTES = 12
    private const val GCM_TAG_BITS = 128

    private val secureRandom = SecureRandom()

    /** Generate an ephemeral EC (secp256r1) key pair for one connection's ECDH. */
    fun generateKeyPair(): KeyPair {
        val generator = KeyPairGenerator.getInstance(EC_ALGORITHM)
        generator.initialize(ECGenParameterSpec(EC_CURVE))
        return generator.generateKeyPair()
    }

    /** X.509-encoded bytes of a public key, suitable for sending over the wire. */
    fun publicKeyBytes(pub: PublicKey): ByteArray = pub.encoded

    /** Rebuild a peer's public key from the X.509 bytes received over the wire. */
    fun decodePublicKey(bytes: ByteArray): PublicKey {
        val keyFactory = KeyFactory.getInstance(EC_ALGORITHM)
        return keyFactory.generatePublic(X509EncodedKeySpec(bytes))
    }

    /**
     * Run ECDH between our private key and the peer's public bytes, then SHA-256 the
     * raw shared secret down to a 32-byte AES-256 key. Both sides derive the same key.
     */
    fun deriveSessionKey(ourPrivate: PrivateKey, peerPublicBytes: ByteArray): ByteArray {
        val peerPublic = decodePublicKey(peerPublicBytes)
        val agreement = KeyAgreement.getInstance(ECDH_ALGORITHM)
        agreement.init(ourPrivate)
        agreement.doPhase(peerPublic, true)
        val sharedSecret = agreement.generateSecret()
        return MessageDigest.getInstance(HASH_ALGORITHM).digest(sharedSecret)
    }

    /**
     * AES-256-GCM encrypt [plaintext] under [key]. A fresh random 12-byte IV is
     * prepended to the output: `IV(12) || ciphertext+tag`. Never reuses an IV.
     */
    fun encrypt(key: ByteArray, plaintext: ByteArray): ByteArray {
        val iv = ByteArray(GCM_IV_BYTES).also { secureRandom.nextBytes(it) }
        val cipher = Cipher.getInstance(AES_TRANSFORM)
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, AES_ALGORITHM), GCMParameterSpec(GCM_TAG_BITS, iv))
        val ciphertext = cipher.doFinal(plaintext)
        return iv + ciphertext
    }

    /**
     * Inverse of [encrypt]: split off the leading 12-byte IV and AES-256-GCM decrypt
     * the remainder. Throws if the blob is truncated or the key/tag don't match.
     */
    fun decrypt(key: ByteArray, blob: ByteArray): ByteArray {
        require(blob.size > GCM_IV_BYTES) { "Encrypted blob too short" }
        val iv = blob.copyOfRange(0, GCM_IV_BYTES)
        val ciphertext = blob.copyOfRange(GCM_IV_BYTES, blob.size)
        val cipher = Cipher.getInstance(AES_TRANSFORM)
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, AES_ALGORITHM), GCMParameterSpec(GCM_TAG_BITS, iv))
        return cipher.doFinal(ciphertext)
    }

    // --- Plan-25 record signing (ECDSA over secp256r1) -----------------------
    //
    // Distinct from the ephemeral ECDH path above: an authorized device holds a
    // persistent EC signing key pair, signs a location/shelter update, and any peer
    // can verify the signature OFFLINE from the carried public key. Same curve and
    // X.509 public-key encoding as the ECDH keys, so [publicKeyBytes]/[decodePublicKey]
    // are reused for the wire format.

    /**
     * Generate an EC (secp256r1) signing key pair. Unlike [generateKeyPair] (which is
     * thrown away with the connection), this pair is meant to be persisted by the caller
     * so a device keeps a stable signing identity across sessions.
     */
    fun generateSigningKeyPair(): KeyPair {
        val generator = KeyPairGenerator.getInstance(EC_ALGORITHM)
        generator.initialize(ECGenParameterSpec(EC_CURVE))
        return generator.generateKeyPair()
    }

    /** X.509-encoded bytes of a signing public key — identical encoding to [publicKeyBytes]. */
    fun signingPublicKeyBytes(pub: PublicKey): ByteArray = publicKeyBytes(pub)

    /** Sign [message] with [privateKey] using SHA256withECDSA, returning the DER signature. */
    fun sign(privateKey: PrivateKey, message: ByteArray): ByteArray {
        val signer = Signature.getInstance(SIGNATURE_ALGORITHM)
        signer.initSign(privateKey)
        signer.update(message)
        return signer.sign()
    }

    /**
     * Verify a SHA256withECDSA [signature] over [message] against the X.509-encoded
     * [publicKeyBytes]. Returns false on any failure (bad key bytes, tampered message,
     * malformed signature) and never throws — verification is best-effort, like the
     * rest of this object's degrade-quietly contract.
     */
    fun verify(publicKeyBytes: ByteArray, message: ByteArray, signature: ByteArray): Boolean =
        try {
            val verifier = Signature.getInstance(SIGNATURE_ALGORITHM)
            verifier.initVerify(decodePublicKey(publicKeyBytes))
            verifier.update(message)
            verifier.verify(signature)
        } catch (_: Exception) {
            false
        }
}
