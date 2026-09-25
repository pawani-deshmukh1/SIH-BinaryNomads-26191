// map.js - Handles Leaflet and Zone Data

const map = L.map('map', { zoomControl: false }).setView([26.342, 92.651], 8);
L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

let currentHabitations = [];
let mapMarkers = {}; // hab.id -> L.circleMarker
let safeZoneMarkers = [];
let towerMarkers = [];
let weatherMarkers = [];
let floodPolygonLayer = null;
let commsLayerActive = false;
let weatherLayerActive = true;
let habClusterLayer = null;

let nwdpMarkers = [];
let nwdpLayerActive = false;

let bhuvanWMSLayer = null;
let bhuvanLayerActive = false;

// Colors for zones
const ZONE_COLORS = {
  'RED': '#ef4444',
  'ORANGE': '#f97316',
  'YELLOW': '#eab308',
  'GREEN': '#22c55e'
};

async function initDashboard() {
  document.getElementById('loader').classList.add('active');
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const region = urlParams.get('region') || 'assam';

    // 1. Fetch the Susceptibility Zone Map
    const res = await fetch(`${window.API_BASE}/susceptibility/zone-map?region=${region}`);
    if (!res.ok) throw new Error('Failed to fetch zone map');
    
    const data = await res.json();
    currentHabitations = data.features.map(f => ({
      id: f.properties.id,
      name: f.properties.name,
      population: f.properties.population,
      type: f.properties.id.includes('CHAR') ? 'char' : 
            f.properties.id.includes('KARBI') ? 'tribal' :
            f.properties.id.includes('URBAN') ? 'urban' : 
            f.properties.id.includes('TEAGARDEN') ? 'tea_garden' : 'riverbank',
      zone: f.properties.zone_class,
      raw_flood_score: f.properties.flood_score,
      raw_landslide_score: f.properties.landslide_score,
      vulnerability: f.properties.sc_st_percent,
      women_pct: f.properties.women_percent || 49,
      children_pct: f.properties.children_percent || 29,
      elderly_pct: f.properties.elderly_percent || 8,
      landless: f.properties.landless_pct,
      literacy: f.properties.literacy_rate_pct,
      hospital: f.properties.nearest_hospital_km,
      lat: f.geometry.coordinates[1],
      lng: f.geometry.coordinates[0]
    }));
    
    // 2. Fetch Safe Zones (just for visualization)
    await fetchSafeZones();
    
    // 3. Fetch Towers (Comms Layer)
    await fetchTowers(region);
    
    // 4. Render everything
    renderHabitations();
    updateSidebarCounts();
    
    // 5. Fetch Weather Grid
    await fetchWeatherGrid(region);
    
    // 6. Fetch Flood Polygon
    await fetchFloodPolygon(region);
    
    // 7. Load Wind Vectors (NDEM Style)
    await loadWindVectors();
    
    // Auto-fit bounds (Zoomed out slightly for Pan-India/NDEM feel)
    if (currentHabitations.length > 0) {
      const bounds = L.latLngBounds(currentHabitations.map(h => [h.lat, h.lng]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 6 });
    }
    
  } catch (err) {
    console.error(err);
    alert('Dashboard Error: ' + err.message + '\n\nStack: ' + err.stack);
  } finally {
    document.getElementById('loader').classList.remove('active');
  }
}

async function fetchSafeZones() {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const region = urlParams.get('region') || 'assam';
    const res = await fetch(`${window.API_BASE}/advisory/safe-zones?region=${region}`);
    if (!res.ok) throw new Error('Failed to fetch safe zones');
    
    const data = await res.json();
    
    data.features.forEach(sz => {
      const marker = L.circleMarker([sz.geometry.coordinates[1], sz.geometry.coordinates[0]], {
        radius: 8,
        fillColor: '#3b82f6', // Blue for Relief Camps
        color: '#ffffff',
        weight: 2,
        fillOpacity: 0.9,
      }).addTo(map);
      
      marker.bindPopup(`<strong>🏕️ Relief Camp</strong><br>${sz.properties.name}<br>Capacity: ${sz.properties.capacity}`);
      safeZoneMarkers.push(marker);
    });
  } catch(err) {
    console.error("Could not load safe zones:", err);
  }
}

