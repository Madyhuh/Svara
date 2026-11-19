const video = document.querySelector('#video');
const statusText = document.querySelector('#status');
const cameraMessage = document.querySelector('#camera-message');
let stream = null;

async function startCamera() {
  if (!video) return;
  if (!navigator.mediaDevices?.getUserMedia) {
    statusText.textContent = 'Camera API unavailable';
    return;
  }
  try {
    if (stream) stopCamera();
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
    video.srcObject = stream;
    await video.play();
    statusText.textContent = 'Camera ready, detector not connected';
    cameraMessage.textContent = '';
  } catch (error) {
    statusText.textContent = error.name === 'NotAllowedError' ? 'Camera permission denied' : 'Unable to access camera';
    cameraMessage.textContent = 'Check camera permissions and device availability';
  }
}
function stopCamera() {
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  if (video) video.srcObject = null;
  if (statusText) statusText.textContent = 'Camera is off';
  if (cameraMessage) cameraMessage.textContent = 'Camera is off';
}
document.querySelector('#start')?.addEventListener('click', startCamera);
document.querySelector('#stop')?.addEventListener('click', stopCamera);
window.addEventListener('pagehide', stopCamera);
