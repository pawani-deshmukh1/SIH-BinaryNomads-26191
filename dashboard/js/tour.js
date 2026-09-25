/**
 * DISHA Tour Engine v2 — tour.js
 * 
 * Design principles:
 * - NO blocking overlay. The map and UI remain fully interactive during the tour.
 * - A fixed bottom-right narrator card shows step content.
 * - Target elements get a glowing highlight ring, not a dark dim.
 * - TTS (Web Speech API) narrates each step automatically.
 * - Works on ALL pages: index, cop, guwahati_3d, strategic, field_ops, layer3_review, simulation.
 * - Zero external dependencies. Pure vanilla JS + CSS injected at runtime.
 */

(function () {
  // ─── STATE ───────────────────────────────────────────────────────────────
  let _steps = [];
  let _current = 0;
  let _voiceEnabled = true;
  let _highlightEl = null;
  let _highlightRing = null;
  let _onStepChange = null; // optional callback: called with stepIndex before card renders

  // ─── INJECT STYLES (once) ────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('disha-tour-styles')) return;
    const style = document.createElement('style');
    style.id = 'disha-tour-styles';
    style.textContent = `
      /* ── Narrator Card ── */
      #disha-tour-card {
        position: fixed;
        bottom: 24px;
        right: 24px;
        width: 380px;
        max-width: calc(100vw - 48px);
        background: linear-gradient(135deg, rgba(15,23,42,0.97) 0%, rgba(7,15,30,0.97) 100%);
        border: 1px solid rgba(0, 213, 255, 0.35);
        border-radius: 14px;
        box-shadow: 0 8px 40px rgba(0,213,255,0.15), 0 2px 8px rgba(0,0,0,0.6);
        z-index: 99999;
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: #e2e8f0;
        overflow: hidden;
        animation: tourCardIn 0.3s ease;
        backdrop-filter: blur(12px);
      }
      @keyframes tourCardIn {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      /* ── Card Header ── */
      #disha-tour-header {
        background: linear-gradient(90deg, rgba(0,213,255,0.12) 0%, rgba(0,213,255,0.04) 100%);
        border-bottom: 1px solid rgba(0,213,255,0.2);
        padding: 10px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        cursor: grab;
      }
      #disha-tour-header:active {
        cursor: grabbing;
      }
      #disha-tour-title {
        font-size: 11px;
        font-weight: 700;
        color: #00d5ff;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        flex: 1;
      }
      #disha-tour-progress-text {
        font-size: 10px;
        color: #64748b;
        white-space: nowrap;
      }
      #disha-tour-close {
        background: none;
        border: none;
        color: #64748b;
        cursor: pointer;
        font-size: 16px;
        line-height: 1;
        padding: 0 0 0 8px;
        transition: color 0.2s;
      }
      #disha-tour-close:hover { color: #ef4444; }

      /* ── Progress Bar ── */
      #disha-tour-progress-bar-wrap {
        height: 2px;
        background: rgba(255,255,255,0.06);
      }
      #disha-tour-progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #00d5ff, #7c3aed);
        transition: width 0.35s ease;
      }

      /* ── Content ── */
      #disha-tour-body {
        padding: 16px 18px 12px;
        font-size: 13.5px;
        line-height: 1.65;
        color: #cbd5e1;
        max-height: 260px;
        overflow-y: auto;
      }
      #disha-tour-body b {
        color: #f1f5f9;
        font-weight: 700;
      }
      #disha-tour-body .tour-badge {
        display: inline-block;
        padding: 1px 7px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        margin: 0 2px;
      }
      #disha-tour-body .badge-red  { background: rgba(239,68,68,0.2);  color: #ef4444; }
      #disha-tour-body .badge-green{ background: rgba(34,197,94,0.2);  color: #22c55e; }
      #disha-tour-body .badge-blue { background: rgba(59,130,246,0.2); color: #60a5fa; }
      #disha-tour-body .badge-amber{ background: rgba(245,158,11,0.2); color: #f59e0b; }

      /* ── Footer Controls ── */
      #disha-tour-footer {
        padding: 10px 18px 14px;
        display: flex;
        align-items: center;
        gap: 8px;
        border-top: 1px solid rgba(255,255,255,0.06);
      }
      .disha-tour-btn {
        padding: 7px 16px;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        font-family: inherit;
        font-size: 12px;
        font-weight: 700;
        transition: all 0.2s;
        white-space: nowrap;
      }
      #disha-tour-prev {
        background: rgba(255,255,255,0.06);
        color: #94a3b8;
      }
      #disha-tour-prev:hover { background: rgba(255,255,255,0.12); color: #e2e8f0; }
      #disha-tour-next {
        background: linear-gradient(135deg, #00d5ff, #0891b2);
        color: #0f172a;
        flex: 1;
        text-align: center;
      }
      #disha-tour-next:hover { opacity: 0.88; transform: translateY(-1px); }
      #disha-tour-voice {
        background: rgba(255,255,255,0.06);
        color: #94a3b8;
        min-width: 36px;
        text-align: center;
        padding: 7px 10px;
        font-size: 14px;
      }
      #disha-tour-voice:hover { background: rgba(255,255,255,0.12); }

      /* ── Highlight Ring (injected around target element) ── */
      .disha-tour-highlight-ring {
        position: fixed;
        pointer-events: none;
        z-index: 99990;
        border-radius: 8px;
        box-shadow:
          0 0 0 3px rgba(0, 213, 255, 0.9),
          0 0 0 6px rgba(0, 213, 255, 0.25),
          0 0 24px rgba(0, 213, 255, 0.4);
        transition: all 0.3s ease;
        animation: tourRingPulse 1.8s ease-in-out infinite;
      }
      @keyframes tourRingPulse {
        0%, 100% { box-shadow: 0 0 0 3px rgba(0,213,255,0.9), 0 0 0 6px rgba(0,213,255,0.25), 0 0 24px rgba(0,213,255,0.4); }
        50%       { box-shadow: 0 0 0 3px rgba(0,213,255,0.6), 0 0 0 10px rgba(0,213,255,0.12), 0 0 40px rgba(0,213,255,0.25); }
      }
    `;
    document.head.appendChild(style);
  }

  // ─── TTS ─────────────────────────────────────────────────────────────────
  function speak(html) {
    if (!_voiceEnabled || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const text = html
      .replace(/<br\s*\/?>/gi, '. ')
      .replace(/<[^>]*>/gm, '')
      .replace(/\s+/g, ' ')
      .trim();
    const utt = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find(v =>
      v.name.includes('Google UK English Male') ||
      v.name.includes('Microsoft Mark') ||
      v.name.includes('Google')
    ) || voices.find(v => v.lang.startsWith('en'));
    if (voice) utt.voice = voice;
    utt.rate = 0.9;
    utt.pitch = 1.0;
    setTimeout(() => window.speechSynthesis.speak(utt), 200);
  }

  // ─── HIGHLIGHT ───────────────────────────────────────────────────────────
  function clearHighlight() {
    if (_highlightRing) { _highlightRing.remove(); _highlightRing = null; }
    if (_highlightEl) { _highlightEl = null; }
  }

  function highlightElement(selector) {
    clearHighlight();
    if (!selector) return;

    const el = typeof selector === 'string'
      ? document.querySelector(selector)
      : selector;
    if (!el) return;

    _highlightEl = el;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    const ring = document.createElement('div');
    ring.className = 'disha-tour-highlight-ring';
    document.body.appendChild(ring);
    _highlightRing = ring;

    function positionRing() {
      if (!_highlightRing || !_highlightEl) return;
      const r = _highlightEl.getBoundingClientRect();
      const pad = 4;
      ring.style.left   = (r.left - pad) + 'px';
      ring.style.top    = (r.top  - pad) + 'px';
      ring.style.width  = (r.width  + pad * 2) + 'px';
      ring.style.height = (r.height + pad * 2) + 'px';
    }
    positionRing();
    // Re-position on scroll/resize
    window._tourRingInterval = setInterval(positionRing, 200);
  }

  // ─── RENDER STEP ─────────────────────────────────────────────────────────
  function renderStep() {
    const step = _steps[_current];
    if (!step) return;

    // Run pre-step callback (e.g., switch tabs, toggle layers)
    if (_onStepChange) _onStepChange(_current, step);
    if (typeof step.before === 'function') step.before();

    // Highlight target
    clearHighlight();
    if (window._tourRingInterval) clearInterval(window._tourRingInterval);
    if (step.highlight) {
      setTimeout(() => highlightElement(step.highlight), 350);
    }

    // Update card content
    const total = _steps.length;
    document.getElementById('disha-tour-title').textContent = step.title || 'DISHA Tour';
    document.getElementById('disha-tour-progress-text').textContent = `Step ${_current + 1} of ${total}`;
    document.getElementById('disha-tour-progress-bar').style.width = ((_current + 1) / total * 100) + '%';
    document.getElementById('disha-tour-body').innerHTML = step.content;

    // Buttons
    const prevBtn = document.getElementById('disha-tour-prev');
    const nextBtn = document.getElementById('disha-tour-next');
    prevBtn.style.display = _current === 0 ? 'none' : '';
    nextBtn.textContent = _current === total - 1 ? '✓ Finish' : 'Next →';

    // Speak
    setTimeout(() => speak(step.content), 400);
  }

  // ─── BUILD CARD ──────────────────────────────────────────────────────────
  function buildCard() {
    if (document.getElementById('disha-tour-card')) return;

    const card = document.createElement('div');
    card.id = 'disha-tour-card';
    card.innerHTML = `
      <div id="disha-tour-header">
        <span id="disha-tour-title">DISHA Tour</span>
        <span id="disha-tour-progress-text">Step 1 of 1</span>
        <button id="disha-tour-close" title="Exit tour">✕</button>
      </div>
      <div id="disha-tour-progress-bar-wrap">
        <div id="disha-tour-progress-bar" style="width:0%"></div>
      </div>
      <div id="disha-tour-body"></div>
      <div id="disha-tour-footer">
        <button class="disha-tour-btn" id="disha-tour-prev">← Back</button>
        <button class="disha-tour-btn" id="disha-tour-next">Next →</button>
        <button class="disha-tour-btn" id="disha-tour-voice" title="Toggle voice">🔊</button>
      </div>
    `;
    document.body.appendChild(card);

    document.getElementById('disha-tour-next').onclick = () => {
      if (_current < _steps.length - 1) { _current++; renderStep(); }
      else endTour();
    };
    document.getElementById('disha-tour-prev').onclick = () => {
      if (_current > 0) { _current--; renderStep(); }
    };
    document.getElementById('disha-tour-close').onclick = endTour;
    document.getElementById('disha-tour-voice').onclick = () => {
      _voiceEnabled = !_voiceEnabled;
      if (!_voiceEnabled && window.speechSynthesis) window.speechSynthesis.cancel();
      document.getElementById('disha-tour-voice').textContent = _voiceEnabled ? '🔊' : '🔇';
    };

    // ── DRAGGABLE LOGIC ──
    const header = document.getElementById('disha-tour-header');
    let isDragging = false;
    let startX, startY, initialX, initialY;

    header.onmousedown = (e) => {
      // Don't drag if clicking the close button
      if (e.target.id === 'disha-tour-close') return;
      
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = card.getBoundingClientRect();
      initialX = rect.left;
      initialY = rect.top;
      
      // Switch from bottom/right to left/top positioning for dragging
      card.style.bottom = 'auto';
      card.style.right = 'auto';
      card.style.left = initialX + 'px';
      card.style.top = initialY + 'px';
      
      e.preventDefault(); // Prevent text selection
    };

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      
      // Constrain to window bounds
      const newLeft = Math.max(0, Math.min(window.innerWidth - card.offsetWidth, initialX + dx));
      const newTop = Math.max(0, Math.min(window.innerHeight - card.offsetHeight, initialY + dy));
      
      card.style.left = newLeft + 'px';
      card.style.top = newTop + 'px';
    });

    document.addEventListener('mouseup', () => {
      isDragging = false;
    });
  }

  // ─── START / END ─────────────────────────────────────────────────────────
  function startTour(steps, onStepChange) {
    injectStyles();
    _steps = steps;
    _current = 0;
    _onStepChange = onStepChange || null;
    buildCard();
    renderStep();
  }

  function endTour() {
    clearHighlight();
    if (window._tourRingInterval) clearInterval(window._tourRingInterval);
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    const card = document.getElementById('disha-tour-card');
    if (card) card.remove();
  }

  // ─── PUBLIC API ──────────────────────────────────────────────────────────
  window.DishaTour = { start: startTour, end: endTour };

  // ══════════════════════════════════════════════════════════════════════════
  //  PAGE-SPECIFIC TOUR DEFINITIONS
  // ══════════════════════════════════════════════════════════════════════════

  // ── INDEX.HTML — Layer 1 EWS ───────────────────────────────────────────
  window.startMainTutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — Layer 1 Overview',
        content: `<b>Welcome to DISHA 🌊</b><br><br>
          DISHA is an <b>AI-powered Disaster Intelligence & Hazard Assessment</b> platform built for the Ministry of Home Affairs and NDRF.<br><br>
          In the next 90 seconds you'll see how raw terrain data becomes a life-saving evacuation decision — in real time.<br><br>
          <i>The UI remains fully interactive. Click anything while the tour runs.</i>`
      },
      {
        title: 'Habitation Intelligence Map',
        highlight: '#map',
        content: `<b>The Multi-Hazard Risk Map 🗺️</b><br><br>
          Every dot is a <b>real vulnerable settlement</b> in Assam — chars (river islands), tribal hill villages, tea garden communities, and riverbank settlements.<br><br>
          Each one was pre-scored by our backend using <b>ISRO Bhuvan DEM</b> — extracting elevation, slope, Topographic Wetness Index (TWI), and Terrain Ruggedness Index (TRI).<br><br>
          <span class="tour-badge badge-red">● RED</span> Immediate evacuation &nbsp;
          <span class="tour-badge badge-amber">● ORANGE</span> On watch &nbsp;
          <span class="tour-badge badge-green">● YELLOW</span> Monitor`
      },
      {
        title: 'Automated Risk Classification',
        highlight: '.status-grid',
        content: `<b>XGBoost Risk Tiers ⚠️</b><br><br>
          Our <b>XGBoost ML model</b> fuses 12 terrain and weather features into a composite risk score.<br><br>
          Score > 70% → <span class="tour-badge badge-red">RED</span> — evacuate now<br>
          Score 45–70% → <span class="tour-badge badge-amber">ORANGE</span> — activate pre-positioning<br>
          Score 25–45% → <span class="tour-badge badge-green">YELLOW</span> — monitor with 6-hour intervals<br><br>
          These thresholds update <b>dynamically</b> as live rainfall data arrives from Open-Meteo and CWC.`
      },
      {
        title: 'Live Weather & Wind Layer',
        highlight: '#layer-b-btn',
        content: `<b>Regional Rainfall Trigger ☁️</b><br><br>
          The wind vector overlay (bottom of the map) shows real-time wind field from Open-Meteo — critical for the CBRN plume model in the Guwahati module.<br><br>
          Click <b>Regional Rainfall Trigger</b> to see district-level rainfall telemetry and identify which areas are approaching the <b>20mm/hr critical threshold</b> for flash flood escalation.`
      },
      {
        title: 'Relocation Advisory Engine',
        highlight: '#hab-list',
        content: `<b>Click Any Habitation → Instant Advisory 📋</b><br><br>
          Click any habitation card in the sidebar. The <b>Carrying Capacity Engine</b> runs immediately — it uses the <b>Hungarian Algorithm (O(n³))</b> to optimally assign the population to the best passing safe zone.<br><br>
          The advisory shows:<br>
          ✅ Best Sphere-compliant safe zone (3.5m² per person)<br>
          🚫 All rejected sites with exact rejection reasons<br>
          🛣️ Color-coded evacuation route (green = paved, brown = kutcha, red = blocked)`
      },
      {
        title: 'Navigate to Guwahati UFRI',
        highlight: '.btn[onclick*="strategic"]',
        content: `<b>Next: Layer 2 Strategic + Guwahati Deep-Dive 🏙️</b><br><br>
          Click <b>Layer 2 Strategy</b> in the top nav to see the long-term vulnerability watchlist — GLOF lake expansion, Brahmaputra bank erosion, urban subsidence trends.<br><br>
          From there, click <b>"Guwahati Deep-Dive"</b> to open the <b>Urban Flood Risk Intelligence (UFRI)</b> — our 10-layer forensic city analysis with live AI tactical briefing.<br><br>
          <i>That is where the real depth of DISHA lives.</i>`
      }
    ]);
  };

  // ── STRATEGIC.HTML — Layer 2 ───────────────────────────────────────────
  window.startStrategicTutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — Layer 2 Strategic Monitor',
        content: `<b>Long-Term Vulnerability Intelligence 📡</b><br><br>
          Layer 2 is not about today's flood — it's about <b>what will become dangerous in the next 2–4 years</b>.<br><br>
          This watchlist is generated from multi-year Sentinel-2 satellite imagery processed through Google Earth Engine on Kaggle's free GPU pipeline.`
      },
      {
        title: 'Hazard Category Filters',
        highlight: '.tab-filters',
        content: `<b>4 Strategic Hazard Categories</b><br><br>
          <b>GLOF</b> — Glacial Lake Outburst Flood risk from expanding Himalayan lakes (Sikkim, Arunachal)<br><br>
          <b>Erosion</b> — Brahmaputra bank erosion rate (m/year) threatening villages within 500m<br><br>
          <b>Urban Flood</b> — Guwahati bowl effect, drainage overload choke points<br><br>
          <b>Subsidence</b> — Groundwater depletion lowering land elevation (InSAR-derived)`
      },
      {
        title: 'Trend Analysis Charts',
        highlight: '#trend-chart-container',
        content: `<b>Satellite-Derived Trend Charts 📈</b><br><br>
          Each watchlist item shows a multi-year trend chart — NDVI loss, water body expansion, or erosion extent derived from <b>Sentinel-2 Band 8 / NDWI analysis</b>.<br><br>
          The runway horizon filter lets commanders see: <i>"Which locations become critical in under 2 years?"</i> — enabling proactive, not reactive, relocation planning.`
      },
      {
        title: 'Guwahati Deep-Dive',
        highlight: '#guwahati-deepdive-btn',
        content: `<b>Urban Flood Risk Intelligence (UFRI) 🏙️</b><br><br>
          Click <b>"Guwahati Deep-Dive"</b> to launch the most advanced module in DISHA — a 10-layer 3D city forensic analysis combining elevation basins, drainage choke points, subsidence zones, CBRN industrial hazards, and live AI tactical routing.<br><br>
          This is DISHA's direct response to NDRF's operational needs in urban flood scenarios.`
      }
    ]);
  };

  // ── GUWAHATI_3D.HTML — UFRI ────────────────────────────────────────────
  window.startGuwahatiTutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — Guwahati UFRI',
        content: `<b>Urban Flood Risk Intelligence 🏙️</b><br><br>
          This module provides a <b>10-layer forensic analysis</b> of Guwahati's urban flood system — the same city NDRF Battalion 1 is stationed in at Azara.<br><br>
          The red star marker on the map <b>is their actual base</b>. Every layer you activate tells the battalion commander something they cannot see from field observation alone.`
      },
      {
        title: 'Layer 1: Brahmaputra Flood Baseline',
        highlight: '#layer-btn-brahmaputra',
        content: `<b>DEM Flood Basin: The Bowl Effect 🌊</b><br><br>
          Dark red zones = terrain below <b>49.68m</b> — the CWC Brahmaputra Danger Level gauge threshold.<br><br>
          When the river crosses this level, <b>these exact pixels flood first</b>. The data is from ISRO Bhuvan DEM (30m resolution) processed in GeoPandas.<br><br>
          The live CWC gauge auto-syncs the river stage slider — so as the river rises, you see which areas are next.`
      },
      {
        title: 'Drainage Choke Points',
        highlight: '#layer-btn-choke',
        content: `<b>Computed Drainage Choke Points 🚧</b><br><br>
          These are not drawn by hand — they are <b>mathematically derived</b> using GeoPandas spatial intersection:<br><br>
          Any drain segment within <b>400m of a slope >15°</b> is flagged as a choke point — because hillside runoff hits flat urban drains faster than capacity allows.<br><br>
          <span class="tour-badge badge-red">CRITICAL</span> = drain likely blocked within 2h of heavy rain<br>
          <span class="tour-badge badge-amber">HIGH</span> = overflow probable at 30mm/hr+`
      },
      {
        title: 'CBRN Chemical Hazard',
        highlight: '#cbrn-toggle',
        content: `<b>Chemical Hazard Overlay ☣️</b><br><br>
          Toggle CBRN to activate 3 Guwahati industrial facilities: <b>IOCL Noonmati Refinery, Kamrup Industrial Gases, Shiva Chemicals</b>.<br><br>
          The plume uses <b>Pasquill-Gifford Gaussian dispersion</b> and rotates in real time as Open-Meteo updates wind direction.<br><br>
          Heavy rain <b>shrinks</b> the plume (wet scavenging). The NDRF staging point auto-routes to an upwind position, bypassing the hazard zone.`
      },
      {
        title: 'Scenario Simulator + AI Brief',
        highlight: '#scenario-panel',
        content: `<b>Live Scenario + Groq AI Tactical Brief 🤖</b><br><br>
          Adjust Rain (mm/hr), Brahmaputra Stage (m), and Umiam Dam fill (%) using the sliders.<br><br>
          Click <b>"Generate AI Brief"</b> — the Groq Llama 3 RAG agent synthesizes all 10 spatial layers into a plain-language tactical brief for the NDRF commander, with specific basin-level action items.<br><br>
          The <b>Approve / Override</b> buttons are the Human-in-the-Loop (HITL) control — no AI recommendation executes without human confirmation.`
      },
      {
        title: 'NDRF Tactical Routing',
        content: `<b>AI-Generated Dispatch Routes 🚑</b><br><br>
          After the AI brief is approved, DISHA computes OSRM road routes from <b>Azara Base → each at-risk basin</b>, with turn-by-turn geometry drawn on the map.<br><br>
          For CBRN scenarios, the route automatically detours around the plume's critical zone.<br><br>
          This replaces the 30–45 minute manual map consultation that NDRF currently performs before deploying teams.`
      }
    ]);
  };

  // ── SIMULATION.HTML — 3D Cesium ────────────────────────────────────────
  window.startSimulationTutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — 3D Flood Simulation',
        content: `<b>Cesium Ion 3D Tactical Simulation 🌐</b><br><br>
          This is a physics-based flood growth model running on real Indian terrain — ISRO Bhuvan DEM via Cesium Ion.<br><br>
          The model steps through <b>T+0h → T+6h → T+18h → T+36h</b>, computing how far flood water spreads based on terrain topology and GloFAS river discharge volumes.`
      },
      {
        title: 'Time Controls',
        highlight: '#sim-controls',
        content: `<b>Simulation Playback Controls ⏱️</b><br><br>
          Use the stage buttons to jump directly to any time horizon, or play in sequence.<br><br>
          Speed modes: <b>1x / 5x / 30x</b> — 30x compresses the entire 36-hour flood event into about 30 seconds for presentation.<br><br>
          The blue flood polygons grow using <b>Manning's Equation</b> applied to live GloFAS discharge data.`
      },
      {
        title: 'Habitation Breach Alert',
        content: `<b>Automatic Breach Detection 🚨</b><br><br>
          The system uses <b>Turf.js point-in-polygon</b> to continuously check whether the expanding flood polygon has reached any habitation.<br><br>
          The moment it does — a full-screen <b>"HABITATION SUBMERGED"</b> alert fires, the advisory API is called automatically, and DISHA outputs the relocation action to take — without any manual trigger.`
      },
      {
        title: 'Live Weather Context',
        highlight: '#weather-panel',
        content: `<b>Synchronized Live Weather 🌧️</b><br><br>
          The right panel shows live Open-Meteo data — current rainfall mm/hr, 72h forecast, and the river level hydrograph (Chart.js).<br><br>
          The simulation risk multiplier automatically updates based on real rainfall intensity — so a real-world heavy rain event would push the simulation toward the T+36h peak faster than calm conditions.`
      }
    ]);
  };

  // ── FIELD_OPS.HTML ─────────────────────────────────────────────────────
  window.startFieldOpsTutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — Field Operations Command',
        content: `<b>Field Operations Hub 📡</b><br><br>
          This is the real-time operations room for NDRF commanders — the ground layer of DISHA that connects the intelligence platform to the field teams carrying it out.<br><br>
          It receives live GPS telemetry from the <b>DISHA+ mobile app</b> running on field officers' phones.`
      },
      {
        title: 'Team Status Panel',
        highlight: '.panel-left',
        content: `<b>NDRF Team Roster 🛡️</b><br><br>
          Each card shows a real-time team status:<br>
          <span class="tour-badge badge-green">AVAILABLE</span> — at base, ready to deploy<br>
          <span class="tour-badge badge-amber">DISPATCHED</span> — en route to habitation<br>
          <span class="tour-badge badge-red">ON SCENE</span> — actively conducting rescue<br><br>
          The dispatch dropdown lets commanders assign any available team to any habitation in one click.`
      },
      {
        title: 'Live Team Tracking Map',
        highlight: '#map',
        content: `<b>GPS Team Location Map 🗺️</b><br><br>
          Team markers update every 5 seconds from the DISHA+ mobile app via <code>/dispatch/{id}/location</code>.<br><br>
          The <b>HITL Commander Override</b> button sends a location verification request to the team's phone — the field officer must confirm their position before the commander sees it as verified.<br><br>
          This prevents GPS spoofing and ensures accountability.`
      },
      {
        title: 'Comms Dead Zone Resilience',
        highlight: '.btn[onclick*="simulateDeadZone"]',
        content: `<b>Dead Zone SMS Failsafe 📵</b><br><br>
          Click <b>"Sim Dead Zone Alert"</b> to see what happens when a team enters a communications blackout zone.<br><br>
          DISHA automatically:<br>
          1. Caches the team's last known route to local storage<br>
          2. Fires an SMS alert via the backend <code>/comms/offline-alert/</code> endpoint<br>
          3. Displays a warning banner to the commander<br><br>
          This works even without internet — DISHA+ is a Progressive Web App with offline support.`
      },
      {
        title: 'Live Field Reports Feed',
        highlight: '.panel-right',
        content: `<b>Real-Time Field Reports 📋</b><br><br>
          The right panel shows incoming field reports from DISHA+ — rescue counts, field notes, team IDs, and timestamps.<br><br>
          This creates a live incident log that feeds directly into the AI's situational awareness — the Groq RAG agent uses recent field reports to adjust its tactical recommendations in the Guwahati module.`
      }
    ]);
  };

  // ── LAYER3_REVIEW.HTML — ONNX ─────────────────────────────────────────
  window.startLayer3Tutorial = function () {
    DishaTour.start([
      {
        title: 'DISHA — Layer 3: ONNX Calibration',
        content: `<b>Post-Disaster Model Self-Correction 🔁</b><br><br>
          Layer 3 closes the loop. After a real disaster, this module compares <b>what the AI predicted</b> (Layer 1 risk scores) with <b>what satellite imagery confirmed actually happened</b>.<br><br>
          The result is a <b>Calibration Gap metric</b> — and with one click, the model weights update for the next monsoon season.`
      },
      {
        title: 'Upload Post-Disaster Imagery',
        highlight: '#post-image',
        content: `<b>Sentinel-2 Post-Event Upload 🛰️</b><br><br>
          Upload any post-disaster optical satellite image (Sentinel-2, ResourceSat-2, or drone orthomosaic).<br><br>
          The ONNX pipeline — a <b>U-Net with ResNet-50 backbone</b> (<code>disha_flood_v4.onnx</code>) — runs semantic segmentation to extract:<br>
          • Flood inundation extent (blue pixels)<br>
          • Landslide scarring (red pixels)<br>
          • Structural damage zones (orange pixels)`
      },
      {
        title: 'Calibration Gap Analysis',
        highlight: '#gap-val',
        content: `<b>Predictive vs Actual Gap 📊</b><br><br>
          The Calibration Gap metric shows the delta between Layer 1's predicted flood boundary and the ONNX-detected actual boundary.<br><br>
          A gap > 15% triggers an automatic retraining recommendation. Click <b>"Commit Calibration Loop"</b> to update the weights — the next Layer 1 prediction for similar terrain will be that much more accurate.<br><br>
          <i>This is what makes DISHA a learning system, not just a static model.</i>`
      }
    ]);
  };

})();
