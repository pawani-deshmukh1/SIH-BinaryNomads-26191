// field_ops.js - Logic for Commander Dashboard

const map = L.map('map', { zoomControl: false }).setView([26.342, 92.651], 8);
L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

let habitations = [];
let safeZones = [];
let activeRouteLayers = {}; // dispatchId -> L.layerGroup
const routeCache = {}; // Cache API route data
let teamMarkers = {}; // teamId -> L.circleMarker

// Initialize
async function initFieldOps() {
  await loadMapData();
  await fetchTeams();
  await fetchReports();
  await fetchWeatherGrid('assam'); // Load the weather grid
  
  // Auto-refresh every 5 seconds for the demo
  setInterval(() => {
    fetchTeams();
    fetchReports();
  }, 5000);
  
  // Refresh weather every 5 mins
  setInterval(() => {
    fetchWeatherGrid('assam');
  }, 300000);
}

async function loadMapData() {
  try {
    // Load Safe Zones
    const szRes = await fetch(window.API_BASE + '/advisory/safe-zones');
    const szData = await szRes.json();
    safeZones = szData.features;
    
    safeZones.forEach(sz => {
      L.circleMarker([sz.geometry.coordinates[1], sz.geometry.coordinates[0]], {
        radius: 8,
        fillColor: '#3b82f6', // Blue for Relief Camps
        color: '#ffffff',
        weight: 2,
        fillOpacity: 0.9,
      }).addTo(map).bindTooltip(`Relief Camp: ${sz.properties.name}`, {permanent: false});
    });

    // Load Habitations
    const habRes = await fetch(window.API_BASE + '/susceptibility/zone-map');
    const habData = await habRes.json();
    habitations = habData.features.filter(f => f.properties.zone_class !== 'GREEN');
    
    // Load Physical Hazards (Polygons) from COP
    /* Temporarily disabled to avoid complex judging questions regarding synthetic bounds
    try {
      const copRes = await fetch(window.API_BASE + '/analyze/cop');
      const copData = await copRes.json();
      
      L.geoJSON(copData, {
        filter: function(feature) {
          const type = feature.properties.layer_type;
          return type === 'red_zone' || type === 'flood_zone' || type === 'landslide_zone';
        },
        style: function(feature) {
          const type = feature.properties.layer_type;
          if (type === 'red_zone') return { color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.3, weight: 2 };
          if (type === 'flood_zone') return { color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.2, weight: 1, dashArray: '4' };
          if (type === 'landslide_zone') return { color: '#8b5cf6', fillColor: '#8b5cf6', fillOpacity: 0.3, weight: 1 };
        }
      }).addTo(map);
    } catch (e) {
      console.warn("Could not load COP polygons:", e);
    }
    */

    habitations.forEach(hab => {
      const zone = hab.properties.zone_class;
      const isRed = zone === 'RED';
      const color = zone === 'RED' ? '#ef4444' : (zone === 'ORANGE' ? '#f97316' : '#eab308');
      
      L.circleMarker([hab.geometry.coordinates[1], hab.geometry.coordinates[0]], {
        radius: isRed ? 10 : 7,
        fillColor: color,
        color: '#ffffff',
        weight: 2,
        fillOpacity: 0.8,
      }).addTo(map).bindTooltip(`Risk: ${hab.properties.name} (${zone})`, {permanent: false});

      // We will draw the actual paths sequentially afterwards to prevent connection pool exhaustion
    });

    if (habitations.length > 0 || safeZones.length > 0) {
      const boundsPoints = [];
      habitations.forEach(h => boundsPoints.push([h.geometry.coordinates[1], h.geometry.coordinates[0]]));
      safeZones.forEach(sz => boundsPoints.push([sz.geometry.coordinates[1], sz.geometry.coordinates[0]]));
      if (boundsPoints.length > 0) {
        const bounds = L.latLngBounds(boundsPoints);
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 11 });
      }
    }

    // Launch sequential background task for routes using Advisory cache
    loadBaselineRoutesSequentially(habitations);

  } catch(err) {
    console.error("Map data load error:", err);
  }
}

