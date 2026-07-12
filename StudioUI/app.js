/**
 * StudioUI Controller Script
 * Interactive logic for the Music Studio Dashboard: Sequencer, Web Audio Synth, Mock Logic Pro, and Console Logs.
 */

// Global state
const state = {
  // Web Audio Context
  audioCtx: null,
  
  // Sequencer Settings
  isPlaying: false,
  bpm: 120,
  bars: 2,
  currentStep: 0,
  seqInterval: null,
  totalSteps: 32, // 2 bars * 16 steps = 32. Or 16/32/64 based on Bars select
  
  // Active Sequencer Grid Matrix
  // 6 instruments: Kick, Snare, Hat, Openhat, Clap, 808
  grid: {
    Kick: Array(32).fill(false),
    Snare: Array(32).fill(false),
    Hat: Array(32).fill(false),
    Openhat: Array(32).fill(false),
    Clap: Array(32).fill(false),
    808: Array(32).fill(false)
  },
  
  // Library items database
  library: {
    stems: [
      { name: "06 Open Interlude/vocals.wav", meta: "Vocals stem (24.1 MB)" },
      { name: "06 Open Interlude/drums.wav", meta: "Drums stem (18.6 MB)" },
      { name: "06 Open Interlude/bass.wav", meta: "Bass stem (12.4 MB)" },
      { name: "06 Open Interlude/other.wav", meta: "Other stem (31.0 MB)" },
      { name: "07 Skyline Drift/vocals.wav", meta: "Vocals stem (20.3 MB)" },
      { name: "07 Skyline Drift/drums.wav", meta: "Drums stem (16.2 MB)" }
    ],
    'one-shots': [
      { name: "One-Shots/06 Open Interlude/drums_001.wav", meta: "Kick drum hit" },
      { name: "One-Shots/06 Open Interlude/drums_002.wav", meta: "Snare hit" },
      { name: "One-Shots/06 Open Interlude/drums_003.wav", meta: "Closed hat hit" }
    ],
    vocals: [
      { name: "Vocals/06 Open Interlude/vocals_001.wav", meta: "Chop phrase 1 (4.2s)" },
      { name: "Vocals/06 Open Interlude/vocals_002.wav", meta: "Chop phrase 2 (5.1s)" }
    ],
    chops: [
      { name: "Chops/06 Open Interlude/bass/bass_001.wav", meta: "8s bass chop loop" },
      { name: "Chops/06 Open Interlude/other/other_001.wav", meta: "8s other chop loop" }
    ],
    loops: [
      { name: "Loops/beat_render_120bpm.wav", meta: "Sequencer loop render (4.0s)" }
    ],
    kits: [
      { name: "Kits/htdemucs_06_Open_Interlude/kick/", meta: "Classified kick hits (4 files)" },
      { name: "Kits/htdemucs_06_Open_Interlude/snare/", meta: "Classified snare hits (2 files)" }
    ],
    midi: [
      { name: "MIDI/06_Open_Interlude_bass.mid", meta: "Transcribed bass MIDI (120 BPM)" }
    ],
    resynth: [
      { name: "Resynth/revoiced_melody_guitar.wav", meta: "FluidSynth revoiced wav (6.4s)" }
    ]
  },
  
  // Logic Pro connection state
  logic: {
    connected: true,
    project: "06 Open Interlude.logicx",
    tempo: 120,
    key: "A minor",
    position: "1 1 1 1"
  }
};