async function fetchTowers(region) {
  try {
    const res = await fetch(`${window.API_BASE}/towers/?region=${region}`);
    if (!res.ok) return;
    const data = await res.json();
    
    data.features.forEach(tower => {
      const isAtRisk = tower.properties.status === 'at_risk';
      const isPredictedOffline = tower.properties.status === 'predicted_offline';
      
      let color = '#22c55e'; // Green for operational
      let pulseClass = '';
      if (isAtRisk) {
        color = '#ef4444'; // Red for at risk
        pulseClass = 'marker-pulse-RED';
      }
      
      const svgIcon = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 22h14M2 22h3M19 22h3M8.6 22l3.4-18M15.4 22l-3.4-18M8 12h8M6.5 16h11" />
          <circle cx="12" cy="4" r="2" fill="${isAtRisk ? color : 'transparent'}" />
        </svg>
      `;

      const icon = L.divIcon({
        className: 'custom-tower-icon ' + pulseClass,
        html: svgIcon,
        iconSize: [24, 24],
        iconAnchor: [12, 24]
      });

      const marker = L.marker([tower.geometry.coordinates[1], tower.geometry.coordinates[0]], { icon });
      
      let statusHtml = '✅ Operational';
      if (isAtRisk) statusHtml = '⚠️ AT RISK';
      
      marker.bindPopup(`<strong>🗼 Cell Tower</strong><br>${tower.properties.name || tower.properties.id}<br>Operator: ${tower.properties.operator}<br>Status: ${statusHtml}`);
      towerMarkers.push({ marker, isAtRisk });
      
      // Add Coverage Circles for the Comms Shadow Demo
      if (!isAtRisk && !isPredictedOffline) {
        const coverage = L.circle([tower.geometry.coordinates[1], tower.geometry.coordinates[0]], {
          radius: 3000,
          color: '#22c55e',
          weight: 1,
          fillOpacity: 0.05
        });
        towerMarkers.push({ marker: coverage, isCoverage: true });
      } else if (isAtRisk) {
        const shadow = L.circle([tower.geometry.coordinates[1], tower.geometry.coordinates[0]], {
          radius: 3000,
          color: '#ef4444',
          weight: 1,
          fillOpacity: 0.15,
          dashArray: "10, 10"
        });
        shadow.bindPopup(`<strong>📡 COMMS SHADOW WARNING</strong><br>Coverage failed.`);
        towerMarkers.push({ marker: shadow, isCoverage: true });
      }
    });
    
    document.getElementById('layer-comms')?.addEventListener('click', toggleCommsLayer);
    document.getElementById('layer-nwdp')?.addEventListener('click', toggleNwdpLayer);
    document.getElementById('layer-bhuvan')?.addEventListener('click', toggleBhuvanLayer);
  } catch(err) {
    console.error("Could not load towers:", err);
  }
}

function toggleCommsLayer() {
  commsLayerActive = !commsLayerActive;
  const btn = document.getElementById('layer-comms');
  
  if (commsLayerActive) {
    if(btn) { btn.style.background = 'var(--orange)'; btn.style.color = 'black'; }
    towerMarkers.forEach(t => t.marker.addTo(map));
  } else {
    if(btn) { btn.style.background = 'rgba(15,23,42,0.9)'; btn.style.color = 'white'; }
    towerMarkers.forEach(t => map.removeLayer(t.marker));
  }
}

async function fetchNwdpData() {
  try {
    const res = await fetch(`${window.API_BASE}/api/nwdp/reservoirs`);
    if (!res.ok) return;
    const data = await res.json();
    
    data.data.forEach(res => {
      const icon = L.divIcon({
        className: 'custom-nwdp-icon ' + (res.status !== 'NORMAL' ? 'marker-pulse-RED' : ''),
        html: `<div style="background:${res.color}; width:16px; height:16px; border-radius:50%; border:2px solid white; box-shadow:0 0 8px ${res.color};"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      });
      
      const marker = L.marker([res.lat, res.lng], { icon });
      marker.bindPopup(`<strong>💧 NWDP Reservoir Telemetry</strong><br>${res.name}<br>Level: ${res.level_m}m<br>Capacity: ${res.capacity_pct.toFixed(1)}%<br>Status: <strong>${res.status}</strong><br><span style="font-size:10px;color:gray;">Source: nwdp.nwic.gov.in</span>`);
      nwdpMarkers.push(marker);
      if (nwdpLayerActive) {
        marker.addTo(map);
      }
    });
  } catch(err) {
    console.error("Could not load NWDP data:", err);
  }
}

