package com.vybedev.coach.reader

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.PermissionController
import kotlinx.coroutines.launch

/** The one screen: the secret, access to Health Connect, Test and Sync now. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // No screenshots, recents thumbnail or screen capture of the secret field (security review).
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        setContent { MaterialTheme { Surface(Modifier.fillMaxSize()) { ReaderScreen() } } }
    }
}

@Composable
private fun ReaderScreen() {
    val context = LocalContext.current
    val store = remember { Store(context) }
    val scope = rememberCoroutineScope()
    var secret by remember { mutableStateOf("") }
    var hasSecret by remember { mutableStateOf(store.hasSecret) }
    // Health Connect permissions the reader has: null until checked.
    var granted by remember { mutableStateOf<Set<String>?>(null) }
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf(store.lastResult) }
    var week by remember { mutableStateOf("") }
    // A background sync that sent nothing: loaded once, kept across recreation (rotation, dark
    // mode), and cleared from the store only once it is on screen.
    var problem by rememberSaveable { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) { if (problem == null) problem = store.backgroundProblem }
    LaunchedEffect(problem) { if (!problem.isNullOrEmpty()) store.backgroundProblem = "" }
    val available = remember { HealthReader.available(context) }
    // The background read permission is asked for only where Health Connect supports it.
    val background = remember { available && Background.supported(context) }

    val missing = HealthReader.READS.filterKeys { granted?.contains(it) != true }
    val inBackground = granted?.contains(Background.PERMISSION) == true
    val askBackground = background && !inBackground
    val ask = missing.keys + (if (askBackground) setOf(Background.PERMISSION) else emptySet())

    val askAccess = rememberLauncherForActivityResult(
        PermissionController.createRequestPermissionResultContract(),
    ) { allowed -> granted = granted.orEmpty() + allowed }

    LaunchedEffect(available) {
        if (available) granted = HealthReader(context).granted()
    }

    // Once the check is done: the twice-daily sync runs only with every permission and a secret.
    LaunchedEffect(granted, hasSecret) {
        if (granted != null) Background.schedule(context, background && missing.isEmpty() && inBackground && hasSecret)
    }

    val window = (context as? ComponentActivity)?.window

    fun work(show: (String) -> Unit = { result = it }, job: suspend () -> String) {
        busy = true
        // Health Connect reads only while the app is on screen, so the screen stays awake.
        window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        scope.launch {
            try {
                show(runCatching { job() }.getOrElse { "Failed: ${it.message ?: it.javaClass.simpleName}" })
            } finally {
                // Also when the screen goes away mid-sync, so it never stays awake for good.
                window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                busy = false
            }
        }
    }

    Column(
        Modifier.padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Coach reader", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Reads steps, heart rate, sleep and exercise from Health Connect and sends them to " +
                "your coach. " +
                "Open Mi Fitness first, so the band's latest data is in Health Connect.",
        )
        Text("Sends to ${java.net.URI(BuildConfig.COACH_URL).host} only.", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(
            value = secret,
            onValueChange = { secret = it },
            label = { Text(if (hasSecret) "Secret saved (type to replace it)" else "Secret (tci_...)") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            // A password field: the keyboard doesn't suggest, learn or sync what's typed.
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, autoCorrectEnabled = false),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedButton(
            enabled = !busy && secret.isNotBlank(),
            onClick = {
                store.saveSecret(secret)
                secret = ""
                hasSecret = true
                result = "Secret saved."
            },
        ) { Text("Save the secret") }

        when {
            !available -> Text("Health Connect isn't installed or needs an update (Play Store).")
            granted == null -> Unit
            // Only the missing ones, so an update that reads a new type asks for just that.
            ask.isNotEmpty() -> Button(onClick = { askAccess.launch(ask) }) {
                val what = missing.values.joinToString()
                Text(
                    when {
                        what.isEmpty() -> "Allow Health Connect to let the reader sync in the background"
                        askBackground -> "Allow Health Connect to read $what, and in the background"
                        else -> "Allow Health Connect to read $what"
                    },
                )
            }
            else -> Text("Health Connect: steps, heart rate, sleep and exercise allowed.")
        }
        if (available && granted != null) {
            Text(
                when {
                    !background -> "This phone's Health Connect doesn't let apps read in the background, " +
                        "so the reader syncs only when you open it and tap Sync now."
                    inBackground && missing.isEmpty() -> "It also syncs by itself about every " +
                        "${Background.EVERY_HOURS} hours; Android picks the time, so it can come late."
                    else -> "Allow the above and it also syncs by itself, about every ${Background.EVERY_HOURS} hours."
                },
                style = MaterialTheme.typography.bodySmall,
            )
        }

        OutlinedButton(enabled = !busy && hasSecret, onClick = { work { Sync.test(context) } }) {
            Text("Test the secret")
        }
        Button(enabled = !busy && hasSecret && granted != null && missing.isEmpty(), onClick = { work { Sync.run(context) } }) {
            Text(if (busy) "Working..." else "Sync now")
        }
        if (busy) {
            Text(
                "Keep this screen open until it finishes: Health Connect only lets the app read " +
                    "while it's on screen. The first sync reads a day of history and takes longest.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Text(result, style = MaterialTheme.typography.bodyMedium)
        problem?.takeIf { it.isNotEmpty() && it != result }?.let {
            Text("Since you last looked: $it", style = MaterialTheme.typography.bodyMedium)
        }
        // Four reads, so only when tapped (spec "One screen").
        OutlinedButton(enabled = !busy && missing.isEmpty() && granted != null, onClick = {
            work(show = { week = it }) { Sync.week(context) }
        }) { Text("In Health Connect, last 7 days") }
        if (week.isNotEmpty()) Text(week, style = MaterialTheme.typography.bodyMedium)
        Text("Version ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)
    }
}
