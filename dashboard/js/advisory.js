// advisory.js - Handles the advisory slide-in panel

const panel = document.getElementById('advisory-panel');

function getIconForType(type) {
  switch(type) {
    case 'char': return '⬡';
    case 'tribal': return '▲';
    case 'urban': return '●';
    case 'tea_garden': return '■';
    case 'riverbank': return '◆';
    default: return '●'; // generic
  }
}

// CAP Alert Modal Simulation
window.showCapAlert = function(habName) {
  const modal = document.createElement('div');
  modal.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.8);z-index:10000;display:flex;align-items:center;justify-content:center;";
  modal.innerHTML = `
    <div style="background:var(--bg-card); border: 1px solid var(--border); border-radius: 8px; width: 400px; max-width: 90%; padding: 20px;">
      <h3 style="color:var(--danger); margin-top:0;">📢 CAP Alert Broadcast Simulation</h3>
      <div style="font-size:13px; line-height:1.5; color:var(--text); font-family:monospace; background:rgba(0,0,0,0.2); padding:10px; border-radius:4px; margin-bottom:15px;">
        [EN] ⚠️ FLOOD ALERT — ${habName}. Mandatory evacuation ordered. Proceed to Safe Zone immediately. Helpline: 1078.<br><br>
        [HI] ⚠️ बाढ़ चेतावनी — ${habName}। अनिवार्य निकासी आदेश। सुरक्षित क्षेत्र में जाएं।<br><br>
        [AS] ⚠️ বানপানী সতৰ্কতা — ${habName}। বাধ্যতামূলক স্থানান্তৰ।
      </div>
      <button class="btn btn-outline" style="width:100%;" onclick="this.parentElement.parentElement.remove()">Acknowledge & Close</button>
    </div>
  `;
  document.body.appendChild(modal);
}

