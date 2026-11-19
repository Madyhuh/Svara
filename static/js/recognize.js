// Svara Recognition Studio Integration
// Connects MediaPipe Hands landmarks with Svara Recognition Adapter

const video = document.getElementById('webcam');
const canvas = document.getElementById('landmark-canvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const btnStart = document.getElementById('btn-start-camera');
const btnStop = document.getElementById('btn-stop-camera');
const promptEl = document.getElementById('camera-prompt');
const streamState = document.getElementById('studio-stream-state');
const langSelect = document.getElementById('language-select');

const badgeStatus = document.getElementById('badge-status');
const displayPred = document.getElementById('display-prediction');
const statusDesc = document.getElementById('lbl-status-desc');
const confNum = document.getElementById('lbl-confidence-num');
const confBar = document.getElementById('bar-confidence');
const tapeOutput = document.getElementById('tape-output');
const btnClearTape = document.getElementById('btn-clear-tape');
const btnSpeakTape = document.getElementById('btn-speak-tape');

let cameraInstance = null;
let handsInstance = null;
let isStreaming = false;
let lastInferenceTime = 0;
let recentPredictions = [];
let accumulatedTranscript = '';

// Landmark skeleton connections for 21 MediaPipe hand points
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],        // Thumb
  [0, 5], [5, 6], [6, 7], [7, 8],        // Index
  [5, 9], [9, 10], [10, 11], [11, 12],   // Middle
  [9, 13], [13, 14], [14, 15], [15, 16], // Ring
  [13, 17], [17, 18], [18, 19], [19, 20], // Pinky
  [0, 17]                                // Palm base
];

function drawHandLandmarks(handLandmarks) {
  if (!ctx) return;
  // Draw skeleton lines
  ctx.strokeStyle = '#B08D57';
  ctx.lineWidth = 2.5;
  for (const [startIdx, endIdx] of HAND_CONNECTIONS) {
    const p1 = handLandmarks[startIdx];
    const p2 = handLandmarks[endIdx];
    ctx.beginPath();
    ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height);
    ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height);
    ctx.stroke();
  }

  // Draw landmark points
  for (let i = 0; i < handLandmarks.length; i++) {
    const pt = handLandmarks[i];
    ctx.beginPath();
    ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 4, 0, 2 * Math.PI);
    ctx.fillStyle = i === 0 ? '#1E355F' : '#FBCF84';
    ctx.fill();
    ctx.strokeStyle = '#F7F4EB';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

async function queryRecognitionAdapter(handsList) {
  const selectedLang = langSelect ? langSelect.value : 'ASL';
  try {
    const response = await fetch('/api/recognize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language: selectedLang,
        hands: handsList
      })
    });
    const result = await response.json();
    updateRecognitionUI(result);
  } catch (err) {
    console.error('[Svara Studio] Recognition network error:', err);
  }
}