// UI Elements mapping
const dom = {
  alert: document.getElementById('desktop-commander-alert'),
  console: document.getElementById('output-console'),
  consoleStatusDot: document.getElementById('output-status'),
  consoleStatusText: document.getElementById('output-status-text'),
  btnStopTask: document.getElementById('btn-stop-task'),
  libraryList: document.getElementById('library-list'),
  seqRows: document.getElementById('sequencer-rows-container'),
  seqBpm: document.getElementById('seq-bpm'),
  seqBars: document.getElementById('seq-bars'),
  seqName: document.getElementById('seq-name'),
  seqPlayBtn: document.getElementById('btn-seq-play'),
  playhead: document.getElementById('playhead'),
  logicProj: document.getElementById('logic-project-name'),
  logicTempo: document.getElementById('logic-tempo'),
  logicKey: document.getElementById('logic-key'),
  logicPos: document.getElementById('logic-position'),
  logicPlayBtn: document.getElementById('btn-logic-play'),
  statusLogic: document.getElementById('logic-connection-badge'),
  downloadUrl: document.getElementById('input-download-url'),
  stemFolder: document.getElementById('select-stem-folder'),
  sourceTrack: document.getElementById('select-source-track'),
  tempoInput: document.getElementById('input-tempo')
};

// Initialize App
window.addEventListener('DOMContentLoaded', () => {
  setupSequencerGrid();
  reloadLibrary();
  refreshLogicUI();
  
  // Initial sequencer playhead sizing and alignment
  updatePlayheadPosition();
  
  // Sync core input tempo with sequencer tempo
  dom.tempoInput.addEventListener('change', (e) => {
    dom.seqBpm.value = e.target.value;
    state.bpm = parseInt(e.target.value);
  });
});

// Toast Connection simulation
function retryConnection() {
  logConsole("Connecting to Desktop Commander...", "info");
  setTimeout(() => {
    dom.alert.style.transform = 'scaleY(0)';
    setTimeout(() => dom.alert.style.display = 'none', 300);
    logConsole("[ok] Connected to Desktop Commander. System Events automation active.", "success");
  }, 1000);
}

function dismissAlert(id) {
  const el = document.getElementById(id);
  el.style.transform = 'scaleY(0)';
  setTimeout(() => el.style.display = 'none', 300);
}

// Console Logging
function logConsole(message, type = "normal") {
  const timestamp = new Date().toLocaleTimeString();
  let prefix = "";
  if (type === "success") prefix = "[ok] ";
  if (type === "error") prefix = "[error] ";
  if (type === "info") prefix = "[info] ";
  
  const text = `\n[${timestamp}] ${prefix}${message}`;
  dom.console.innerText += text;
  dom.console.scrollTop = dom.console.scrollHeight;
}

function clearOutput() {
  dom.console.innerText = "Ready. Pick a track and run a step — output streams here.";
}

let activeTask = null;
function runAction(actionName, scope) {
  // Check parameters
  let target = "";
  if (scope === 'download') target = dom.downloadUrl.value.trim();
  if (scope === 'source') target = dom.sourceTrack.value;
  if (scope === 'stems') target = dom.stemFolder.value;
  
  if ((scope === 'download' || scope === 'source' || scope === 'stems') && !target) {
    logConsole(`Action "${actionName}" requires an input path or option.`, "error");
    return;
  }
  
  // Show running indicator
  dom.consoleStatusDot.className = "status-indicator-dot running";
  dom.consoleStatusText.innerText = "running";
  dom.btnStopTask.classList.remove('disabled');
  
  logConsole(`Starting task: ${actionName}...`, "info");
  
  // Simulate task processing
  activeTask = setTimeout(() => {
    if (actionName === 'Download') {
      logConsole(`Downloading audio from URL: ${target}...`, "info");
      logConsole(`Using cookies.txt authentication bypass...`, "info");
      logConsole(`File downloaded: "06 Open Interlude.m4a"`, "success");
      dom.sourceTrack.innerHTML += `<option value="song_new">06 Open Interlude.m4a</option>`;
      dom.sourceTrack.value = "song_new";
    } else if (actionName === 'Separate stems') {
      const mode = document.getElementById('select-stem-mode').value;
      logConsole(`Running Demucs Separation [${mode}] on selected track...`, "info");
      logConsole(`Writing output stems to: Stems/htdemucs/06 Open Interlude/`, "info");
      logConsole(`Separation Complete. 4 files created: drums.wav, bass.wav, other.wav, vocals.wav`, "success");
      dom.stemFolder.innerHTML += `<option value="stems_new">Stems/htdemucs/06 Open Interlude</option>`;
      dom.stemFolder.value = "stems_new";
    } else if (actionName === 'Deconstruct') {
      logConsole(`Initiating full deconstruct pipeline...`, "info");
      logConsole(`1. Analyzing track key/BPM...`, "info");
      logConsole(`   Tempo: 120.0 BPM, Key: Am`, "success");
      logConsole(`2. Separating stems via Demucs (4-stem)...`, "info");
      logConsole(`3. Slicing drums into one-shots...`, "info");
      logConsole(`4. Sorting kit by spectral centroid...`, "info");
      logConsole(`5. Slicing stems to fixed chops...`, "info");
      logConsole(`Deconstruct pipeline completed successfully.`, "success");
    } else if (actionName === 'Build Logic project from stems') {
      logConsole(`Creating empty project in Logic Pro...`, "info");
      logConsole(`Setting project BPM: ${state.logic.tempo}...`, "info");
      logConsole(`Setting key signature: ${state.logic.key}...`, "info");
      logConsole(`Importing stems to tracks...`, "info");
      logConsole(`Logic project created with 4 tracks successfully.`, "success");
      
      // Update logic status panel
      state.logic.project = "Project_Stems_Build.logicx";
      state.logic.tempo = dom.seqBpm.value;
      refreshLogicUI();
    } else {
      logConsole(`Task completed: ${actionName}`, "success");
    }
    
    taskFinished();
  }, 2500);
}

