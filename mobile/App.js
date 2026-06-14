import React, { useRef } from 'react';
import { StyleSheet, StatusBar, Platform } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';

export default function App() {
  const webViewRef = useRef(null);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={['top', 'bottom', 'left', 'right']}>
        <StatusBar barStyle="light-content" backgroundColor="#121212" />
        <WebView
          ref={webViewRef}
          userAgent="localtunnel"
          source={{
            uri: `https://silver-readers-fold.loca.lt?v=${Date.now()}`,
            headers: { 'Bypass-Tunnel-Reminder': 'true' }
          }}
          style={styles.webview}
          // Enable camera/microphone in WebView for face/video analysis
          allowsInlineMediaPlayback={true}
          mediaPlaybackRequiresUserAction={false}
          domStorageEnabled={true}
          javaScriptEnabled={true}
          originWhitelist={['*']}
          bounces={true}
          overScrollMode="always"
          showsVerticalScrollIndicator={false}
          showsHorizontalScrollIndicator={false}
          scrollEnabled={true}
        />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
  },
  webview: {
    flex: 1,
    backgroundColor: 'transparent',
  },
}); 
