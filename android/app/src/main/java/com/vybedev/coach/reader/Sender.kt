package com.vybedev.coach.reader

import kotlinx.serialization.json.JsonObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

const val INGEST_PATH = "/api/ingest/health-connect"
private const val MOST_READ = 4_096 // of the coach's answer: a hostile host can't fill the memory

/**
 * Whether [address] is the coach's ingest on [host] and nothing else: HTTPS, no user part (as in
 * `https://coach@evil.example`), no port, the ingest's path, no query (ADR-0070).
 */
fun usableAddress(address: String, host: String): Boolean {
    val uri = runCatching { URI(address) }.getOrNull() ?: return false
    return uri.scheme == "https" && uri.rawUserInfo == null && uri.host == host && uri.port == -1 &&
        uri.rawPath == INGEST_PATH && uri.rawQuery == null && uri.rawFragment == null
}

/** Posts to the coach with the secret as a bearer token. Blocking: call it off the main thread. */
fun send(secret: String, body: JsonObject, address: String = BuildConfig.COACH_URL): Answer {
    require(usableAddress(address, URI(BuildConfig.COACH_URL).host)) { "not the coach's address" }
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
        val text = stream?.bufferedReader()?.use { reader ->
            val buffer = CharArray(MOST_READ)
            String(buffer, 0, reader.read(buffer).coerceAtLeast(0))
        }.orEmpty()
        Answer(status, text.take(300))
    } catch (e: IOException) {
        Answer(0, e.message ?: "no network")
    } finally {
        connection.disconnect()
    }
}
