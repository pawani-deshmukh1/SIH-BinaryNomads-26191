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
  
  // Auto-refresh every 5 seconds for the demo
  setInterval(() => {
    fetchTeams();
    fetchReports();
  }, 5000);
}

async function loadMapData() {
  try {
    // Load Safe Zones
    const szRes = await fetch('http://127.0.0.1:8000/advisory/safe-zones');
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
    const habRes = await fetch('http://127.0.0.1:8000/susceptibility/zone-map');
    const habData = await habRes.json();
    habitations = habData.features.filter(f => f.properties.zone_class !== 'GREEN');
    
    // Load Physical Hazards (Polygons) from COP
    try {
      const copRes = await fetch('http://127.0.0.1:8000/analyze/cop');
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

    // Launch sequential background task for routes
    loadBaselineRoutesSequentially(habitations, safeZones);

  } catch(err) {
    console.error("Map data load error:", err);
  }
}

async function loadBaselineRoutesSequentially(habs, szs) {
  for (const hab of habs) {
      let nearestSZ = null;
      let minDist = Infinity;
      szs.forEach(sz => {
         let dist = Math.hypot(hab.geometry.coordinates[1] - sz.geometry.coordinates[1], hab.geometry.coordinates[0] - sz.geometry.coordinates[0]);
         if(dist < minDist) { minDist = dist; nearestSZ = sz; }
      });
      if(nearestSZ) {
          const originLat = hab.geometry.coordinates[1];
          const originLon = hab.geometry.coordinates[0];
          const destLat = nearestSZ.geometry.coordinates[1];
          const destLon = nearestSZ.geometry.coordinates[0];
          
          await fetchAndDrawRoute(originLat, originLon, destLat, destLon, true);
      }
  }
}

async function fetchTeams() {
  try {
    const res = await fetch('http://127.0.0.1:8000/dispatch/');
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
    const res = await fetch('http://127.0.0.1:8000/field-reports/');
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
          <select id="hab-${team.id}">
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
    await fetch(`http://127.0.0.1:8000/dispatch/${teamId}/request-verification`, { method: 'POST' });
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
    const res = await fetch('http://127.0.0.1:8000/dispatch/', {
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
      const res = await fetch(`http://127.0.0.1:8000/route/?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}&dest_lon=${destLon}`, {
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
        if (isBaseline) {
          return { color: '#ffffff', weight: 2, dashArray: '5, 10', opacity: 0.5 };
        } else {
          let color = '#0ea5e9'; // Active dispatch
          let dashArray = '8, 8';
          if (feature.properties.segment_type === 'kacha_way') {
              color = '#8B4513';
              dashArray = '10, 10';
          } else if (feature.properties.segment_type === 'blocked' || feature.properties.route_status === 'ERROR' || feature.properties.route_status === 'ISOLATED') {
              color = '#ef4444';
              dashArray = '5, 5';
          }
          return { color: color, weight: 4, opacity: 0.9, dashArray: dashArray };
        }
      }
    });
    layer.addTo(map);
    return layer;
  }
  return null;
}

// Start
initFieldOps();

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

