package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Whether an address can be posted to: HTTPS only (ADR-0070), never cleartext. */
fun usableAddress(address: String): Boolean =
    address.startsWith("https://") && address.length > "https://".length && ' ' !in address

/** Posts to the ingest with the secret as a bearer token. Blocking: call it off the main thread. */
fun send(address: String, secret: String, body: JsonObject): Answer {
    require(usableAddress(address)) { "the address must start with https://" }
    val connection = URL(address).openConnection() as HttpURLConnection
    return try {
        connection.requestMethod = "POST"
        // The request carries the secret: a redirect could hand it to another host, and the coach
        // never redirects an ingest post, so a 3xx is a failure.
        connection.instanceFollowRedirects = false
        connection.connectTimeout = 20_000
        connection.readTimeout = 60_000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        connection.setRequestProperty("Authorization", "Bearer $secret")
        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        Answer(status, text.take(300))
    } catch (e: IOException) {
        Answer(0, e.message ?: "no network")
    } finally {
        connection.disconnect()
    }
}