function toggleNwdpLayer() {
  nwdpLayerActive = !nwdpLayerActive;
  const btn = document.getElementById('layer-nwdp');
  
  if (nwdpLayerActive) {
    if(btn) { btn.style.background = '#0ea5e9'; btn.style.color = 'black'; }
    if (nwdpMarkers.length === 0) fetchNwdpData();
    else nwdpMarkers.forEach(m => m.addTo(map));
  } else {
    if(btn) { btn.style.background = 'rgba(14, 165, 233, 0.2)'; btn.style.color = '#bae6fd'; }
    nwdpMarkers.forEach(m => map.removeLayer(m));
  }
}

function toggleBhuvanLayer() {
  bhuvanLayerActive = !bhuvanLayerActive;
  const btn = document.getElementById('layer-bhuvan');
  
  if (bhuvanLayerActive) {
    if(btn) { btn.style.background = '#22c55e'; btn.style.color = 'black'; }
    if (!bhuvanWMSLayer) {
      // Using a highly available global LULC/Satellite WMS as a resilient fallback for Bhuvan
      // to prevent SSL/CORS timeouts during the live hackathon demo.
      bhuvanWMSLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: "ISRO Bhuvan (Simulated via Esri for Demo Stability)"
      });
    }
    bhuvanWMSLayer.addTo(map);
  } else {
    if(btn) { btn.style.background = 'rgba(34, 197, 94, 0.2)'; btn.style.color = '#bbf7d0'; }
    if (bhuvanWMSLayer) map.removeLayer(bhuvanWMSLayer);
  }
}

async function fetchWeatherGrid(region) {
  try {
    const res = await fetch(`${window.API_BASE}/weather-grid/?region=${region}`);
    if (!res.ok) return;
    const data = await res.json();
    
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
        iconAnchor: [20, 55] // Shifted upwards so it hovers above the habitation dot
      });
      
      const marker = L.marker([cell.geometry.coordinates[1], cell.geometry.coordinates[0]], { icon });
      marker.bindPopup(`
        <strong>${emoji} Weather Alert: ${cell.properties.alert_level.toUpperCase()}</strong><br>
        24h Forecast: ${cell.properties.rain_24h_mm} mm<br>
        Precip Prob: ${cell.properties.precipitation_probability}%<br>
        Wind Max: ${cell.properties.wind_speed_kmh} km/h<br>
        <span style="font-size:10px;color:var(--text-dim)">Source: Open-Meteo Grid</span>
      `);
      
      marker.addTo(map);
      weatherMarkers.push(marker);
    });
    
  } catch(err) {
    console.error("Could not load weather grid:", err);
  }
}

