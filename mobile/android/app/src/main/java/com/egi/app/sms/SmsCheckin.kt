package com.egi.app.sms

/**
 * Pure parser for the SMS check-in format — no Android imports, so it is plain
 * JVM-unit-testable. This MUST mirror the server parser in `server/modules/sms.py`
 * ([parse_checkin]) field-for-field so a message parses identically whether it
 * lands at the cloud webhook or is decoded offline on the device.
 *
 * Format (case-insensitive keyword, comma- or space-separated fields):
 *     EGI CHECKIN <cedula> <name> <location>
 *     EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte
 *
 * Privacy: text-only by design — no photos or exact coordinates.
 */
object SmsCheckin {

    const val KEYWORD = "EGI CHECKIN"

    /** Parsed check-in fields. Mirrors the server's {cedula, name, location} dict. */
    data class CheckinFields(
        val cedula: String,
        val name: String,
        val location: String,
    )

    /**
     * Parse an EGI CHECKIN message into [CheckinFields], or return null when the
     * keyword is missing or no cédula can be extracted (the server raises HTTP 400
     * in those same two cases; offline we degrade to null instead of throwing).
     */
    fun parse(body: String?): CheckinFields? {
        if (body.isNullOrBlank()) return null
        val text = body.trim()
        if (!text.uppercase().startsWith(KEYWORD)) return null

        val remainder = text.substring(KEYWORD.length).trim()
        if (remainder.isEmpty()) return null

        val cedula: String
        val name: String
        val location: String

        if (remainder.contains(",")) {
            val parts = remainder.split(",").map { it.trim() }
            cedula = parts.getOrElse(0) { "" }
            name = parts.getOrElse(1) { "" }
            location = parts.getOrElse(2) { "" }
        } else {
            // Whitespace form: first token is the cédula, last token the location,
            // everything between is the name (best effort).
            val tokens = remainder.split(Regex("\\s+")).filter { it.isNotEmpty() }
            cedula = tokens.firstOrNull() ?: ""
            when {
                tokens.size >= 3 -> {
                    name = tokens.subList(1, tokens.size - 1).joinToString(" ")
                    location = tokens.last()
                }
                tokens.size == 2 -> {
                    name = tokens[1]
                    location = ""
                }
                else -> {
                    name = ""
                    location = ""
                }
            }
        }

        if (cedula.isEmpty()) return null
        return CheckinFields(cedula = cedula, name = name, location = location)
    }
}
