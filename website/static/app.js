/**
 * SIGNIFY - Real-Time Sign Language to Speech Translation
 * Client-Side Application Logic & Web Speech Engine
 */

// Global State
let synth = window.speechSynthesis;
let availableVoices = [];
let autoSpeakEnabled = true;
let speechRate = 1.0;
let speechPitch = 1.0;
let lastSpokenText = "";
let currentSentence = "";
let customMap = JSON.parse(localStorage.getItem("signify_custom_map")) || {
  "0": "Hello",
  "1": "Yes",
  "2": "No",
  "3": "Thank You",
  "4": "Please Help",
  "5": "Water",
  "A": "A",
  "B": "B",
  "C": "C"
};

// DOM References
const liveSignDisplay = document.getElementById("liveSignDisplay");
const liveConfidence = document.getElementById("liveConfidence");
const sentenceDisplay = document.getElementById("sentenceDisplay");
const chatFeed = document.getElementById("chatFeed");
const soundwaveBox = document.getElementById("soundwaveBox");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const voiceSelect = document.getElementById("voiceSelect");

// Sensor bar elements
const sensorBars = {
  thumb: document.getElementById("barThumb"),
  index: document.getElementById("barIndex"),
  middle: document.getElementById("barMiddle"),
  ring: document.getElementById("barRing"),
  pinky: document.getElementById("barPinky")
};

const sensorVals = {
  thumb: document.getElementById("valThumb"),
  index: document.getElementById("valIndex"),
  middle: document.getElementById("valMiddle"),
  ring: document.getElementById("valRing"),
  pinky: document.getElementById("valPinky")
};

// ================== SPEECH SYNTHESIS ENGINE ==================

function populateVoices() {
  if (!synth) return;
  availableVoices = synth.getVoices();
  if (!voiceSelect) return;

  voiceSelect.innerHTML = "";
  
  // Prefer English voices (especially en-IN or en-US)
  availableVoices.forEach((voice, index) => {
    const option = document.createElement("option");
    option.value = index;
    option.textContent = `${voice.name} (${voice.lang})`;
    if (voice.lang.includes("en-IN") || (voice.lang.includes("en-US") && !voiceSelect.value)) {
      option.selected = true;
    }
    voiceSelect.appendChild(option);
  });
}

if (synth) {
  populateVoices();
  if (speechSynthesis.onvoiceschanged !== undefined) {
    speechSynthesis.onvoiceschanged = populateVoices;
  }
}

/**
 * Speaks text using the browser Web Speech API with soundwave animation
 */
function speakText(text) {
  if (!synth || !text || text.trim() === "") return;

  // Cancel any ongoing speech for ultra low-latency response
  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = speechRate;
  utterance.pitch = speechPitch;

  if (voiceSelect && voiceSelect.value !== "") {
    const selectedVoice = availableVoices[parseInt(voiceSelect.value)];
    if (selectedVoice) utterance.voice = selectedVoice;
  }

  // Animate soundwaves while speaking
  utterance.onstart = () => {
    if (soundwaveBox) soundwaveBox.classList.add("active");
  };

  utterance.onend = utterance.onerror = () => {
    if (soundwaveBox) soundwaveBox.classList.remove("active");
  };

  synth.speak(utterance);
  lastSpokenText = text;
}

// ================== TRANSLATION & GESTURE HANDLING ==================

let lastProcessedTimestamp = 0;
let lastProcessedLabel = "";

/**
 * Handles incoming gesture detection from ESP32 or Simulator
 */
function handleGesture(label, confidence = 95, sensors = null) {
  if (!label) return;

  // Map label to custom word/phrase if configured
  const translatedWord = customMap[label] || label;

  // Update prominent live display
  if (liveSignDisplay) {
    liveSignDisplay.textContent = translatedWord;
    liveSignDisplay.style.transform = "scale(1.08)";
    setTimeout(() => {
      liveSignDisplay.style.transform = "scale(1)";
    }, 180);
  }

  if (liveConfidence) {
    liveConfidence.textContent = `Confidence: ${confidence}% • Sign: [${label}]`;
  }

  // Update sensor telemetry bars if provided
  if (sensors && sensors.length >= 5) {
    updateSensorTelemetry(sensors);
  }

  // Append to Sentence Builder
  appendToSentence(translatedWord);

  // Add message to translation feed
  addChatMessage(translatedWord, label, confidence);

  // Auto-speak if enabled
  if (autoSpeakEnabled) {
    speakText(translatedWord);
  }
}

