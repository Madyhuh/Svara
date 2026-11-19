// Svara Reverse Translator (Text / Voice to Sign)

const inputArea = document.getElementById('trans-input');
const langSelect = document.getElementById('trans-lang-select');
const btnTranslate = document.getElementById('btn-translate-text');
const btnVoice = document.getElementById('btn-voice-input');
const micIcon = document.getElementById('mic-icon');
const micLabel = document.getElementById('mic-label');

const stageToken = document.getElementById('stage-token');
const stageFlagContainer = document.getElementById('stage-flag-container');
const stageDescription = document.getElementById('stage-description');
const stageSteps = document.getElementById('stage-steps');
const chipsContainer = document.getElementById('timeline-chips');
const lblFrameIndex = document.getElementById('lbl-sequence-index');

const btnPrev = document.getElementById('btn-prev-frame');
const btnPlay = document.getElementById('btn-play-pause');
const btnNext = document.getElementById('btn-next-frame');

let sequence = [];
let currentIndex = 0;
let isPlaying = false;
let playInterval = null;

async function executeTranslation() {
  const query = inputArea.value.trim();
  const lang = langSelect.value;
  if (!query) return;

  try {
    const res = await fetch('/api/text-to-sign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: query, language: lang })
    });
    const data = await res.json();
    sequence = data.sequence || [];
    currentIndex = 0;
    renderChips();
    displayCurrentFrame();
  } catch (err) {
    console.error('Translation error:', err);
  }
}

function renderChips() {
  chipsContainer.innerHTML = '';
  sequence.forEach((item, idx) => {
    const chip = document.createElement('button');
    chip.className = `timeline-chip ${idx === currentIndex ? 'active' : ''}`;
    chip.textContent = item.label;
    chip.addEventListener('click', () => {
      currentIndex = idx;
      displayCurrentFrame();
    });
    chipsContainer.appendChild(chip);
  });
}

function displayCurrentFrame() {
  if (sequence.length === 0) {
    stageToken.textContent = '—';
    stageFlagContainer.innerHTML = '<span class="sign-verification-flag flag-verified">Awaiting Query</span>';
    stageDescription.textContent = 'Enter text on the left to begin the manual sign sequence.';
    stageSteps.textContent = '';
    lblFrameIndex.textContent = 'Frame 0 of 0';
    return;
  }

  const current = sequence[currentIndex];
  stageToken.textContent = current.label;
  lblFrameIndex.textContent = `Frame ${currentIndex + 1} of ${sequence.length}`;

  if (current.is_verified) {
    stageFlagContainer.innerHTML = '<span class="sign-verification-flag flag-verified">✓ Verified Sign Demonstration</span>';
  } else {
    stageFlagContainer.innerHTML = '<span class="sign-verification-flag flag-unsupported">⚠ Pending Verification / Extensible</span>';
  }

  stageDescription.textContent = current.description || '';
  stageSteps.textContent = current.steps || '';

  // Update chip highlights
  const chips = chipsContainer.querySelectorAll('.timeline-chip');
  chips.forEach((c, i) => {
    if (i === currentIndex) c.classList.add('active');
    else c.classList.remove('active');
  });
}

function nextFrame() {
  if (sequence.length === 0) return;
  if (currentIndex < sequence.length - 1) {
    currentIndex++;
  } else {
    currentIndex = 0; // Loop or stop
    if (isPlaying) togglePlay();
  }
  displayCurrentFrame();
}

function prevFrame() {
  if (sequence.length === 0) return;
  if (currentIndex > 0) {
    currentIndex--;
  } else {
    currentIndex = sequence.length - 1;
  }
  displayCurrentFrame();
}

function togglePlay() {
  if (sequence.length === 0) return;
  isPlaying = !isPlaying;
  if (isPlaying) {
    btnPlay.textContent = 'Pause';
    btnPlay.classList.add('btn-primary');
    btnPlay.classList.remove('btn-honey');
    playInterval = setInterval(nextFrame, 1400);
  } else {
    btnPlay.textContent = 'Play Sequence';
    btnPlay.classList.remove('btn-primary');
    btnPlay.classList.add('btn-honey');
    clearInterval(playInterval);
  }
}

// Speech Recognition (Web Speech API)
let recognitionInstance = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognitionInstance = new SpeechRec();
  recognitionInstance.continuous = false;
  recognitionInstance.interimResults = false;

  recognitionInstance.onstart = () => {
    micLabel.textContent = 'Listening...';
    btnVoice.style.borderColor = 'var(--antique-brass)';
  };

  recognitionInstance.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    inputArea.value = transcript;
    executeTranslation();
  };

  recognitionInstance.onend = () => {
    micLabel.textContent = 'Voice Input';
    btnVoice.style.borderColor = 'var(--border-strong)';
  };
}

btnVoice?.addEventListener('click', () => {
  if (!recognitionInstance) {
    alert('Speech recognition is not supported in this browser.');
    return;
  }
  try {
    recognitionInstance.start();
  } catch(e) {
    recognitionInstance.stop();
  }
});

btnTranslate?.addEventListener('click', executeTranslation);
btnNext?.addEventListener('click', nextFrame);
btnPrev?.addEventListener('click', prevFrame);
btnPlay?.addEventListener('click', togglePlay);
