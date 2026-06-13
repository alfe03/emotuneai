import React, { useRef } from 'react';
import { StyleSheet, SafeAreaView, StatusBar, Platform } from 'react-native';
import { WebView } from 'react-native-webview';

export default function App() {
  const webViewRef = useRef(null);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#121212" />
      <WebView 
        ref={webViewRef}
        userAgent="localtunnel"
        source={{ 
          uri: 'https://silver-readers-fold.loca.lt',
          headers: { 'Bypass-Tunnel-Reminder': 'true' }
        }} 
        style={styles.webview}
        // Enable camera/microphone in WebView for face/video analysis
        allowsInlineMediaPlayback={true}
        mediaPlaybackRequiresUserAction={false}
        domStorageEnabled={true}
        javaScriptEnabled={true}
        originWhitelist={['*']}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
    paddingTop: Platform.OS === 'android' ? StatusBar.currentHeight : 0,
  },
  webview: {
    flex: 1,
  },
});
// 
