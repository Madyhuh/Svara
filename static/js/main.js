// Global Svara Client Support

// Register Service Worker for PWA compliance
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(reg => console.log('[Svara PWA] Service Worker registered:', reg.scope))
      .catch(err => console.warn('[Svara PWA] Service Worker registration skipped:', err));
  });
}

// Global Text-to-Speech synthesis helper
window.speakSvaraText = function(text) {
  if (!('speechSynthesis' in window)) {
    alert('Speech synthesis is not supported in this browser.');
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
};
