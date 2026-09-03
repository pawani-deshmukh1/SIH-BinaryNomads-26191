// advisory.js - Handles the advisory slide-in panel

const panel = document.getElementById('advisory-panel');

function getIconForType(type) {
  switch(type) {
    case 'char': return '⬡';
    case 'tribal': return '▲';
    case 'urban': return '●';
    case 'tea_garden': return '■';
    case 'riverbank': return '◆';
    default: return '●';
  }
}

async function openAdvisory(habId) {
  // 1. Slide in the panel immediately
  panel.classList.add('active');
  
  // 2. Set loading state
  document.getElementById('adv-title').textContent = 'Loading...';
  document.getElementById('adv-subtitle').textContent = 'Fetching relocation plan...';
  document.getElementById('adv-content').innerHTML = `
    <div style="text-align: center; padding: 40px 0;">
      <div class="spinner" style="margin: 0 auto 16px;"></div>
      Evaluating Sphere Standards & Logistics...
    </div>
  `;
  
  // 3. Fetch data from backend
  try {
    const res = await fetch(`http://127.0.0.1:8000/advisory/${habId}`);
    const data = await res.json();
    if (!res.ok && res.status !== 404) throw new Error('Failed to fetch');
    
    if (data.status === 'success') {
      renderAdvisoryContent(data.advisory);
    } else {
      renderError(data.message || 'No valid safe zones found.', data.rejected_sites || []);
    }
  } catch (err) {
    console.error(err);
    renderError('Failed to connect to backend server. Make sure it is running.');
  }
}

function closeAdvisory() {
  panel.classList.remove('active');
}

function renderAdvisoryContent(adv) {
  const hab = adv.habitation;
  const trigger = adv.trigger;
  const plan = adv.relocation_plan;
  const rejected = adv.rejected_sites_log || [];
  
  // Header
  document.getElementById('adv-title').innerHTML = `⚠ ${hab.name.toUpperCase()}`;
  document.getElementById('adv-subtitle').innerHTML = `${getIconForType(hab.type)} ${hab.type.replace('_', ' ')} community · ${hab.population} people`;
  
  // Content
  let html = `
    <div class="adv-box">
      <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:12px;">
        <span style="color:var(--text-dim)">Population</span>
        <strong>${hab.population}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:12px;">
        <span style="color:var(--text-dim)">Households</span>
        <strong>${hab.households}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:12px;">
        <span style="color:var(--text-dim)">Vulnerability (SC/ST)</span>
        <strong>${hab.vulnerability_sc_st_pct}%</strong>
      </div>
    </div>
    
    <div class="section-title">Risk Assessment</div>
    <div class="adv-box">
  `;
  
  if (trigger.live_weather && trigger.live_weather.forecast_72h_mm !== undefined) {
    html += `
      <div style="margin-bottom:12px; font-size:13px; color:var(--red); font-weight:600;">
        🔴 ${adv.urgency} — ${trigger.reason}
      </div>
      <div style="font-size:12px; color:var(--text-dim); margin-bottom:16px;">
        Live Weather Trigger: ${trigger.live_weather.forecast_72h_mm.toFixed(1)}mm forecast over 72h.
      </div>
    `;
  } else {
     html += `
      <div style="margin-bottom:12px; font-size:13px; color:var(--orange); font-weight:600;">
        🟠 ${adv.urgency} — Terrain Risk High
      </div>
    `;
  }
  html += `</div>`;
  
  if (plan.recommended_site) {
    const site = plan.recommended_site;
    const res = plan.resources_required;
    
    html += `
      <div class="section-title">Relocation Plan</div>
      <div class="adv-box safe-zone-card">
        <div class="safe-title">✅ ${site.name}</div>
        <div class="safe-metrics">
          <div class="metric">Assigned Pop<br><span>${site.capacity} pax</span></div>
          <div class="metric">Distance<br><span>${site.distance_km} km</span></div>
          <div class="metric">Access<br><span>${site.access_mode ? site.access_mode.toUpperCase() : 'ROAD'}</span></div>
          <div class="metric">Safety Score<br><span>${site.hazard_safety_score ? (site.hazard_safety_score * 100).toFixed(0) : 95}%</span></div>
        </div>
        
        <div class="resources-grid">
          <div class="res-item">
            <div class="res-val">${res.tents_50_person}</div>
            <div class="res-lbl">Tents Req.</div>
          </div>
          <div class="res-item">
            <div class="res-val">${res.food_rations_daily}</div>
            <div class="res-lbl">Rations/day</div>
          </div>
          <div class="res-item">
            <div class="res-val">${Math.round(res.total_water_litres/1000)}k</div>
            <div class="res-lbl">Water (L)</div>
          </div>
        </div>
      </div>
    `;
    
    if (plan.overflow_sites && plan.overflow_sites.length > 0) {
      html += `<div class="section-title" style="color: var(--orange); margin-top: 10px;">⚠️ Capacity Overflow Routing</div>`;
      plan.overflow_sites.forEach(os => {
        html += `
        <div class="adv-box safe-zone-card" style="border-left: 3px solid var(--orange);">
          <div class="safe-title">🔄 Routed to: ${os.name}</div>
          <div class="safe-metrics">
            <div class="metric">Overflow Pop<br><span style="color: var(--orange);">${os.assigned_population} pax</span></div>
            <div class="metric">Distance<br><span>${os.distance_km} km</span></div>
          </div>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 8px;">
            Primary safe zone reached maximum capacity. This group has been dynamically routed to the next available zone.
          </div>
        </div>
        `;
      });
    }
  }
  
  if (rejected.length > 0) {
    html += `<div class="section-title">Rejected Sites (Sphere Standard Fails)</div>`;
    rejected.forEach(r => {
      html += `
        <div class="rejected-site">
          <div class="rej-name">${r.name}</div>
      `;
      r.reasons.forEach(reason => {
        html += `<div class="rej-reason">${reason}</div>`;
      });
      html += `</div>`;
    });
  }
  
  html += `
    <button class="btn" style="width:100%; margin-top:24px; padding:12px; font-size:14px; background:var(--accent); color:white; border:none; border-radius:6px; cursor:pointer;" onclick="window.open('cop.html?hab_id=${hab.id}', '_blank')">
      🔍 Advanced Analysis (COP) & Simulation
    </button>
    <button class="btn btn-primary" style="width:100%; margin-top:12px; padding:12px; font-size:14px;" onclick="alert('PDF Generation simulated.')">
      📥 Download Relocation Order PDF
    </button>
  `;
  
  document.getElementById('adv-content').innerHTML = html;
}

function renderError(msg, rejected = []) {
  let html = `
    <div class="adv-box" style="border-color: var(--red); background: rgba(239, 68, 68, 0.05);">
      <div style="color: var(--red); font-weight:600; margin-bottom:8px;">❌ Advisory Generation Failed</div>
      <div style="font-size:13px;">${msg}</div>
    </div>
  `;
  
  if (rejected.length > 0) {
    html += `<div class="section-title">Rejected Sites</div>`;
    rejected.forEach(r => {
      html += `
        <div class="rejected-site">
          <div class="rej-name">${r.name}</div>
      `;
      r.reasons.forEach(reason => {
        html += `<div class="rej-reason">${reason}</div>`;
      });
      html += `</div>`;
    });
  }
  
  document.getElementById('adv-content').innerHTML = html;
}