async function fetchFloodPolygon(region) {
  try {
    const res = await fetch(`${window.API_BASE}/inundation/demo?region=${region}`);
    if (!res.ok) return;
    const data = await res.json();
    
    if (data.features && data.features.length > 0) {
      // Pick the +2.0m scenario (index 3 usually) or the last one
      const feature = data.features.length > 3 ? data.features[3] : data.features[data.features.length - 1];
      
      floodPolygonLayer = L.geoJSON(feature, {
        style: function (f) {
          return {
            color: '#3b82f6',
            weight: 2,
            dashArray: '5, 5',
            fillColor: '#3b82f6',
            fillOpacity: 0.15
          };
        }
      });
      
      floodPolygonLayer.bindPopup(`<strong>🌊 Simulated Flood Inundation</strong><br>Level: ${feature.properties.scenario_label}<br>Area: ${feature.properties.affected_area_km2} km²`);
      floodPolygonLayer.addTo(map);
    }
  } catch(err) {
    console.error("Could not load flood polygon:", err);
  }
}

function renderHabitations() {
  const listEl = document.getElementById('hab-list');
  if(listEl) listEl.innerHTML = '';
  
  // Sort by risk (RED first, then ORANGE, etc), then by vulnerability descending
  const sortOrder = { 'RED': 1, 'ORANGE': 2, 'YELLOW': 3, 'GREEN': 4 };
  currentHabitations.sort((a, b) => {
    if (sortOrder[a.zone] !== sortOrder[b.zone]) {
      return sortOrder[a.zone] - sortOrder[b.zone];
    }
    return b.vulnerability - a.vulnerability;
  });

  // Create Cluster Group
  if (habClusterLayer) {
    map.removeLayer(habClusterLayer);
  }
  
  habClusterLayer = L.markerClusterGroup({
    iconCreateFunction: function(cluster) {
      const children = cluster.getAllChildMarkers();
      const count = cluster.getChildCount();
      
      let clusterColor = '#22c55e'; // Default Green
      let hasRed = false;
      let hasOrange = false;
      let hasYellow = false;
      
      children.forEach(marker => {
        const color = marker.options.fillColor;
        if (color === '#ef4444') hasRed = true;
        else if (color === '#f97316') hasOrange = true;
        else if (color === '#eab308') hasYellow = true;
      });
      
      if (hasRed) clusterColor = '#ef4444';
      else if (hasOrange) clusterColor = '#f97316';
      else if (hasYellow) clusterColor = '#eab308';
      
      const pulseClass = hasRed ? 'marker-pulse-RED' : (hasOrange ? 'marker-glow-ORANGE' : '');

      return L.divIcon({
          className: 'custom-cluster-icon ' + pulseClass,
          html: `
              <div style="background-color: ${clusterColor}; color: white; width: 36px; height: 36px; display: flex; justify-content: center; align-items: center; border-radius: 50%; font-weight: bold; border: 2px solid white; box-shadow: 0 0 10px ${clusterColor};">
                  ${count}
              </div>
          `,
          iconSize: [36, 36],
          iconAnchor: [18, 18]
      });
    },
    maxClusterRadius: 60,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true
  });
  
  currentHabitations.forEach(hab => {
    // 1. Draw on Map
    const color = ZONE_COLORS[hab.zone] || '#94a3b8';
    
    const marker = L.circleMarker([hab.lat, hab.lng], {
      radius: hab.zone === 'RED' ? 10 : 8,
      fillColor: color,
      color: '#ffffff',
      weight: 2,
      fillOpacity: 0.8,
    });
    
    habClusterLayer.addLayer(marker);
    
    // Add pulsing css class if RED
    if (hab.zone === 'RED') {
      marker.getElement()?.classList.add('marker-pulse-RED');
    } else if (hab.zone === 'ORANGE') {
      marker.getElement()?.classList.add('marker-glow-ORANGE');
    }
    
    // Click opens advisory panel
    marker.on('click', () => {
      openAdvisory(hab.id);
    });
    
    mapMarkers[hab.id] = marker;
    
    // 2. Add to Sidebar List
    const card = document.createElement('div');
    card.className = 'hab-card';
    card.id = `card-${hab.id}`;
    card.onclick = () => {
      map.flyTo([hab.lat, hab.lng], 13);
      openAdvisory(hab.id);
    };
    
    const typeIcon = hab.type === 'char' ? '🏝️' : hab.type === 'tribal' ? '🏕️' : hab.type === 'urban' ? '🏢' : hab.type === 'tea_garden' ? '🍃' : '🌊';
    card.innerHTML = `
      <div class="hab-info">
        <h4>${typeIcon} ${hab.name}</h4>
        <p>${hab.type.replace('_', ' ')} · Pop: ${hab.population}</p>
        <div style="font-size:10px; color:var(--text-dim); margin-top:4px; line-height: 1.4;">
          <span style="color:var(--orange)">⚠ Social Vulnerability Drivers:</span><br>
          SC/ST: ${hab.vulnerability}% | Landless: ${hab.landless}%<br>
          <hr style="border-color:#333; margin:5px 0;">
          <b style="color:var(--text-bright)">Demographics:</b><br>
          Women: ${hab.women_pct}% | Children: ${hab.children_pct}% | Elderly: ${hab.elderly_pct}%<br>
          Literacy: ${hab.literacy}% | Hospital: ${hab.hospital}km
        </div>
      </div>
      <div class="zone-badge ${hab.zone}">${hab.zone}</div>
    `;
    
    if(listEl) listEl.appendChild(card);
  });
  
  map.addLayer(habClusterLayer);
}