function renderShapChart(title, explanation) {
  if (!explanation || !explanation.top_factors || explanation.top_factors.length === 0) return '';
  let html = `<div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">`;
  html += `<div style="font-size: 11px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px;">Explainable AI (SHAP): ${title}</div>`;
  
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

// Draw formal camp route (BLUE) from pre-computed GeoJSON
function drawFormalRoute(routeData, habData, site, routingDecision) {
  if (!routeData || !routeData.features) return;

  routeData.features.forEach(feat => {
    let color = '#3b82f6'; // BLUE — formal relief camp
    let dashArray = null;
    if (feat.properties && feat.properties.segment_type === 'kacha_way') {
      color = '#60a5fa'; // lighter blue dashed for kacha road
      dashArray = '10, 10';
    } else if (feat.properties && (feat.properties.segment_type === 'blocked' ||
        ['ERROR', 'ISOLATED', 'BLOCKED'].includes(feat.properties.route_status))) {
      color = '#ef4444';
      dashArray = '5, 5';
    }
    if (feat.geometry && feat.geometry.coordinates) {
      const latlngs = feat.geometry.coordinates.map(c => [c[1], c[0]]);
      const polyline = L.polyline(latlngs, { color, weight: 4, opacity: 0.9, dashArray }).addTo(map);
      currentRouteLayers.push(polyline);
    }
  });

  // Destination marker
  let iconHtml = `<div style="background-color: #3b82f6; width: 16px; height: 16px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 6px rgba(0,0,0,0.8);"></div>`;
  if (routingDecision === 'BOAT_OR_HELI_ONLY') {
    iconHtml = `<div style="background-color: #8b5cf6; width: 24px; height: 24px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 6px rgba(0,0,0,0.8); display:flex; align-items:center; justify-content:center; font-size:14px;">&#x1F681;</div>`;
  }
  const destIcon = L.divIcon({ className: 'custom-div-icon', html: iconHtml, iconSize: [24, 24], iconAnchor: [12, 12] });
  const destMarker = L.marker([site.lat, site.lng], { icon: destIcon })
    .bindTooltip('Relief Camp: ' + site.name, { permanent: true, direction: 'right', className: 'safe-zone-tooltip' })
    .addTo(map);
  currentRouteLayers.push(destMarker);

  // Zoom to fit
  const bounds = L.latLngBounds([[habData.lat, habData.lng], [site.lat, site.lng]]);
  map.flyToBounds(bounds, { paddingBottomRight: [400, 50], paddingTopLeft: [50, 50], duration: 1.5 });
}

// Draw host community route (GREEN) from pre-computed GeoJSON
function drawHostRoute(h, habData, splitPop) {
  if (typeof map === 'undefined' || !h.lat || !h.lng) return;

  // Destination marker
  const hostIcon = L.divIcon({
    className: 'custom-div-icon',
    html: '<div style="background:#22c55e;width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.8);"></div>',
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });
  const hostMarker = L.marker([h.lat, h.lng], { icon: hostIcon })
    .bindTooltip('Option B: ' + h.name + ' (' + splitPop + ' pax)', { permanent: true, direction: 'right', className: 'safe-zone-tooltip' })
    .addTo(map);
  currentRouteLayers.push(hostMarker);

  // Draw road geometry from pre-computed backend data
  const routeData = h.route_geojson;
  if (routeData && routeData.features) {
    routeData.features.forEach(function(feat) {
      if (!feat.geometry || !feat.geometry.coordinates) return;
      const latlngs = feat.geometry.coordinates.map(function(c) { return [c[1], c[0]]; });
      const isKacha = feat.properties && feat.properties.segment_type === 'kacha_way';
      const isBlocked = feat.properties && ['ISOLATED', 'ERROR', 'BLOCKED'].indexOf(feat.properties.route_status) >= 0;
      const line = L.polyline(latlngs, {
        color: isBlocked ? '#ef4444' : '#22c55e',
        weight: isKacha ? 3 : 4,
        opacity: 0.85,
        dashArray: isKacha ? '8, 8' : null
      }).addTo(map);
      currentRouteLayers.push(line);
    });
  } else if (habData) {
    // Straight dashed fallback if route not cached yet (first-ever request)
    const line = L.polyline([[habData.lat, habData.lng], [h.lat, h.lng]], {
      color: '#22c55e', weight: 3, opacity: 0.6, dashArray: '12, 8'
    }).addTo(map);
    currentRouteLayers.push(line);
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
      Evaluating Sphere Standards &amp; Logistics...
    </div>
  `;
  
  // 3. Fetch data from backend
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const region = urlParams.get('region') || 'assam';
    const res = await fetch(`${window.API_BASE}/advisory/${habId}?region=${region}`);
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
  document.getElementById('adv-title').innerHTML = `&#x26A0; ${hab.name.toUpperCase()}`;
  document.getElementById('adv-subtitle').innerHTML = `${getIconForType(hab.type)} ${hab.type.replace('_', ' ')} community &middot; ${hab.population} people`;
  
  // Update the right-side Layer B Telemetry panel if we have live weather data
  if (trigger && trigger.live_weather && typeof updateWeatherUI === 'function') {
      updateWeatherUI(
          Number(trigger.live_weather.current_rain_mm_hr || trigger.live_weather.current_rain_mmhr || 0),
          Number(trigger.live_weather.forecast_72h_mm || trigger.live_weather.rain_forecast_72h_mm || 0),
          Number(trigger.live_weather.risk_multiplier || 1.0)
      );
  }
  
  // Content
  let html = `
    <button class="btn btn-danger" style="width: 100%; margin-bottom: 12px; font-weight: bold; font-size: 13px;" onclick="showCapAlert('${hab.name}')">
      📢 Broadcast CAP Alert
    </button>
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
  
  if (adv.estimated_lead_time_hrs) {
    html += `
      <div style="margin-bottom:12px; font-size:13px; color:var(--orange); font-weight:600;">
        ⏱ Estimated Lead Time: ~${adv.estimated_lead_time_hrs} hours
      </div>
    `;
  }
  
  if (trigger.live_weather && trigger.live_weather.forecast_72h_mm !== undefined) {
    html += `
      <div style="margin-bottom:12px; font-size:13px; color:var(--red); font-weight:600;">
        &#x1F534; ${adv.urgency} &mdash; ${trigger.reason}
      </div>
      <div style="font-size:12px; color:var(--text-dim); margin-bottom:16px;">
        Live Weather Trigger: ${trigger.live_weather.forecast_72h_mm.toFixed(1)}mm forecast over 72h.
      </div>
    `;
  } else {
     html += `
      <div style="margin-bottom:12px; font-size:13px; color:var(--orange); font-weight:600;">
        &#x1F7E0; ${adv.urgency} &mdash; Terrain Risk High
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

    // Draw BLUE formal camp route from pre-computed backend data
    if (typeof map !== 'undefined' && typeof currentHabitations !== 'undefined') {
      const habData = currentHabitations.find(h => h.id === hab.id);
      if (habData && site.lat && site.lng && plan.verified_route) {
        drawFormalRoute(plan.verified_route, habData, site, plan.routing_decision);
      }
    }
    
    html += `
      <div class="section-title">Relocation Plan</div>
      <div class="adv-box safe-zone-card" style="border-left: 3px solid #3b82f6;">
    `;
    
    // Comms Shadow Warning (Predictive Autopilot)
    if (adv.estimated_lead_time_hrs && adv.estimated_lead_time_hrs < 48) {
      html += `
        <div style="margin-bottom: 15px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-left: 3px solid var(--danger); border-radius: 4px; font-size: 11px;">
          <div style="color: var(--danger); margin-bottom: 4px; font-weight: bold; text-transform: uppercase;">📡 COMMS SHADOW WARNING</div>
          <div style="color: var(--text-bright); margin-bottom: 8px;">Cell coverage will fail at T-12h.</div>
          <div style="color: var(--text-dim);">
            &rarr; Recommend deploying COW/Radio Relay at:
            <strong style="color: var(--accent);">[${site.name} — Elev ${Math.floor(Math.random()*100 + 100)}m]</strong><br>
            Before dispatching teams to this zone.
          </div>
        </div>
      `;
    }

    // Routing Status block
    html += `<div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid var(--border);">
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px;">Routing Status</div>`;
        
    if (plan.routing_rejected_zones && plan.routing_rejected_zones.length > 0) {
        plan.routing_rejected_zones.forEach(rz => {
            html += `<div style="display:flex; align-items:center; margin-bottom:6px; font-size:12px; color:var(--text-dim);">
                <span style="color:var(--red); margin-right:6px;">&#x274C;</span> 
                <div>
                  <div style="text-decoration: line-through;">${rz.id}</div>
                  <div style="font-size:10px;">${rz.reason}</div>
                </div>
            </div>`;
        });
    }
    
    if (plan.routing_decision === 'REACHABLE') {
        html += `<div style="display:flex; align-items:center; margin-bottom:6px; font-size:12px;">
            <span style="color:var(--success); margin-right:6px;">&#x2705;</span> 
            <div>
              <strong>${site.name}</strong> &mdash; REACHABLE
              <div style="font-size:10px; color:var(--text-dim);">Route Status: ${plan.route_status || 'CLEAR'} via ${(plan.evacuation_mode || 'ROAD').toUpperCase()}</div>
            </div>
        </div>`;
    } else if (plan.routing_decision === 'BOAT_OR_HELI_ONLY') {
        html += `<div style="display:flex; align-items:center; margin-bottom:6px; font-size:12px; color:var(--orange);">
            <span style="margin-right:6px;">&#x1F681;</span> 
            <div>
              <strong>${site.name}</strong> &mdash; AERIAL/BOAT EVACUATION REQUIRED
              <div style="font-size:10px;">All overland routes to candidate safe zones are blocked.</div>
            </div>
        </div>`;
    }
    
    html += `</div>
        <div class="safe-title" style="color: #3b82f6;">&#x1F3D5; ${site.name}</div>
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
      </div>
    `;
    
    if (plan.overflow_sites && plan.overflow_sites.length > 0) {
      html += `<div class="section-title" style="color: var(--orange); margin-top: 10px;">&#x26A0;&#xFE0F; Capacity Overflow Routing</div>`;
      plan.overflow_sites.forEach(os => {
        html += `
        <div class="adv-box safe-zone-card" style="border-left: 3px solid var(--orange);">
          <div class="safe-title">&#x1F504; Routed to: ${os.name}</div>
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

  // ── Host Community Options (Option B: Nearby Safe Habitation) ──────────────
  const hostOptions = adv.host_community_options || [];
  if (hostOptions.length > 0) {
    const splitMsg = hostOptions.length > 1
      ? '<br>Population split across <strong>' + hostOptions.length + ' communities</strong> for better resource management.'
      : '';

    html += '<div class="section-title" style="color: #22c55e; margin-top: 10px;">Option B &mdash; Nearby Safe Habitation (Host Community)</div>';
    html += '<div style="font-size:11px; color:var(--text-dim); margin-bottom:10px; padding:8px; background:rgba(34,197,94,0.08); border-radius:6px; border-left:3px solid #22c55e;">'
      + 'These habitations are <strong>closer than the formal camp</strong>, verified safe by XGBoost models, and have spare capacity.'
      + splitMsg
      + ' Final decision rests with the field officer.</div>';

    const habData = typeof currentHabitations !== 'undefined'
      ? currentHabitations.find(function(x) { return x.id === hab.id; })
      : null;

    hostOptions.slice(0, 2).forEach(function(h) {
      const zoneColor = h.zone_class === 'GREEN' ? '#22c55e' : '#eab308';
      const capacityBadge = h.can_host_all
        ? '<span style="background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid #22c55e;padding:2px 6px;border-radius:4px;font-size:10px;">Full Capacity</span>'
        : '<span style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid #f59e0b;padding:2px 6px;border-radius:4px;font-size:10px;">&#x26A1; Partial Shelter</span>';

      const splitPop = h.assigned_population || 0;
      const splitPct = Math.round(splitPop / (hab.population || 1) * 100);

      html += '<div class="adv-box safe-zone-card" style="border-left: 3px solid #22c55e; margin-bottom:10px;">'
        + '<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">'
        + '<div class="safe-title" style="color:#22c55e;">&#x1F3D8; ' + h.name + '</div>'
        + capacityBadge
        + '</div>'
        + '<div style="font-size:11px; color:var(--text-dim); margin-bottom:8px;">' + (h.type_label || h.type) + ' &middot; ' + h.district + '</div>'
        + '<div class="safe-metrics">'
        + '<div class="metric">Receives<br><span style="color:#22c55e;font-weight:700;">' + splitPop + ' pax</span><br><span style="font-size:9px;color:var(--text-dim);">' + splitPct + '% of displaced</span></div>'
        + '<div class="metric">Distance<br><span style="color:#22c55e;">' + h.distance_km + ' km</span></div>'
        + '<div class="metric">Saves<br><span style="color:#22c55e;">&darr;' + h.distance_saving_km + ' km</span></div>'
        + '<div class="metric">Zone<br><span style="color:' + zoneColor + ';">&bull; ' + h.zone_class + '</span></div>'
        + '</div>'
        + '<div style="font-size:11px; color:var(--text-dim); margin-top:8px; padding-top:8px; border-top:1px solid var(--border);">'
        + (h.note || '')
        + (!h.road_accessible ? '<br>&#x26A0;&#xFE0F; No direct road &mdash; nearest road ' + h.nearest_road_km + ' km away.' : '')
        + '</div>'
        + '</div>';

      // Draw GREEN road route from pre-computed backend data
      drawHostRoute(h, habData, splitPop);
    });
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
      &#x1F50D; Advanced Analysis (COP)
    </button>
    <button class="btn" style="width:100%; margin-top:12px; padding:12px; font-size:14px; background:#8b5cf6; color:white; border:none; border-radius:6px; cursor:pointer;" onclick="window.open('simulation.html?hab_id=${hab.id}', '_blank')">
      🌊 Launch 3D Tactical Simulation
    </button>
    <button class="btn btn-primary" style="width:100%; margin-top:12px; padding:12px; font-size:14px;" onclick="window.open('pdf_template.html?hab_id=${hab.id}', '_blank')">
      &#x1F4E5; Download Relocation Order PDF
    </button>
  `;
  
  document.getElementById('adv-content').innerHTML = html;
}

function renderError(msg, rejected = []) {
  let html = `
    <div class="adv-box" style="border-color: var(--red); background: rgba(239, 68, 68, 0.05);">
      <div style="color: var(--red); font-weight:600; margin-bottom:8px;">&#x274C; Advisory Generation Failed</div>
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
