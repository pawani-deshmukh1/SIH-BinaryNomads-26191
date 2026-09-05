// ───────────────────────────────────────────────────────────
// DISHA Guided Tour Engine — tutorial.js
// Voice toggle: press the 🔇 button in the tour to mute TTS
// without muting system audio (so team leader can voiceover).
// ───────────────────────────────────────────────────────────

let _voiceEnabled = true;

function toggleVoice() {
  _voiceEnabled = !_voiceEnabled;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  const btn = document.getElementById('disha-voice-toggle');
  if (btn) btn.innerText = _voiceEnabled ? '🔊 Voice On' : '🔇 Voice Off';
}

// Injects the voice toggle button into the intro.js tooltip bar
function injectVoiceToggle() {
  if (document.getElementById('disha-voice-toggle')) return; // already injected
  const bar = document.querySelector('.introjs-tooltipbuttons');
  if (!bar) return;
  const btn = document.createElement('button');
  btn.id = 'disha-voice-toggle';
  btn.className = 'introjs-button';
  btn.style.cssText = 'margin-right: auto; background: rgba(255,255,255,0.1); color: #fff; border: 1px solid rgba(255,255,255,0.3); font-size: 12px;';
  btn.innerText = _voiceEnabled ? '🔊 Voice On' : '🔇 Voice Off';
  btn.onclick = (e) => { e.stopPropagation(); toggleVoice(); };
  bar.prepend(btn);
}