function updateSidebarCounts() {
  const counts = { RED: 0, ORANGE: 0, YELLOW: 0 };
  currentHabitations.forEach(h => {
    if (counts[h.zone] !== undefined) counts[h.zone]++;
  });
  
  if(document.getElementById('count-red')) document.getElementById('count-red').textContent = counts.RED;
  if(document.getElementById('count-orange')) document.getElementById('count-orange').textContent = counts.ORANGE;
  if(document.getElementById('count-yellow')) document.getElementById('count-yellow').textContent = counts.YELLOW;
}

// Remove escalateMapZones entirely, as we do it in triggerInundationSpread

// Start the dashboard
initDashboard();

// ---- NDEM UI Additions ----

async function loadWindVectors() {
    try {
        const res = await fetch('data/wind-global.json');
        const data = await res.json();
        
        const velocityLayer = L.velocityLayer({
            displayValues: true,
            displayOptions: {
                velocityType: 'Global Wind',
                displayPosition: 'bottomleft',
                displayEmptyString: 'No wind data'
            },
            data: data,
            maxVelocity: 15,
            velocityScale: 0.015,
            particleAge: 60,
            particleMultiplier: 1/300,
            lineWidth: 2,
            colorScale: ['#ffffff', '#a3e635', '#4ade80', '#2dd4bf', '#38bdf8'] // NDEM greenish-white wind colors
        });
        
        velocityLayer.addTo(map);
    } catch (e) {
        console.error("Failed to load wind vectors: ", e);
    }
}

// ---- Auto-Score Mode Logic ----
let autoScoreMode = false;
document.getElementById('btn-auto-score')?.addEventListener('click', () => {
    autoScoreMode = !autoScoreMode;
    const btn = document.getElementById('btn-auto-score');
    if (autoScoreMode) {
        btn.style.background = '#ec4899';
        btn.style.color = 'white';
        map.getContainer().style.cursor = 'crosshair';
        alert("Live Coord-Score Mode Active:\nClick anywhere on the map to run the real-time terrain ML pipeline for that exact coordinate.");
    } else {
        btn.style.background = 'rgba(236, 72, 153, 0.2)';
        btn.style.color = '#fbcfe8';
        map.getContainer().style.cursor = '';
    }
});

// Global state for passing data to the popup form without stringifying
window.__currentGroundSurveyData = null;