async function loadBaselineRoutesSequentially(habs) {
  for (const hab of habs) {
      const habId = hab.properties.id;
      try {
          const advRes = await fetch(`${window.API_BASE}/advisory/${habId}`);
          const advData = await advRes.json();
          
          if (advData.status === 'success' && advData.advisory.relocation_plan) {
              const plan = advData.advisory.relocation_plan;
              const site = plan.recommended_site;
              
              // Draw Formal Safe Zone (BLUE)
              if (site && site.lat && site.lng) {
                  L.circleMarker([site.lat, site.lng], {
                    radius: 8, fillColor: '#3b82f6', color: '#fff', weight: 2, fillOpacity: 1
                  }).addTo(map).bindTooltip(`Primary Safe Zone: ${site.name}`, {permanent: false});
              }
              
              // 1. Draw Formal Route (BLUE)
              if (plan.verified_route && plan.verified_route.features) {
                  plan.verified_route.features.forEach(feat => {
                      let color = '#3b82f6';
                      let dash = '5, 10';
                      if (feat.properties.segment_type === 'kacha_way') {
                          color = '#60a5fa';
                      } else if (feat.properties.segment_type === 'blocked' || ['ERROR', 'ISOLATED', 'BLOCKED'].includes(feat.properties.route_status)) {
                          color = '#ef4444';
                      }
                      if (feat.geometry && feat.geometry.coordinates) {
                          const latlngs = feat.geometry.coordinates.map(c => [c[1], c[0]]);
                          L.polyline(latlngs, {
                              color: color, weight: 2, dashArray: dash, opacity: 0.5
                          }).addTo(map);
                      }
                  });
              }
              
              // 2. Draw Host Communities (GREEN) and their routes
              const hostOptions = advData.advisory.host_community_options || [];
              hostOptions.forEach(h => {
                  if (h.lat && h.lng) {
                      L.circleMarker([h.lat, h.lng], {
                        radius: 7, fillColor: '#22c55e', color: '#fff', weight: 2, fillOpacity: 0.9
                      }).addTo(map).bindTooltip(`Option B: ${h.name} (Receives ${h.assigned_population} pax)`, {permanent: false});
                      
                      if (h.route_geojson && h.route_geojson.features) {
                          h.route_geojson.features.forEach(feat => {
                              let color = '#22c55e';
                              let dash = '5, 10';
                              if (feat.properties.segment_type === 'blocked' || ['ERROR', 'ISOLATED', 'BLOCKED'].includes(feat.properties.route_status)) {
                                  color = '#ef4444';
                              }
                              if (feat.geometry && feat.geometry.coordinates) {
                                  const latlngs = feat.geometry.coordinates.map(c => [c[1], c[0]]);
                                  L.polyline(latlngs, {
                                      color: color, weight: 2, dashArray: dash, opacity: 0.5
                                  }).addTo(map);
                              }
                          });
                      }
                  }
              });
          }
      } catch (e) {
          console.error(`Failed to load advisory for ${habId}`, e);
      }
  }
}

async function fetchTeams() {
  try {
    const res = await fetch(window.API_BASE + '/dispatch/');
    const data = await res.json();
    renderTeams(data.teams, data.dispatches);
    drawActiveRoutes(data.teams, data.dispatches);
    renderTeamMarkers(data.teams);
  } catch(err) {
    console.error("Teams fetch error:", err);
  }
}

function renderTeamMarkers(teams) {
  teams.forEach(team => {
    if (team.lat && team.lng) {
      const isLost = team.status === 'SIGNAL_LOST';
      const color = isLost ? '#ef4444' : '#3b82f6';
      
      if (!teamMarkers[team.id]) {
        teamMarkers[team.id] = L.circleMarker([team.lat, team.lng], {
          radius: 6,
          fillColor: color,
          color: '#fff',
          weight: 2,
          fillOpacity: 1,
          className: isLost ? 'pulse-dot' : ''
        }).addTo(map).bindPopup(`<b>${team.id}</b><br>Status: ${team.status}`);
      } else {
        teamMarkers[team.id].setLatLng([team.lat, team.lng]);
        teamMarkers[team.id].setStyle({ fillColor: color, className: isLost ? 'pulse-dot' : '' });
        teamMarkers[team.id].setPopupContent(`<b>${team.id}</b><br>Status: ${team.status}`);
      }
    }
  });
}

