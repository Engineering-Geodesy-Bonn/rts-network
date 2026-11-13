package de.unibonn.igg.rtsdashboard

import android.content.ContentValues
import android.content.Context
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.widget.Toast

/**
 * Saves the downloads of the dashboard to Downloads/RTS, since WebView ignores `<a download>`.
 * Available to the dashboard as `window.RTSAndroid` (see rts-dashboard/src/lib/api.ts).
 */
class DownloadBridge(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())

    /** Text files (CSV) */
    @JavascriptInterface
    fun saveFile(filename: String, content: String) {
        save(filename, content.toByteArray(Charsets.UTF_8), "text/csv")
    }

    /** Binary files (e.g. the ZIP export of a session), base64 encoded by the dashboard */
    @JavascriptInterface
    fun saveBase64(filename: String, base64: String, mimeType: String?) {
        val data = try {
            Base64.decode(base64, Base64.DEFAULT)
        } catch (_: IllegalArgumentException) {
            toast(context.getString(R.string.download_failed, filename))
            return
        }
        save(filename, data, mimeType?.ifBlank { null } ?: "application/octet-stream")
    }

    private fun save(filename: String, data: ByteArray, mimeType: String) {
        val name = filename.replace(Regex("""[\\/:*?"<>|]"""), "_")
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, name)
            put(MediaStore.Downloads.MIME_TYPE, mimeType)
            put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/RTS")
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
        val saved = uri != null && try {
            resolver.openOutputStream(uri)!!.use { it.write(data) }
            true
        } catch (_: Exception) {
            resolver.delete(uri, null, null)
            false
        }
        toast(context.getString(if (saved) R.string.download_saved else R.string.download_failed, name))
    }

    private fun toast(message: String) {
        main.post { Toast.makeText(context, message, Toast.LENGTH_LONG).show() }
    }
}
