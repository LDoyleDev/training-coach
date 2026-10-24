package com.vybedev.coach.reader

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/** What Health Connect shows when the person asks why this app reads their data. */
class PermissionsRationaleActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Why Coach reader reads your health data", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "It reads your steps and heart rate and sends them only to your coach " +
                                "(coach.vybe-dev.com), with your own secret. It writes nothing to " +
                                "Health Connect and sends nothing anywhere else. It keeps only the last " +
                                "two days' step totals, so it knows what it already sent.",
                            Modifier.padding(top = 12.dp),
                        )
                    }
                }
            }
        }
    }
}