function stopTask() {
  if (activeTask) {
    clearTimeout(activeTask);
    logConsole("Task cancelled by user.", "error");
    taskFinished();
  }
}

function taskFinished() {
  activeTask = null;
  dom.consoleStatusDot.className = "status-indicator-dot idle";
  dom.consoleStatusText.innerText = "idle";
  dom.btnStopTask.classList.add('disabled');
}

// Library Management
let activeTab = 'stems';
function switchLibraryTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.innerText.toLowerCase() === tabName) btn.classList.add('active');
  });
  activeTab = tabName;
  renderLibraryItems();
}

function renderLibraryItems() {
  dom.libraryList.innerHTML = "";
  const items = state.library[activeTab] || [];
  
  if (items.length === 0) {
    dom.libraryList.innerHTML = `<div class="library-item" style="justify-content: center; color: var(--text-dim);">No items in this category.</div>`;
    return;
  }
  
  items.forEach(item => {
    const el = document.createElement('div');
    el.className = "library-item";
    el.innerHTML = `
      <span class="library-item-name">${item.name}</span>
      <span class="library-item-meta">${item.meta}</span>
    `;
    
    // Play on click simulation
    el.addEventListener('click', () => {
      logConsole(`Playing preview: afplay "${item.name}"`, "info");
      playMockBeep();
    });
    
    // Reveal on double click
    el.addEventListener('dblclick', () => {
      logConsole(`Revealing in Finder: ${item.name}`, "info");
    });
    
    dom.libraryList.appendChild(el);
  });
}

function reloadLibrary() {
  logConsole("Reloading library indexes...", "info");
  renderLibraryItems();
}

function openFinderFolder(name) {
  logConsole(`Opening folder in Finder: /Users/home/Developer/music/${name}`, "info");
}

// Logic Pro Status
function refreshLogicStatus() {
  logConsole("Querying Logic Pro connection status...", "info");
  state.logic.connected = !state.logic.connected;
  if (state.logic.connected) {
    state.logic.project = "06 Open Interlude.logicx";
    state.logic.tempo = 120;
    state.logic.key = "A minor";
    state.logic.position = "1 1 1 1";
    dom.statusLogic.className = "badge badge-online";
    dom.statusLogic.innerText = "connected";
    logConsole("[ok] Connection established with Logic Pro.", "success");
  } else {
    state.logic.project = "—";
    state.logic.tempo = "—";
    state.logic.key = "—";
    state.logic.position = "—";
    dom.statusLogic.className = "badge badge-offline";
    dom.statusLogic.innerText = "unknown";
    logConsole("Logic Pro connection dropped.", "error");
  }
  refreshLogicUI();
}