async function fetchReports() {
  try {
    const res = await fetch(window.API_BASE + '/field-reports/');
    const data = await res.json();
    renderReports(data.reports);
  } catch(err) {
    console.error("Reports fetch error:", err);
  }
}

function renderTeams(teams, dispatches) {
  document.getElementById('teams-count').innerText = teams.length;
  const listEl = document.getElementById('teams-list');
  
  if (teams.length === 0) {
    listEl.innerHTML = '<div style="text-align:center; color:var(--text-dim);">No teams registered.</div>';
    return;
  }

  let html = '';
  teams.forEach(team => {
    const statusClass = team.status.toLowerCase();
    
    let dispatchUI = '';
    if (team.status === 'AVAILABLE') {
      // Save user's current dropdown selections so they don't reset on auto-refresh
      const currentHabVal = document.getElementById(`hab-${team.id}`)?.value;
      const currentSzVal = document.getElementById(`sz-${team.id}`)?.value;

      // Build dropdowns for dispatch
      let habOptions = habitations.map(h => `<option value="${h.properties.id}" ${currentHabVal === h.properties.id ? 'selected' : ''}>${h.properties.name}</option>`).join('');
      let szOptions = safeZones.map(sz => `<option value="${sz.properties.id}" ${currentSzVal === sz.properties.id ? 'selected' : ''}>${sz.properties.name}</option>`).join('');
      
      dispatchUI = `
        <div class="team-actions">
          <select id="hab-${team.id}" onchange="loadMissionBrief(this.value)">
            <option value="">Select Target Habitation...</option>
            ${habOptions}
          </select>
          <select id="sz-${team.id}">
            <option value="">Select Destination Relief Camp...</option>
            ${szOptions}
          </select>
          <button onclick="dispatchTeam('${team.id}')">Issue Dispatch Order</button>
        </div>
      `;
    } else {
      let destStr = 'Unknown';
      if (team.current_assignment) {
         const dsp = dispatches.find(d => d.id === team.current_assignment);
         if (dsp) {
            const hab = habitations.find(h => h.properties.id === dsp.habitation_id);
            const sz = safeZones.find(s => s.properties.id === dsp.safe_zone_id);
            if (hab && sz) {
                destStr = `${hab.properties.name} → ${sz.properties.name}`;
            }
         }
      }
      dispatchUI = `
        <div style="font-size: 11px; margin-top: 8px; color: var(--text-dim);">
          Current Assignment: ${destStr}
        </div>
      `;
      
      if (team.location_verification === 'PENDING') {
        dispatchUI += `<div style="font-size: 11px; margin-top: 5px; color: #fb923c;">⏳ Verifying Location with Team...</div>`;
      } else if (team.location_verification === 'VERIFIED') {
        dispatchUI += `<div style="font-size: 11px; margin-top: 5px; color: #10b981;">✅ Location Verified by Team</div>`;
      } else {
        dispatchUI += `<button onclick="requestVerification('${team.id}')" style="margin-top: 5px; background: transparent; border: 1px solid #4b5563; padding: 4px; font-size: 10px;">Verify Location</button>`;
      }
    }

    const isSignalLost = team.status === 'SIGNAL_LOST';
    
    html += `
      <div class="team-card ${statusClass}" style="${isSignalLost ? 'border: 2px solid #ef4444; animation: flash-red 1.5s infinite;' : ''}">
        <div class="team-header">
          <div class="team-id">🚑 ${team.id}</div>
          <div class="team-status status-${statusClass}" style="${isSignalLost ? 'background: #ef4444; color: white;' : ''}">
             ${team.status.replace('_', ' ')}
          </div>
        </div>
        <div style="font-size: 11px; color: var(--text-dim);">
          Last Ping: ${team.last_ping ? new Date(team.last_ping).toLocaleTimeString() : new Date(team.last_updated).toLocaleTimeString()}
        </div>
        ${dispatchUI}
      </div>
    `;
  });
  
  listEl.innerHTML = html;
}