function updateSensorTelemetry(sensors) {
  const keys = ["thumb", "index", "middle", "ring", "pinky"];
  keys.forEach((key, idx) => {
    const val = sensors[idx] || 0;
    const pct = Math.min(100, Math.max(0, (val / 4095) * 100));
    if (sensorBars[key]) sensorBars[key].style.width = `${pct}%`;
    if (sensorVals[key]) sensorVals[key].textContent = val;
  });
}

function addChatMessage(word, originalSign, confidence) {
  if (!chatFeed) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = "chat-message";

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  msgDiv.innerHTML = `
    <div class="msg-avatar">🤟</div>
    <div class="msg-body">
      <div class="msg-text">${word}</div>
      <div class="msg-meta">ISL Sign: <strong>${originalSign}</strong> • ${confidence}% confidence • ${timeStr}</div>
    </div>
    <button class="msg-speak-btn" title="Speak again" onclick="speakText('${word}')">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
      </svg>
    </button>
  `;

  chatFeed.appendChild(msgDiv);
  chatFeed.scrollTop = chatFeed.scrollHeight;
}

// ================== SENTENCE BUILDER ==================

function appendToSentence(word) {
  if (!sentenceDisplay) return;

  // If single letter, append directly; if multi-word phrase, add with space
  if (word.length === 1 && !currentSentence.endsWith(" ")) {
    currentSentence += word;
  } else {
    currentSentence = currentSentence ? `${currentSentence} ${word}` : word;
  }
  sentenceDisplay.textContent = currentSentence;
}

function speakCurrentSentence() {
  if (currentSentence && currentSentence.trim()) {
    speakText(currentSentence);
  }
}

function addSentenceSpace() {
  if (currentSentence && !currentSentence.endsWith(" ")) {
    currentSentence += " ";
    sentenceDisplay.textContent = currentSentence;
  }
}

function sentenceBackspace() {
  if (currentSentence.length > 0) {
    currentSentence = currentSentence.slice(0, -1);
    sentenceDisplay.textContent = currentSentence || "Sign gestures to build sentence...";
  }
}

function clearSentence() {
  currentSentence = "";
  if (sentenceDisplay) sentenceDisplay.textContent = "Sign gestures to build sentence...";
}

function clearChat() {
  if (chatFeed) chatFeed.innerHTML = "";
}

// ================== CONTROLS & SETTINGS ==================

const autoSpeakToggle = document.getElementById("autoSpeakToggle");
if (autoSpeakToggle) {
  autoSpeakToggle.checked = autoSpeakEnabled;
  autoSpeakToggle.addEventListener("change", (e) => {
    autoSpeakEnabled = e.target.checked;
  });
}

const rateSlider = document.getElementById("rateSlider");
const rateVal = document.getElementById("rateVal");
if (rateSlider) {
  rateSlider.addEventListener("input", (e) => {
    speechRate = parseFloat(e.target.value);
    if (rateVal) rateVal.textContent = `${speechRate}x`;
  });
}

const pitchSlider = document.getElementById("pitchSlider");
const pitchVal = document.getElementById("pitchVal");
if (pitchSlider) {
  pitchSlider.addEventListener("input", (e) => {
    speechPitch = parseFloat(e.target.value);
    if (pitchVal) pitchVal.textContent = `${speechPitch}x`;
  });
}

// ================== MQTT WEBSOCKETS + REST POLLING ==================

function initMQTT() {
  if (typeof BROKER_WS_URL === "undefined" || !window.mqtt) return;

  try {
    const client = mqtt.connect(BROKER_WS_URL, {
      reconnectPeriod: 3000,
      connectTimeout: 4000
    });

    client.on("connect", () => {
      setConnectionStatus("online", "Connected via MQTT WebSockets");
      client.subscribe("signify/prediction");
      client.subscribe("signify/sensors");
    });

    client.on("message", (topic, payload) => {
      try {
        const data = JSON.parse(payload.toString());
        if (topic === "signify/prediction") {
          handleGesture(data.label, data.confidence || 95, data.sensors);
        } else if (topic === "signify/sensors") {
          updateSensorTelemetry([data.thumb, data.index, data.middle, data.ring, data.pinky]);
        }
      } catch (e) {
        console.warn("Payload parse error:", e);
      }
    });

    client.on("error", () => {
      setConnectionStatus("connecting", "MQTT reconnecting (REST active)");
    });

    client.on("close", () => {
      setConnectionStatus("offline", "Local Mode Active");
    });
  } catch (err) {
    console.log("MQTT Client Init Info:", err);
  }
}

