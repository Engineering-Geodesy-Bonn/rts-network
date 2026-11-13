# The dashboard calls these methods from JavaScript (window.RTSAndroid), so R8 must keep them.
-keepattributes JavascriptInterface
-keepclassmembers class de.unibonn.igg.rtsdashboard.DownloadBridge {
    @android.webkit.JavascriptInterface <methods>;
}