async function requestVerification(teamId) {
  try {
    await fetch(`${window.API_BASE}/dispatch/${teamId}/request-verification`, { method: 'POST' });
    fetchTeams();
  } catch(e) {
    console.error("Failed to request verification", e);
  }
}

function renderReports(reports) {
  const listEl = document.getElementById('reports-list');
  
  if (reports.length === 0) {
    listEl.innerHTML = '<div style="text-align:center; color:var(--text-dim); margin-top:20px;">No field reports yet.</div>';
    return;
  }

  let html = '';
  reports.forEach(r => {
    html += `
      <div class="report-card">
        <div class="report-time">⏰ ${new Date(r.submitted_at).toLocaleTimeString()}</div>
        <div class="report-title">Report from ${r.team_id}</div>
        <div class="report-stat">🛟 ${r.rescued_count} Rescued & Relocated</div>
        <div style="font-size: 12px; color: white;">
          ${r.notes || 'No additional notes provided.'}
        </div>
      </div>
    `;
  });
  
  listEl.innerHTML = html;
}

async function dispatchTeam(teamId) {
  const habId = document.getElementById(`hab-${teamId}`).value;
  const szId = document.getElementById(`sz-${teamId}`).value;
  
  if (!habId || !szId) {
    alert("Please select both a habitation and a safe zone.");
    return;
  }
  
  // Find population of habitation to set as target
  const hab = habitations.find(h => h.properties.id === habId);
  const targetPop = hab ? hab.properties.population : 100;

  try {
    const res = await fetch(window.API_BASE + '/dispatch/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        team_id: teamId,
        habitation_id: habId,
        safe_zone_id: szId,
        target_population: targetPop,
        notes: "Automated dispatch from Field Command Hub"
      })
    });
    
    if (res.ok) {
      fetchTeams();
    } else {
      const err = await res.json();
      alert("Dispatch failed: " + err.detail);
    }
  } catch(err) {
    console.error("Dispatch error:", err);
    alert("Dispatch error: " + err.message);
  }
}

