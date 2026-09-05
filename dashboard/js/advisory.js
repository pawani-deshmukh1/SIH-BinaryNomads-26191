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

function renderShapChart(title, explanation) {
  if (!explanation || !explanation.top_factors || explanation.top_factors.length === 0) return '';
  let html = `<div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">`;
  html += `<div style="font-size: 11px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px;">Explainable AI (SHAP): ${title}</div>`;
  
  // get max abs value for scaling
  let maxVal = Math.max(...explanation.top_factors.map(f => {
      let val = Array.isArray(f) ? f[1] : (f.shap_impact !== undefined ? f.shap_impact : f.value);
      return Math.abs(val);
  }));
  if (maxVal === 0 || isNaN(maxVal)) maxVal = 1;

  explanation.top_factors.slice(0, 5).forEach(factor => {
      const isArr = Array.isArray(factor);
      const nameRaw = isArr ? factor[0] : factor.feature;
      const val = isArr ? factor[1] : (factor.shap_impact !== undefined ? factor.shap_impact : factor.value);
      const name = nameRaw ? nameRaw.replace(/_/g, ' ') : 'Unknown';
      const pct = (Math.abs(val) / maxVal) * 100;
      const color = val > 0 ? 'var(--red)' : 'var(--success)';
      const sign = val > 0 ? '+' : '';
      html += `
          <div style="display: flex; align-items: center; margin-bottom: 4px; font-size: 11px;">
              <div style="width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text);" title="${name}">${name}</div>
              <div style="flex: 1; margin: 0 8px; background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                  <div style="width: ${pct}%; height: 100%; background: ${color}; border-radius: 3px;"></div>
              </div>
              <div style="width: 35px; text-align: right; color: ${color}; font-family: monospace;">${sign}${val.toFixed(2)}</div>
          </div>
      `;
  });
  html += `</div>`;
  return html;
}

let currentRouteLayers = [];

function clearRouteLayers() {
  if (typeof map !== 'undefined' && currentRouteLayers) {
    currentRouteLayers.forEach(layer => map.removeLayer(layer));
    currentRouteLayers = [];
  }
}

async function openAdvisory(habId) {
  // 1. Slide in the panel immediately
  panel.classList.add('active');
  clearRouteLayers();
  
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
  clearRouteLayers();
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
      <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:12px;">
        <span style="color:var(--text-dim)">Vulnerability (SC/ST)</span>
        <strong>${hab.vulnerability_sc_st_pct}%</strong>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:12px;">
        <span style="color:var(--text-dim)">Women</span>
        <strong>${hab.women_percent || 49}%</strong>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:12px;">
        <span style="color:var(--text-dim)">Children</span>
        <strong>${hab.children_percent || 29}%</strong>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:12px;">
        <span style="color:var(--text-dim)">Elderly</span>
        <strong>${hab.elderly_percent || 8}%</strong>
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
  
  if (adv.risk_explanation) {
    if (adv.risk_explanation.landslide && adv.risk_explanation.landslide.top_factors && adv.risk_explanation.landslide.top_factors.length > 0) {
        html += renderShapChart('Landslide Drivers', adv.risk_explanation.landslide);
    }
    if (adv.risk_explanation.flood && adv.risk_explanation.flood.top_factors && adv.risk_explanation.flood.top_factors.length > 0) {
        html += renderShapChart('Flood Drivers', adv.risk_explanation.flood);
    }
  }

  html += `</div>`;
  
  if (plan.recommended_site) {
    const site = plan.recommended_site;
    const res = plan.resources_required;
    
    // FETCH ROUTE AND DRAW IT ON LEAFLET MAP
    if (typeof currentHabitations !== 'undefined') {
      const habData = currentHabitations.find(h => h.id === hab.id);
      if (habData && site.lat && site.lng) {
        fetch(`http://127.0.0.1:8000/route/?origin_lat=${habData.lat}&origin_lon=${habData.lng}&dest_lat=${site.lat}&dest_lon=${site.lng}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({}) // no flood geojson for 2D map
        }).then(r => r.json()).then(routeData => {
            if (routeData && routeData.features) {
                routeData.features.forEach(feat => {
                    let color = '#22c55e'; // GREEN
                    let dashArray = null;
                    if (feat.properties.segment_type === 'kacha_way') {
                        color = '#8B4513'; // BROWN
                        dashArray = '10, 10';
                    } else if (feat.properties.segment_type === 'blocked' || feat.properties.route_status === 'ERROR' || feat.properties.route_status === 'ISOLATED') {
                        color = '#ef4444'; // RED
                        dashArray = '5, 5'; // Make error lines dashed so they are distinguishable
                    }
                    
                    if (feat.geometry && feat.geometry.coordinates) {
                        const latlngs = feat.geometry.coordinates.map(c => [c[1], c[0]]);
                        const polyline = L.polyline(latlngs, {
                            color: color,
                            weight: 4,
                            opacity: 0.9,
                            dashArray: dashArray
                        }).addTo(map);
                        
                        currentRouteLayers.push(polyline);
                    }
                });
                
                // Add Destination Marker
                const destIcon = L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="background-color: #3b82f6; width: 16px; height: 16px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 6px rgba(0,0,0,0.8);"></div>`,
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                });
                const destMarker = L.marker([site.lat, site.lng], {icon: destIcon})
                  .bindTooltip("Relief Camp: " + site.name, {permanent: true, direction: 'right', className: 'safe-zone-tooltip'})
                  .addTo(map);
                currentRouteLayers.push(destMarker);

                // Zoom map to fit both start and end points
                const bounds = L.latLngBounds([[habData.lat, habData.lng], [site.lat, site.lng]]);
                // 300px right padding to avoid hiding behind the advisory panel
                map.flyToBounds(bounds, { paddingBottomRight: [400, 50], paddingTopLeft: [50, 50], duration: 1.5 });
            }
        }).catch(err => console.error("Route fetch failed:", err));
      }
    }
    
    html += `
      <div class="section-title">Relocation Plan</div>
      <div class="adv-box safe-zone-card" style="border-left: 3px solid #3b82f6;">
        <div class="safe-title" style="color: #3b82f6;">🏕️ ${site.name}</div>
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
    <button class="btn btn-primary" style="width:100%; margin-top:12px; padding:12px; font-size:14px;" onclick="window.open('pdf_template.html?hab_id=${hab.id}', '_blank')">
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
