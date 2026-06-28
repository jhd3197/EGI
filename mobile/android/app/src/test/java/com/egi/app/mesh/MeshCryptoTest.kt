package com.egi.app.mesh

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-JVM tests for [MeshCrypto]: two parties agree on an identical ECDH session
 * key, AES-256-GCM round-trips arbitrary bytes, and a wrong key fails to decrypt.
 * Uses only `java.security`/`javax.crypto`, so it runs as a plain unit test.
 */
class MeshCryptoTest {

    @Test
    fun bothPartiesDeriveTheSameSessionKey() {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()

        val aliceKey = MeshCrypto.deriveSessionKey(
            alice.private, MeshCrypto.publicKeyBytes(bob.public),
        )
        val bobKey = MeshCrypto.deriveSessionKey(
            bob.private, MeshCrypto.publicKeyBytes(alice.public),
        )

        assertArrayEquals(aliceKey, bobKey)
        assertEquals(32, aliceKey.size) // SHA-256 → 256-bit AES key
    }

    @Test
    fun encryptDecryptRoundTripsArbitraryBytes() {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()
        val key = MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(bob.public))

        // TEST DATA — NOT REAL
        val plaintext = "Juan Pérez de prueba — registro de emergencia".toByteArray(Charsets.UTF_8)
        val blob = MeshCrypto.encrypt(key, plaintext)

        // Ciphertext is distinct from the plaintext (IV + tag + encrypted body).
        assertFalse(blob.contentEquals(plaintext))
        assertArrayEquals(plaintext, MeshCrypto.decrypt(key, blob))
    }

    @Test
    fun freshIvMakesCiphertextsDiffer() {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()
        val key = MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(bob.public))

        val plaintext = "egi-test".toByteArray(Charsets.UTF_8)
        val first = MeshCrypto.encrypt(key, plaintext)
        val second = MeshCrypto.encrypt(key, plaintext)

        // Random IV per call: same input, different ciphertext, both decrypt fine.
        assertFalse(first.contentEquals(second))
        assertArrayEquals(plaintext, MeshCrypto.decrypt(key, first))
        assertArrayEquals(plaintext, MeshCrypto.decrypt(key, second))
    }

    @Test(expected = Exception::class)
    fun wrongKeyFailsToDecrypt() {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()
        val mallory = MeshCrypto.generateKeyPair()

        val key = MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(bob.public))
        val wrongKey = MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(mallory.public))

        val blob = MeshCrypto.encrypt(key, "secret".toByteArray(Charsets.UTF_8))
        // GCM tag verification fails under the wrong key → throws.
        MeshCrypto.decrypt(wrongKey, blob)
    }

    // --- Plan-25 signing (ECDSA over secp256r1) ------------------------------

    @Test
    fun signedMessageVerifiesWithTheSignerPublicKey() {
        val signer = MeshCrypto.generateSigningKeyPair()
        // TEST DATA — NOT REAL
        val message = "shelter:la-guaira-01 capacity=120/200".toByteArray(Charsets.UTF_8)

        val signature = MeshCrypto.sign(signer.private, message)
        val pubBytes = MeshCrypto.signingPublicKeyBytes(signer.public)

        assertTrue(MeshCrypto.verify(pubBytes, message, signature))
    }

    @Test
    fun tamperedMessageFailsVerification() {
        val signer = MeshCrypto.generateSigningKeyPair()
        // TEST DATA — NOT REAL
        val message = "shelter:la-guaira-01 capacity=120/200".toByteArray(Charsets.UTF_8)
        val signature = MeshCrypto.sign(signer.private, message)
        val pubBytes = MeshCrypto.signingPublicKeyBytes(signer.public)

        val tampered = "shelter:la-guaira-01 capacity=999/200".toByteArray(Charsets.UTF_8)
        assertFalse(MeshCrypto.verify(pubBytes, tampered, signature))
    }

    @Test
    fun verifyFailsWithAnotherDevicesKeyAndNeverThrows() {
        val signer = MeshCrypto.generateSigningKeyPair()
        val other = MeshCrypto.generateSigningKeyPair()
        // TEST DATA — NOT REAL
        val message = "egi-test signed update".toByteArray(Charsets.UTF_8)
        val signature = MeshCrypto.sign(signer.private, message)

        // Wrong public key → false (not an exception).
        assertFalse(MeshCrypto.verify(MeshCrypto.signingPublicKeyBytes(other.public), message, signature))
        // Garbage key bytes → false, swallowed.
        assertFalse(MeshCrypto.verify(byteArrayOf(1, 2, 3), message, signature))
    }
}