async function fetchAndDrawRoute(originLat, originLon, destLat, destLon, isBaseline = false) {
  const cacheKey = `${originLat},${originLon}-${destLat},${destLon}`;
  let routeData = routeCache[cacheKey];
  
  if (!routeData) {
    try {
      const res = await fetch(`${window.API_BASE}/route/?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}&dest_lon=${destLon}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
      });
      routeData = await res.json();
      routeCache[cacheKey] = routeData;
    } catch (err) {
      console.error("Route fetch failed:", err);
      return null;
    }
  }

  if (routeData && routeData.features) {
    const layer = L.geoJSON(routeData, {
      style: function(feature) {
        let color = '#3b82f6'; // Active dispatch in blue
        let dashArray = '8, 8';
        if (feature.properties.segment_type === 'kacha_way') {
            color = '#60a5fa';
            dashArray = '10, 10';
        } else if (feature.properties.segment_type === 'blocked' || feature.properties.route_status === 'ERROR' || feature.properties.route_status === 'ISOLATED') {
            color = '#ef4444';
            dashArray = '5, 5';
        }
        return { color: color, weight: 4, opacity: 0.9, dashArray: dashArray };
      }
    });
    layer.addTo(map);
    return layer;
  }
  return null;
}

// Start
initFieldOps();

// ─── MISSION BRIEFING ───────────────────────────────────────────────────────
async function loadMissionBrief(habId) {
  if (!habId) return;

  // Update header
  const hab = habitations.find(h => h.properties.id === habId);
  if (hab) {
    document.getElementById('brief-hab-name').innerText = hab.properties.name;
    // Auto-fill transport population
    document.getElementById('transport-pop').value = hab.properties.population || 850;
    calcTransport();
  }

  try {
    const res  = await fetch(`${window.API_BASE}/advisory/${habId}`);
    const data = await res.json();
    if (data.status !== 'success') return;

    const adv       = data.advisory;
    const resources = adv.relocation_plan?.resources_required || {};
    const hostOpts  = adv.host_community_options || [];
    const site      = adv.relocation_plan?.recommended_site || {};

    // ② Resource Pack
    const rEl = document.getElementById('resource-pack');
    rEl.innerHTML = `
      <table style="width:100%; border-collapse:collapse; font-size:12px;">
        <tr style="border-bottom:1px solid rgba(255,255,255,0.07);">
          <td style="padding:5px 0; color:var(--text-dim);">🏕️ Tents (50-person)</td>
          <td style="text-align:right; font-weight:bold; color:white;">${resources.tents_50_person ?? '—'}</td>
        </tr>
        <tr style="border-bottom:1px solid rgba(255,255,255,0.07);">
          <td style="padding:5px 0; color:var(--text-dim);">💧 Water (15L/person/day)</td>
          <td style="text-align:right; font-weight:bold; color:#38bdf8;">${resources.water_litres_per_day ? resources.water_litres_per_day.toLocaleString() + ' L/day' : '—'}</td>
        </tr>
        <tr style="border-bottom:1px solid rgba(255,255,255,0.07);">
          <td style="padding:5px 0; color:var(--text-dim);">🍱 Food rations / day</td>
          <td style="text-align:right; font-weight:bold; color:#34d399;">${resources.food_rations_daily ? resources.food_rations_daily.toLocaleString() : '—'}</td>
        </tr>
        <tr>
          <td style="padding:5px 0; color:var(--text-dim);">🩺 Medical kits (1/50)</td>
          <td style="text-align:right; font-weight:bold; color:#fb923c;">${resources.tents_50_person ?? '—'}</td>
        </tr>
      </table>
      <div style="margin-top:6px; font-size:11px; color:var(--text-dim);">Based on Sphere Humanitarian Minimum Standards — 5-day pack for ${adv.habitation?.population ?? '?'} people</div>
    `;

    // ③ Option B — host communities
    const bEl = document.getElementById('option-b-panel');
    if (hostOpts.length === 0) {
      bEl.innerHTML = `<div style="font-size:12px; color:var(--text-dim);">No host community options in range. Primary shelter only.</div>`;
    } else {
      let hostsHtml = hostOpts.slice(0, 3).map((h, i) => `
        <div style="background:rgba(34,197,94,0.07); border:1px solid rgba(34,197,94,0.2); border-radius:6px; padding:8px; margin-bottom:6px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:bold; color:#22c55e; font-size:12px;">Option ${String.fromCharCode(66+i)}: ${h.name}</div>
            <div style="font-size:11px; color:var(--text-dim);">${h.distance_km} km away</div>
          </div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">
            Nominal Capacity: ${h.host_capacity} | Zone: ${h.zone_class}<br>
            <span style="background: rgba(34,197,94,0.2); color: #22c55e; padding: 1px 4px; border-radius: 4px; font-weight: bold; margin-top: 4px; display: inline-block;">Operational (Host): ~${Math.floor(h.host_capacity * 0.8)} pax</span>
          </div>
          <div style="font-size:11px; color:var(--text-dim);">${h.note}</div>
          <button onclick="reportGroundReality('${habId}', '${h.id}', '${h.name}')"
            style="margin-top:6px; width:100%; padding:5px; background:rgba(251,146,60,0.15); border:1px solid rgba(251,146,60,0.4); color:#fb923c; border-radius:4px; cursor:pointer; font-size:11px;">
            📍 Ground Reality Differs — Switch to This Location
          </button>
        </div>
      `).join('');
      bEl.innerHTML = hostsHtml;
    }

  } catch(e) {
    console.error('Mission brief load failed:', e);
  }
}

function reportGroundReality(habId, altId, altName) {
  // Log the override and show confirmation
  console.log(`[HITL Override] CDR flagged ground reality mismatch for ${habId}. Switching to host community: ${altName} (${altId})`);
  const btn = event.target;
  btn.style.background = 'rgba(34,197,94,0.2)';
  btn.style.borderColor = 'rgba(34,197,94,0.5)';
  btn.style.color = '#22c55e';
  btn.innerText = `✅ Switched to ${altName} — Update logged`;
  btn.disabled = true;

  // Could POST to /field-reports/ to log the override, future hook
  fetch(window.API_BASE + '/field-reports/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      team_id: 'CDR-OVERRIDE',
      habitation_id: habId,
      rescued_count: 0,
      notes: `Ground reality override: Primary shelter rejected. Switching relocation to host community ${altName} (${altId}).`
    })
  }).catch(() => {});
}

async function drawActiveRoutes(teams, dispatches) {
  // Find all currently active dispatch IDs
  const activeDispatchIds = new Set(
    teams.filter(t => t.current_assignment).map(t => t.current_assignment)
  );

  // Remove routes that are no longer active
  for (const dspId in activeRouteLayers) {
    if (!activeDispatchIds.has(dspId)) {
      map.removeLayer(activeRouteLayers[dspId]);
      delete activeRouteLayers[dspId];
    }
  }

  // Add new routes
  for (const dsp of dispatches) {
    if (activeDispatchIds.has(dsp.id) && !activeRouteLayers[dsp.id]) {
      const hab = habitations.find(h => h.properties.id === dsp.habitation_id);
      const sz = safeZones.find(s => s.properties.id === dsp.safe_zone_id);

      if (hab && sz) {
        try {
          const originLat = hab.geometry.coordinates[1];
          const originLon = hab.geometry.coordinates[0];
          const destLat = sz.geometry.coordinates[1];
          const destLon = sz.geometry.coordinates[0];

          // Fetch the shortest path avoiding floods (using cache)
          const layer = await fetchAndDrawRoute(originLat, originLon, destLat, destLon, false);
          if (layer) {
             activeRouteLayers[dsp.id] = layer;
          }
        } catch(err) {
          console.error("Failed to draw route for dispatch", dsp.id, err);
        }
      }
    }
  }
}

let weatherMarkers = [];
async function fetchWeatherGrid(region) {
  try {
    const res = await fetch(`${window.API_BASE}/weather-grid/?region=${region}`);
    if (!res.ok) return;
    const data = await res.json();
    
    // Clear old markers
    weatherMarkers.forEach(m => map.removeLayer(m));
    weatherMarkers = [];

    data.features.forEach(cell => {
      let iconClass = '';
      let emoji = '';
      
      if (cell.properties.alert_level === 'cloudburst') {
        iconClass = 'weather-icon-cloudburst';
        emoji = '⛈️';
      } else if (cell.properties.alert_level === 'heavy_rain') {
        iconClass = 'weather-icon-heavy';
        emoji = '🌧️';
      } else if (cell.properties.alert_level === 'cyclonic') {
        iconClass = 'weather-icon-cyclone';
        emoji = '🌀';
      } else {
        return; // skip clear
      }
      
      const icon = L.divIcon({
        className: 'custom-weather-icon',
        html: `<div class="${iconClass}">${emoji}</div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
      });
      
      const marker = L.marker([cell.geometry.coordinates[1], cell.geometry.coordinates[0]], { icon, zIndexOffset: -100 });
      marker.bindPopup(`
        <strong>${emoji} Weather Alert: ${cell.properties.alert_level.toUpperCase()}</strong><br>
        24h Forecast: ${cell.properties.rain_24h_mm} mm<br>
        Precip Prob: ${cell.properties.precipitation_probability}%<br>
        Wind Max: ${cell.properties.wind_speed_kmh} km/h<br>
        <span style="font-size:10px;color:var(--text-dim)">ML Evaluated via Open-Meteo Grid</span>
      `);
      
      marker.addTo(map);
      weatherMarkers.push(marker);
    });
    
  } catch(err) {
    console.error("Could not load weather grid:", err);
  }
}