function refreshLogicUI() {
  dom.logicProj.innerText = state.logic.project;
  dom.logicTempo.innerText = state.logic.tempo;
  dom.logicKey.innerText = state.logic.key;
  dom.logicPos.innerText = state.logic.position;
  document.getElementById('btn-logic-bpm-lbl').innerText = dom.seqBpm.value;
}

function runLogicCommand(cmd) {
  logConsole(`Logic Command: ${cmd}`, "info");
  if (cmd === 'play') {
    dom.logicPlayBtn.innerText = dom.logicPlayBtn.innerText === "▶" ? "⏸" : "▶";
  }
}

// Sequencer Grid Setup
const INSTRUMENTS = ["Kick", "Snare", "Hat", "Openhat", "Clap", "808"];
function setupSequencerGrid() {
  dom.seqRows.innerHTML = "";
  
  // Total steps based on bars setting (2 bars = 32 steps)
  state.totalSteps = state.bars * 16;
  
  INSTRUMENTS.forEach(inst => {
    const row = document.createElement('div');
    row.className = "sequencer-row";
    row.innerHTML = `
      <span class="seq-label-col">${inst}</span>
      <select class="seq-inst-select">
        <option>synth only</option>
        <option>sample hit</option>
      </select>
      <div class="seq-steps" id="seq-steps-${inst}">
        <!-- steps populated here -->
      </div>
    `;
    
    dom.seqRows.appendChild(row);
    
    // Add 16 or 32 step divs
    const stepsContainer = document.getElementById(`seq-steps-${inst}`);
    for (let step = 0; step < state.totalSteps; step++) {
      const stepDiv = document.createElement('div');
      stepDiv.className = `seq-step ${state.grid[inst][step] ? 'active' : ''}`;
      stepDiv.dataset.inst = inst;
      stepDiv.dataset.step = step;
      
      stepDiv.addEventListener('click', () => {
        state.grid[inst][step] = !state.grid[inst][step];
        stepDiv.classList.toggle('active');
        if (state.grid[inst][step]) {
          triggerSynthSound(inst);
        }
      });
      
      stepsContainer.appendChild(stepDiv);
    }
  });
}

function updateSequencerBars() {
  state.bars = parseInt(dom.seqBars.value);
  setupSequencerGrid();
  updatePlayheadPosition();
}

function updateSequencerTempo() {
  state.bpm = parseInt(dom.seqBpm.value);
  dom.tempoInput.value = state.bpm;
  refreshLogicUI();
}

function toggleSequencer() {
  if (state.isPlaying) {
    stopSequencer();
  } else {
    startSequencer();
  }
}