// Function to render the form inside the popup
window.openGroundSurveyForm = function() {
    // Use setTimeout so the click event finishes bubbling BEFORE we destroy the button DOM.
    // If we destroy it synchronously, Leaflet loses the event path and thinks you clicked the map!
    setTimeout(() => {
        if (!window.__currentGroundSurveyData) return;
        const { lat, lng, t, popupId } = window.__currentGroundSurveyData;
        
        // Find the popup container by ID
        const container = document.getElementById(popupId);
        if (!container) return;
        
        container.innerHTML = `
            <div style="font-family:'Inter', sans-serif; min-width: 260px;">
                <div style="font-weight:bold; color:#14b8a6; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:5px; font-size: 13px;">
                    📝 Add Ground Survey
                </div>
                <div style="display:flex; flex-direction:column; gap:8px;">
                    <input type="text" id="gs-name" placeholder="Settlement Name" style="width:100%; padding:6px; border-radius:4px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:12px;">
                    
                    <div style="display:flex; gap:8px;">
                        <input type="number" id="gs-pop" placeholder="Population" style="flex:1; padding:6px; border-radius:4px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:12px;">
                        <input type="number" id="gs-hh" placeholder="Households" style="flex:1; padding:6px; border-radius:4px; border:1px solid #334155; background:#0f172a; color:#fff; font-size:12px;">
                    </div>
                    
                    <button onclick="event.stopPropagation(); submitGroundSurvey();" style="margin-top:8px; width:100%; padding:8px; background:#14b8a6; color:#fff; border:none; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">
                        Save to Monitoring Grid
                    </button>
                </div>
            </div>
        `;
    }, 50);
};

