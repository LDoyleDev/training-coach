package com.vybedev.coach.reader

import android.os.Bundle
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
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Why Coach reader reads your health data", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "It reads your steps and heart rate and sends them only to the coach " +
                                "address you entered, signed with your own secret. It writes nothing " +
                                "to Health Connect, keeps no copy, and sends nothing anywhere else.",
                            Modifier.padding(top = 12.dp),
                        )
                    }
                }
            }
        }
    }
}
