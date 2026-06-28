package com.egi.app.data

import java.text.Normalizer

/**
 * On-device mirror of the server's exact-dedup normalization rules
 * (`server/modules/duplicates.py`: `normalize_cedula`, `normalize_phone`, `_norm`,
 * `_exact_key`). Phase 6 of plan-27 lets the mesh client surface the same
 * high-confidence exact duplicates offline, so the canonicalization MUST agree
 * byte-for-byte with the server or a record would cluster differently on each side.
 *
 * Pure Kotlin (only `java.text` / kotlin stdlib) so it unit-tests on the JVM with
 * no Android or Room dependency. No mutation of any store — these are stateless
 * key derivations consumed by [MeshRepository.localExactDuplicates].
 */
object DedupNormalize {

    /** Nationality prefixes kept on a cédula key (server: the `"VEJGP"` set). */
    private const val CEDULA_PREFIXES = "VEJGP"

    /**
     * Canonical cédula key: optional uppercase nationality letter + digits, no
     * separators. Mirrors `normalize_cedula`: the letter (V/E/J/G/P) is kept only
     * when it precedes any digit; everything else is dropped. Returns "" when the
     * value holds no digits, so blanks never collide.
     */
    fun normalizeCedula(value: String?): String {
        if (value.isNullOrEmpty()) return ""
        val raw = Normalizer.normalize(value, Normalizer.Form.NFKD).uppercase()
        var letter = ""
        val digits = StringBuilder()
        for (ch in raw) {
            when {
                ch.isDigit() -> digits.append(ch)
                ch in CEDULA_PREFIXES && digits.isEmpty() && letter.isEmpty() -> letter = ch.toString()
            }
        }
        if (digits.isEmpty()) return ""
        return letter + digits
    }

    /**
     * Canonical phone key: digits only, last 10. Mirrors `normalize_phone` — strips
     * spaces/dashes/parens/country code and compares on the national significant
     * number. Returns "" for anything with fewer than 7 digits (too short to be real).
     */
    fun normalizePhone(value: String?): String {
        if (value.isNullOrEmpty()) return ""
        val digits = value.filter { it.isDigit() }
        if (digits.length < 7) return ""
        return digits.takeLast(10)
    }

    /**
     * Loose name key: lowercase, accents stripped (NFKD + drop combining marks),
     * whitespace collapsed. Mirrors `_norm`. Returns "" for null/blank.
     */
    fun normalizeName(value: String?): String {
        if (value.isNullOrEmpty()) return ""
        val decomposed = Normalizer.normalize(value, Normalizer.Form.NFKD)
        val noAccents = decomposed.filterNot { Character.getType(it) == Character.NON_SPACING_MARK.toInt() }
        return noAccents.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
    }

    /**
     * Strongest *exact* dedup key for a record, or null when there is none.
     * Mirrors `_exact_key`: a canonical cédula wins; otherwise a canonical phone
     * paired with a normalized name. The kind-prefixed return value keeps cédula
     * and phone keys from ever colliding.
     *
     * - cédula present  -> "cedula:<normalizedCedula>"
     * - phone + name    -> "phonename:<normalizedPhone>|<normalizedName>"
     * - neither         -> null
     *
     * [name] is the record's full name (e.g. given+family, else the `name` field);
     * it is normalized here exactly like the server's `_full_name`/`_norm`.
     */
    fun exactKey(cedula: String?, contact: String?, name: String?): String? {
        val ced = normalizeCedula(cedula)
        if (ced.isNotEmpty()) return "cedula:$ced"
        val phone = normalizePhone(contact)
        val normName = normalizeName(name)
        if (phone.isNotEmpty() && normName.isNotEmpty()) return "phonename:$phone|$normName"
        return null
    }
}