// Automatic polling fallback to Flask backend REST API
function pollLatestPrediction() {
  fetch("/api/latest")
    .then((res) => res.json())
    .then((data) => {
      if (data && data.timestamp > lastProcessedTimestamp && data.label !== "Ready") {
        lastProcessedTimestamp = data.timestamp;
        handleGesture(data.label, data.confidence || 95, data.sensors);
      }
    })
    .catch(() => {});
}

setInterval(pollLatestPrediction, 700);

function setConnectionStatus(type, message) {
  if (!statusDot || !statusText) return;
  statusDot.className = `status-dot ${type}`;
  statusText.textContent = message;
}

// ================== SIMULATOR / TESTING ==================

function simulateSign(signLabel) {
  // Generate pseudo-random sensor values simulating finger flex
  const mockSensors = [
    Math.floor(2000 + Math.random() * 1500),
    Math.floor(2200 + Math.random() * 1400),
    Math.floor(1900 + Math.random() * 1600),
    Math.floor(2100 + Math.random() * 1500),
    Math.floor(2000 + Math.random() * 1300)
  ];
  handleGesture(signLabel, 98, mockSensors);
}

// ================== CUSTOMIZE PAGE LOGIC ==================

function renderCustomList() {
  const container = document.getElementById("customList");
  if (!container) return;

  container.innerHTML = "";
  const keys = Object.keys(customMap).sort();

  if (keys.length === 0) {
    container.innerHTML = `<p style="color: var(--text-dim); text-align: center; padding: 20px;">No custom mappings yet. Add one above!</p>`;
    return;
  }

  keys.forEach((key) => {
    const item = document.createElement("div");
    item.className = "custom-card-item";
    item.innerHTML = `
      <span class="custom-key">${key}</span>
      <span class="custom-value">${customMap[key]}</span>
      <div style="display: flex; gap: 6px;">
        <button class="btn btn-secondary btn-sm" onclick="speakText('${customMap[key]}')" title="Test Speech">🔊</button>
        <button class="btn btn-danger btn-sm" onclick="deleteCustomMapping('${key}')" title="Delete">✕</button>
      </div>
    `;
    container.appendChild(item);
  });
}

function saveCustomMapping(key, phrase) {
  if (!key || !phrase) return;
  customMap[key.toUpperCase()] = phrase;
  localStorage.setItem("signify_custom_map", JSON.stringify(customMap));
  renderCustomList();
}

function deleteCustomMapping(key) {
  delete customMap[key];
  localStorage.setItem("signify_custom_map", JSON.stringify(customMap));
  renderCustomList();
}

function loadQuickPresets(presetType) {
  const presets = {
    everyday: { "A": "Good Morning", "B": "How are you?", "C": "Thank you", "D": "Goodbye", "1": "Yes", "2": "No" },
    emergency: { "0": "Emergency", "1": "Call Doctor", "2": "I need help", "3": "Pain", "4": "Medicine" },
    numbers: { "0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five" }
  };

  if (presets[presetType]) {
    customMap = { ...customMap, ...presets[presetType] };
    localStorage.setItem("signify_custom_map", JSON.stringify(customMap));
    renderCustomList();
    speakText("Preset loaded");
  }
}

// Init Form Hook
const customForm = document.getElementById("customForm");
if (customForm) {
  customForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const key = document.getElementById("gestureKey").value.trim();
    const phrase = document.getElementById("customPhrase").value.trim();
    if (key && phrase) {
      saveCustomMapping(key, phrase);
      customForm.reset();
    }
  });
  renderCustomList();
}

// Run on load
document.addEventListener("DOMContentLoaded", () => {
  initMQTT();
});
