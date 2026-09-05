// safe_zones.js

let staticSafeZones = [];

async function init() {
  // Load static capabilities once
  const res = await fetch('http://127.0.0.1:8000/advisory/safe-zones');
  const data = await res.json();
  staticSafeZones = data.features;
  
  fetchLiveState();
  setInterval(fetchLiveState, 3000); // Poll every 3 seconds for demo
}

async function fetchLiveState() {
  try {
    const res = await fetch('http://127.0.0.1:8000/safe-zone-state/');
    const data = await res.json();
    renderGrid(data.safe_zones);
    document.getElementById('last-sync').innerText = new Date().toLocaleTimeString();
  } catch (e) {
    console.error("Live state error", e);
  }
}

function renderGrid(liveState) {
  const grid = document.getElementById('sz-grid');
  let html = '';
  
  staticSafeZones.forEach(sz => {
    const props = sz.properties;
    const id = props.id;
    const state = liveState[id] || { current_population: 0 };
    
    const capacity = props.capacity;
    const current = state.current_population;
    const pct = Math.min((current / capacity) * 100, 100);
    
    // Calculate remaining resources based on Sphere
    // (In reality this would subtract actual usage, but for demo we derive from population)
    const tentsTotal = Math.ceil(capacity / 50);
    const tentsUsed = Math.ceil(current / 50);
    const tentsLeft = tentsTotal - tentsUsed;
    
    const waterTotal = capacity * 15;
    const waterUsed = current * 15;
    const waterLeft = waterTotal - waterUsed;

    let barColor = 'var(--green)';
    if (pct > 75) barColor = 'var(--orange)';
    if (pct > 95) barColor = 'var(--red)';

    html += `
      <div class="sz-card">
        <div class="sz-header">✅ ${props.name}</div>
        <div style="font-size:12px; color:var(--text-dim);">${props.access_mode.toUpperCase()} Access | Safety: ${(props.hazard_safety_score*100).toFixed(0)}%</div>
        
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${pct}%; background: ${barColor};"></div>
        </div>
        <div style="font-size:11px; margin-top:4px; text-align:right; color:var(--text-dim);">
          Capacity: ${current} / ${capacity} pax
        </div>

        <div class="sz-metrics">
          <div class="metric-box">
            <div class="metric-val" style="color: ${tentsLeft < 2 ? 'var(--red)' : 'white'}">${tentsLeft}</div>
            <div class="metric-lbl">Tents Left</div>
          </div>
          <div class="metric-box">
            <div class="metric-val" style="color: ${waterLeft < 500 ? 'var(--red)' : 'white'}">${Math.round(waterLeft/1000)}k L</div>
            <div class="metric-lbl">Water Left</div>
          </div>
          <div class="metric-box">
            <div class="metric-val" style="color: ${pct > 95 ? 'var(--red)' : 'var(--green)'}">${(100 - pct).toFixed(1)}%</div>
            <div class="metric-lbl">Space</div>
          </div>
        </div>
      </div>
    `;
  });
  
  grid.innerHTML = html;
}

init();