function startSequencer() {
  if (!state.audioCtx) {
    state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  
  state.isPlaying = true;
  dom.seqPlayBtn.innerText = "Stop";
  dom.seqPlayBtn.className = "btn btn-danger btn-seq-action";
  
  dom.playhead.style.opacity = 1;
  state.currentStep = 0;
  
  // Interval duration per step (16th notes: 60 / BPM / 4)
  const stepTimeMs = (60 / state.bpm / 4) * 1000;
  
  state.seqInterval = setInterval(() => {
    // Play active steps in current column
    INSTRUMENTS.forEach(inst => {
      if (state.grid[inst][state.currentStep]) {
        triggerSynthSound(inst);
      }
    });
    
    // Highlight playhead position
    updatePlayheadPosition();
    
    // Advance step
    state.currentStep = (state.currentStep + 1) % state.totalSteps;
  }, stepTimeMs);
}

function stopSequencer() {
  state.isPlaying = false;
  clearInterval(state.seqInterval);
  dom.seqPlayBtn.innerText = "Play";
  dom.seqPlayBtn.className = "btn btn-primary btn-seq-action";
  dom.playhead.style.opacity = 0;
}

function updatePlayheadPosition() {
  // Sizing mapping based on column dimensions
  const labelWidth = 175; // Label + dropdown size + margins
  const stepsContainer = document.querySelector('.seq-steps');
  if (!stepsContainer) return;
  
  const stepWidth = stepsContainer.children[0]?.getBoundingClientRect().width || 0;
  const gap = 6; // gap in stylesheet
  
  const stepOffset = state.currentStep * (stepWidth + gap);
  dom.playhead.style.left = `${labelWidth + stepOffset + 2}px`;
}

function clearSequencer() {
  INSTRUMENTS.forEach(inst => {
    state.grid[inst].fill(false);
  });
  setupSequencerGrid();
}

function randomizeSequencer() {
  INSTRUMENTS.forEach(inst => {
    for (let step = 0; step < state.totalSteps; step++) {
      state.grid[inst][step] = Math.random() < 0.15; // 15% active chance
    }
  });
  setupSequencerGrid();
}

// Web Audio API Synthesizer Sounds
function triggerSynthSound(inst) {
  if (!state.audioCtx) return;
  
  const osc = state.audioCtx.createOscillator();
  const gain = state.audioCtx.createGain();
  
  osc.connect(gain);
  gain.connect(state.audioCtx.destination);
  
  const now = state.audioCtx.currentTime;
  
  if (inst === 'Kick') {
    osc.frequency.setValueAtTime(150, now);
    osc.frequency.exponentialRampToValueAtTime(0.01, now + 0.3);
    gain.gain.setValueAtTime(1.0, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
    osc.start(now);
    osc.stop(now + 0.3);
  } else if (inst === 'Snare') {
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(180, now);
    gain.gain.setValueAtTime(0.6, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
    osc.start(now);
    osc.stop(now + 0.15);
  } else if (inst === 'Hat') {
    osc.type = 'sine';
    osc.frequency.setValueAtTime(8000, now);
    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.05);
    osc.start(now);
    osc.stop(now + 0.05);
  } else if (inst === 'Openhat') {
    osc.type = 'sine';
    osc.frequency.setValueAtTime(7000, now);
    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
    osc.start(now);
    osc.stop(now + 0.2);
  } else if (inst === 'Clap') {
    osc.type = 'square';
    osc.frequency.setValueAtTime(1000, now);
    gain.gain.setValueAtTime(0.4, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
    osc.start(now);
    osc.stop(now + 0.1);
  } else if (inst === '808') {
    osc.frequency.setValueAtTime(55, now); // A1 note
    osc.frequency.exponentialRampToValueAtTime(30, now + 0.8);
    gain.gain.setValueAtTime(0.8, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.8);
    osc.start(now);
    osc.stop(now + 0.8);
  }
}

function playMockBeep() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.frequency.setValueAtTime(440, ctx.currentTime);
  gain.gain.setValueAtTime(0.2, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
  osc.start();
  osc.stop(ctx.currentTime + 0.3);
}

// Sequencer Exporting
function exportMidi() {
  const name = dom.seqName.value || "beat";
  logConsole(`Exporting MIDI: MIDI/${name}.mid successfully created.`, "success");
  
  // Add to library
  state.library.midi.push({
    name: `MIDI/${name}.mid`,
    meta: `Sequencer export (${state.bpm} BPM)`
  });
  if (activeTab === 'midi') renderLibraryItems();
}

function renderWavLoop() {
  const name = dom.seqName.value || "beat";
  logConsole(`Rendering WAV loop: Loops/${name}_render_${state.bpm}bpm.wav...`, "info");
  
  setTimeout(() => {
    logConsole(`Render completed. Added to Loops library.`, "success");
    state.library.loops.push({
      name: `Loops/${name}_render_${state.bpm}bpm.wav`,
      meta: `Sequencer loop render (${state.bars} Bars)`
    });
    if (activeTab === 'loops') renderLibraryItems();
  }, 1000);
}