window.submitGroundSurvey = async function() {
    const data = window.__currentGroundSurveyData;
    if (!data) return;
    
    const name = document.getElementById('gs-name').value;
    const pop = document.getElementById('gs-pop').value;
    const hh = document.getElementById('gs-hh').value;
    
    if (!name || !pop) {
        alert("Please enter at least Name and Population.");
        return;
    }
    
    const btn = document.querySelector('button[onclick="submitGroundSurvey()"]');
    if (btn) btn.innerText = "Saving...";
    
    const payload = {
        name: name,
        lat: data.lat,
        lng: data.lng,
        population: parseInt(pop) || 0,
        households: parseInt(hh) || Math.floor((parseInt(pop)||0)/5),
        elevation_m: data.t.elevation || data.t.elevation_m || 0,
        slope_deg: data.t.slope || data.t.slope_deg || 0,
        aspect_deg: data.t.aspect || data.t.aspect_deg || 0,
        tri: data.t.tri || 0,
        twi: data.t.twi || 0,
        dist_to_river_m: data.t.dist_to_river_m || 3000,
        precip_annual_mm: data.t.precip_annual_mm || 1800,
        precip_daily_mm: data.t.precip_daily_mm || 10,
        vegetation_proxy: data.t.vegetation_proxy || 0.5,
        hand_proxy_m: data.t.hand_proxy_m || 10.0
    };
    
    try {
        const res = await fetch(window.API_BASE + '/susceptibility/habitations/add?region=' + (window.CURRENT_REGION || 'assam'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const resData = await res.json();
        if (resData.status === 'success') {
            const container = document.getElementById(data.popupId);
            if (container) {
                container.innerHTML = `<div style="text-align:center; color:#22c55e; padding:10px; font-weight:bold;">✅ Saved successfully!<br><span style="font-size:11px; font-weight:normal; color:#94a3b8;">Location is now monitored.</span></div>`;
            }
            // Trigger a refresh of the habitation layer if possible
            if (typeof renderHabitations === 'function') {
                setTimeout(() => renderHabitations(), 1000);
            }
        } else {
            alert("Error saving: " + resData.error);
        }
    } catch (e) {
        alert("Failed to reach server: " + e.message);
    }
};

map.on('click', async (e) => {
    if (!autoScoreMode) return;
    
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    
    const popup = L.popup()
        .setLatLng(e.latlng)
        .setContent(`<div style="text-align:center; font-family:'Inter', sans-serif; padding:8px;">
                        <div style="margin: 0 auto 10px; width:20px; height:20px; border:2px solid rgba(255,255,255,0.1); border-top-color:#60a5fa; border-radius:50%; animation:spin 1s linear infinite;"></div>
                        <div style="font-size:12px; color:#94a3b8;">Fetching live terrain from SRTM...</div>
                     </div>`)
        .openOn(map);
        
    try {
        const res = await fetch(`${window.API_BASE}/susceptibility/auto-score?lat=${lat}&lng=${lng}`);
        const data = await res.json();
        
        if (data.status === 'success') {
            // API shape: {status, coordinates, data_source, terrain_features, risk_assessment, zone_class, flood_score, landslide_score}
            const t = data.terrain_features;          // top-level object
            const floodScore = data.flood_score;       // flat top-level float
            const lsScore = data.landslide_score;      // flat top-level float
            const zone = data.zone_class;
            const dataSource = data.data_source || 'live';
            const zoneColor = zone === 'RED' ? '#ef4444' : zone === 'ORANGE' ? '#f97316' : zone === 'YELLOW' ? '#eab308' : '#22c55e';
            
            const popupId = 'gs-popup-' + Date.now();
            
            popup.setContent(`
                <div id="${popupId}" style="font-family:'Inter', sans-serif; min-width: 260px;">
                    <div style="font-weight:bold; color:#60a5fa; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:5px; font-size: 13px;">
                        📍 Live Coordinate Score
                    </div>
                    <div style="font-size:11px; margin-bottom:6px; font-family: monospace; color:#94a3b8;">
                        ${lat.toFixed(5)}, ${lng.toFixed(5)} · <span style="color:${dataSource === 'live' ? '#22c55e' : '#f59e0b'}">${dataSource === 'live' ? '⚡ Live SRTM' : '⚠ Defaults'}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; padding:8px; background:rgba(0,0,0,0.3); border-radius:6px; border-left: 3px solid ${zoneColor};">
                        <div style="font-size:18px; font-weight:900; color:${zoneColor}; letter-spacing:1px;">${zone}</div>
                        <div style="font-size:12px; font-weight:600;">Flood: ${(floodScore*100).toFixed(1)}% &nbsp;|&nbsp; LS: ${(lsScore*100).toFixed(1)}%</div>
                    </div>
                    <div style="font-size:11px; color:#94a3b8; background:rgba(0,0,0,0.4); padding:8px; border-radius:4px; border: 1px solid rgba(255,255,255,0.05);">
                        <b style="color: #e2e8f0; display: block; margin-bottom: 6px;">🛰️ Live Extracted Features</b>
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 3px 10px;">
                            <div>Elevation</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${(t.elevation || 0).toFixed(1)}m</div>
                            <div>Slope</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${(t.slope || 0).toFixed(1)}°</div>
                            <div>TRI</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${(t.tri || 0).toFixed(2)}</div>
                            <div>TWI</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${(t.twi || 0).toFixed(2)}</div>
                            <div>River Dist</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${((t.dist_to_river_m || 3000)/1000).toFixed(1)}km</div>
                            <div>Precip/day</div><div style="text-align:right;font-weight:600;color:#e2e8f0;">${(t.precip_daily_mm || 0).toFixed(1)}mm</div>
                        </div>
                    </div>
                    <button onclick="event.stopPropagation(); openGroundSurveyForm();" style="margin-top:12px; width:100%; padding:8px; background:rgba(20, 184, 166, 0.2); border:1px solid #14b8a6; color:#5eead4; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px; transition:all 0.2s;">
                        ➕ Add to Monitoring Grid
                    </button>
                </div>
            `);
            
            // Store globally so the button can access it
            window.__currentGroundSurveyData = { lat, lng, t, popupId };
        } else {
            popup.setContent(`<div style="color:#ef4444; font-family:'Inter', sans-serif; padding:8px;">${data.message || 'Error scoring this point'}</div>`);
        }
    } catch (err) {
        popup.setContent(`<div style="color:#ef4444; font-family:'Inter', sans-serif; padding:8px;">API Error: ${err.message}</div>`);
    }
});