function speakText(htmlText) {
  if (!_voiceEnabled || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const text = htmlText
    .replace(/<br\s*[\/]?>/gi, '. ')
    .replace(/<[^>]*>?/gm, '')
    .replace(/\s+/g, ' ');
  const utt = new SpeechSynthesisUtterance(text);
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find(v => v.name.includes('Google') || v.name.includes('Microsoft Mark') || v.name.includes('Natural')) || voices.find(v => v.lang.startsWith('en'));
  if (voice) utt.voice = voice;
  utt.rate = 0.88;
  setTimeout(() => window.speechSynthesis.speak(utt), 150);
}

function startMainTutorial() {
  const intro = introJs();

  intro.setOptions({
    showProgress: true,
    showBullets: false,
    exitOnOverlayClick: false,
    disableInteraction: true,   // BLOCK clicks on the target element by default
    tooltipClass: 'custom-intro-tooltip',
    prevLabel: '← Back',
    nextLabel: 'Next →',
    doneLabel: 'Finish Tour',
    steps: [
      // ── Step 0: Welcome ─────────────────────────────────────
      {
        intro: `<b>Welcome to DISHA 🌊</b><br><br>
          DISHA is an AI-powered <b>Disaster Intelligence & Hazard Assessment</b> platform built for the Ministry of Home Affairs.<br><br>
          In the next 60 seconds, you will see how we turn raw terrain and weather data into life-saving evacuation decisions in real time.<br><br>
          Let's begin.`
      },

      // ── Step 1: The Map ──────────────────────────────────────
      {
        element: document.querySelector('#map'),
        intro: `<b>The Habitation Intelligence Map 🗺️</b><br><br>
          Every dot on this map is a real vulnerable settlement in Assam — <b>chars, tribal communities, riverbank villages</b>.<br><br>
          Our backend pre-processes each one using <b>NASA SRTM terrain data</b> (elevation, slope, Topographic Wetness Index) to assign a baseline flood and landslide susceptibility score.`,
        position: 'right'
      },

      // ── Step 2: Risk Status Grid ─────────────────────────────
      {
        element: document.querySelector('.status-grid'),
        intro: `<b>Automated Risk Tiers ⚠️</b><br><br>
          Our <b>XGBoost ML model</b> classifies every habitation into a risk tier:<br><br>
          <span style='color:#ef4444; font-weight:700'>● RED</span> — Critical. Risk score > 70%. Immediate evacuation required.<br>
          <span style='color:#f97316; font-weight:700'>● ORANGE</span> — High risk. 45–70%. Active monitoring.<br>
          <span style='color:#eab308; font-weight:700'>● YELLOW</span> — Moderate. 25–45%. Pre-positioned resources needed.<br><br>
          These scores update dynamically as live weather data comes in.`,
        position: 'left'
      },

      // ── Step 3: Weather Trigger ──────────────────────────────
      {
        element: document.querySelector('.weather-trigger') || document.querySelector('.sidebar'),
        intro: `<b>Layer B: Live Weather Trigger ☁️</b><br><br>
          We continuously pull <b>72-hour rainfall forecasts</b> from OpenWeather API and river discharge rates from <b>GloFAS</b>.<br><br>
          If rainfall exceeds <b>20mm/hr</b> or the 72-hour spike is significant, the system applies a <b>dynamic risk multiplier</b> (based on Zhu et al. 2023) — automatically escalating a YELLOW zone to RED without any human input.<br><br>
          This is our autonomous early-warning engine.`,
        position: 'left'
      },

      // ── Step 4: Habitation Sidebar ───────────────────────────
      {
        element: document.querySelector('#hab-list') || document.querySelector('.sidebar'),
        intro: `<b>Vulnerability-Weighted Prioritization 🛡️</b><br><br>
          Habitations are not just ranked by risk score. We layer in <b>social vulnerability</b> — specifically the percentage of SC/ST population — computed using the <b>Analytical Hierarchy Process (Saaty 1980)</b>.<br><br>
          This ensures the most <b>socially vulnerable communities</b> are always prioritized for evacuation first, even if their raw terrain score is similar to a neighbouring settlement.`,
        position: 'left'
      },

      // ── Step 5: Auto-open advisory AND describe it in same step ──
      // The panel is opened in onbeforechange BEFORE the tooltip renders.
      // We point the tooltip at the sidebar so it appears near the open panel.
      {
        element: document.querySelector('.sidebar'),
        intro: `<b>Live Relocation Advisory 📋</b><br><br>
          The system has automatically opened the Advisory Panel for the first Red Zone habitation.<br><br>
          This panel is the output of our <b>Carrying Capacity Engine</b> — it runs the <b>Hungarian Algorithm</b> — an O(n³) optimizer — to assign habitations to safe zones without exceeding maximum capacity.<br><br>
          It tells you:<br>
          ✅ The best Sphere-compliant safe zone<br>
          🚫 Why every other site was rejected<br>
          📦 Exact tents, water, and ration packs required`,
        position: 'left'
      },

      // ── Step 7: Finish & COP CTA ────────────────────────────
      {
        intro: `<b>🎓 That's the DISHA Intelligence Layer!</b><br><br>
          You've just seen AI move from raw satellite data → terrain risk → live weather escalation → mathematically optimized evacuation plan.<br><br>
          Click <b>"Advanced Analysis (COP) & Simulation"</b> inside the advisory panel to open the 3D Cesium flood simulation and deep-dive analysis for any habitation.`
      }
    ]
  });

  // ── Pre-fire openAdvisory on step 4 (while user reads Vulnerability step)
  // This gives the backend ~2-3 seconds to respond before step 5 renders.
  let _advisoryFired = false;
  intro.onbeforechange(function() {
    const stepIndex = intro._currentStep;

    // Fire on step 4 (Vulnerability) — panel loads in background during that step
    if (stepIndex === 4 && !_advisoryFired) {
      _advisoryFired = true;
      let targetHabId = null;
      if (typeof currentHabitations !== 'undefined' && currentHabitations.length > 0) {
        const redHab = currentHabitations.find(h => h.zone === 'RED') || currentHabitations[0];
        targetHabId = redHab.id;
      } else {
        const firstCard = document.querySelector('.hab-card');
        if (firstCard) firstCard.click();
      }
      if (targetHabId && typeof openAdvisory === 'function') {
        openAdvisory(targetHabId);
      }
    }
  });

  // ── Speak each step + inject voice toggle ───────────────────
  intro.onafterchange(function() {
    setTimeout(() => {
      injectVoiceToggle();
      const tooltip = document.querySelector('.introjs-tooltiptext');
      if (tooltip) speakText(tooltip.innerHTML);
    }, 300);
  });

  intro.onexit(function() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  });

  intro.start();
  // Speak step 0 immediately
  const step0 = intro._options.steps[0];
  if (step0) speakText(step0.intro);
}
