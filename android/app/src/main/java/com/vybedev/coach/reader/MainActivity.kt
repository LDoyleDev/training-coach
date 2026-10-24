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
    var granted by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf(store.lastResult) }
    val available = remember { HealthReader.available(context) }

    val askAccess = rememberLauncherForActivityResult(
        PermissionController.createRequestPermissionResultContract(),
    ) { allowed -> granted = allowed.containsAll(HealthReader.PERMISSIONS) }

    LaunchedEffect(available) {
        if (available) granted = HealthReader(context).granted()
    }

    fun work(job: suspend () -> String) {
        busy = true
        scope.launch {
            result = runCatching { job() }.getOrElse { "Failed: ${it.message ?: it.javaClass.simpleName}" }
            busy = false
        }
    }

    Column(
        Modifier.padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Coach reader", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Reads steps and heart rate from Health Connect and sends them to your coach. " +
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
            !granted -> Button(onClick = { askAccess.launch(HealthReader.PERMISSIONS) }) {
                Text("Allow Health Connect access")
            }
            else -> Text("Health Connect: steps and heart rate allowed.")
        }

        OutlinedButton(enabled = !busy && hasSecret, onClick = { work { Sync.test(context) } }) {
            Text("Test the secret")
        }
        Button(enabled = !busy && hasSecret && granted, onClick = { work { Sync.run(context) } }) {
            Text(if (busy) "Working..." else "Sync now")
        }
        Text(result, style = MaterialTheme.typography.bodyMedium)
        Text("Version ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)
    }
}