function updateRecognitionUI(result) {
  if (!badgeStatus) return;

  // Status mapping
  badgeStatus.className = 'status-state-pill';

  if (result.status === 'no_hand') {
    badgeStatus.classList.add('pill-no-hand');
    badgeStatus.textContent = 'No Hand Detected';
    displayPred.textContent = '—';
    statusDesc.textContent = 'Hold your hand inside the camera frame.';
    confNum.textContent = '0.0%';
    confBar.style.width = '0%';
    recentPredictions = [];
  } 
  else if (result.status === 'model_unavailable') {
    badgeStatus.classList.add('pill-unavailable');
    badgeStatus.textContent = 'Model Unavailable';
    displayPred.textContent = '—';
    statusDesc.textContent = `${result.language} classifier awaits student two-hand training data.`;
    confNum.textContent = '0.0%';
    confBar.style.width = '0%';
    recentPredictions = [];
  } 
  else if (result.status === 'unrecognized') {
    badgeStatus.classList.add('pill-unrecognized');
    badgeStatus.textContent = 'Sign Not Recognized';
    displayPred.textContent = '—';
    statusDesc.textContent = 'Adjust fingerspelling or alignment with active signs (A, B, L).';
    const confVal = result.confidence ? (result.confidence * 100).toFixed(1) : '0.0';
    confNum.textContent = confVal + '%';
    confBar.style.width = confVal + '%';
    recentPredictions = [];
  } 
  else if (result.status === 'recognized') {
    badgeStatus.classList.add('pill-recognized');
    badgeStatus.textContent = `Recognized (${result.language})`;
    displayPred.textContent = result.prediction;
    statusDesc.textContent = `Verified sign detected with student classifier.`;
    const confVal = (result.confidence * 100).toFixed(1);
    confNum.textContent = confVal + '%';
    confBar.style.width = confVal + '%';

    // Smoothing & Transcript tape buffer
    recentPredictions.push(result.prediction);
    if (recentPredictions.length > 4) recentPredictions.shift();

    // If 3 consecutive identical predictions, append to tape
    if (
      recentPredictions.length >= 3 &&
      recentPredictions.every(p => p === result.prediction)
    ) {
      if (!accumulatedTranscript.endsWith(result.prediction)) {
        accumulatedTranscript += result.prediction;
        if (tapeOutput) tapeOutput.textContent = accumulatedTranscript;
      }
    }
  }
}

function onResults(results) {
  if (!ctx || !canvas || !video) return;
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;

  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
    // Render overlays for all detected hands (1 or 2 hands)
    for (const hand of results.multiHandLandmarks) {
      drawHandLandmarks(hand);
    }

    // Rate-limit network inference calls to every ~200ms
    const now = Date.now();
    if (now - lastInferenceTime > 200) {
      lastInferenceTime = now;
      queryRecognitionAdapter(results.multiHandLandmarks);
    }
  } else {
    // Send empty hands for accurate status
    const now = Date.now();
    if (now - lastInferenceTime > 400) {
      lastInferenceTime = now;
      queryRecognitionAdapter([]);
    }
  }
  ctx.restore();
}

async function startCamera() {
  if (!video) return;
  try {
    if (!handsInstance) {
      handsInstance = new Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });
      handsInstance.setOptions({
        maxNumHands: 2, // Supports up to 2 hands for visual landmark tracking
        modelComplexity: 1,
        minDetectionConfidence: 0.6,
        minTrackingConfidence: 0.6
      });
      handsInstance.onResults(onResults);
    }

    cameraInstance = new Camera(video, {
      onFrame: async () => {
        if (isStreaming && handsInstance) {
          await handsInstance.send({ image: video });
        }
      },
      width: 640,
      height: 480
    });

    await cameraInstance.start();
    isStreaming = true;
    if (promptEl) promptEl.style.display = 'none';
    if (streamState) {
      streamState.textContent = '● Streaming Live';
      streamState.style.color = '#FBCF84';
    }
  } catch (err) {
    console.error('Camera startup failed:', err);
    if (statusDesc) statusDesc.textContent = 'Camera initialization failed. Check permissions.';
  }
}

async function stopCamera() {
  if (cameraInstance) {
    await cameraInstance.stop();
  }
  isStreaming = false;
  if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (promptEl) promptEl.style.display = 'block';
  if (streamState) {
    streamState.textContent = '● Standby';
    streamState.style.color = '#8A98A8';
  }
  updateRecognitionUI({ status: 'no_hand' });
}

// Event Listeners
btnStart?.addEventListener('click', startCamera);
btnStop?.addEventListener('click', stopCamera);
btnClearTape?.addEventListener('click', () => {
  accumulatedTranscript = '';
  if (tapeOutput) tapeOutput.textContent = '';
});
btnSpeakTape?.addEventListener('click', () => {
  if (accumulatedTranscript) {
    window.speakSvaraText(accumulatedTranscript);
  }
});

window.addEventListener('pagehide', stopCamera);
