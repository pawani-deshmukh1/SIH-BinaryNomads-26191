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
let commsLayerActive = false;

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
    // 1. Fetch the Susceptibility Zone Map
    const res = await fetch('http://127.0.0.1:8000/susceptibility/zone-map');
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
    await fetchTowers();
    
    // 4. Render everything
    renderHabitations();
    updateSidebarCounts();
    
    // Auto-fit bounds
    if (currentHabitations.length > 0) {
      const bounds = L.latLngBounds(currentHabitations.map(h => [h.lat, h.lng]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 11 });
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
    const res = await fetch('http://127.0.0.1:8000/advisory/safe-zones');
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

async function fetchTowers() {
  try {
    const res = await fetch('http://127.0.0.1:8000/towers/');
    if (!res.ok) return;
    const data = await res.json();
    
    data.features.forEach(tower => {
      const isAtRisk = tower.properties.status === 'at_risk';
      const color = isAtRisk ? '#f97316' : '#94a3b8';
      
      const marker = L.circleMarker([tower.geometry.coordinates[1], tower.geometry.coordinates[0]], {
        radius: 6,
        fillColor: color,
        color: '#ffffff',
        weight: 2,
        fillOpacity: 0.9,
      });
      
      if (isAtRisk) {
        marker.getElement()?.classList.add('marker-pulse-ORANGE');
      }
      
      marker.bindPopup(`<strong>🗼 Cell Tower</strong><br>${tower.properties.name}<br>Status: ${isAtRisk ? '⚠️ AT RISK' : '✅ Operational'}`);
      towerMarkers.push({ marker, isAtRisk });
    });
    
    document.getElementById('layer-comms')?.addEventListener('click', toggleCommsLayer);
  } catch(err) {
    console.error("Could not load towers:", err);
  }
}

function toggleCommsLayer() {
  commsLayerActive = !commsLayerActive;
  const btn = document.getElementById('layer-comms');
  
  if (commsLayerActive) {
    btn.style.background = 'var(--orange)';
    btn.style.color = 'black';
    towerMarkers.forEach(t => t.marker.addTo(map));
  } else {
    btn.style.background = 'rgba(15,23,42,0.9)';
    btn.style.color = 'white';
    towerMarkers.forEach(t => map.removeLayer(t.marker));
  }
}

function renderHabitations() {
  const listEl = document.getElementById('hab-list');
  listEl.innerHTML = '';
  
  // Sort by risk (RED first, then ORANGE, etc), then by vulnerability descending
  const sortOrder = { 'RED': 1, 'ORANGE': 2, 'YELLOW': 3, 'GREEN': 4 };
  currentHabitations.sort((a, b) => {
    if (sortOrder[a.zone] !== sortOrder[b.zone]) {
      return sortOrder[a.zone] - sortOrder[b.zone];
    }
    return b.vulnerability - a.vulnerability;
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
    }).addTo(map);
    
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
    
    card.innerHTML = `
      <div class="hab-info">
        <h4>${getIconForType(hab.type)} ${hab.name}</h4>
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
    
    listEl.appendChild(card);
  });
}

function updateSidebarCounts() {
  const counts = { RED: 0, ORANGE: 0, YELLOW: 0 };
  currentHabitations.forEach(h => {
    if (counts[h.zone] !== undefined) counts[h.zone]++;
  });
  
  document.getElementById('count-red').textContent = counts.RED;
  document.getElementById('count-orange').textContent = counts.ORANGE;
  document.getElementById('count-yellow').textContent = counts.YELLOW;
}

// Remove escalateMapZones entirely, as we do it in triggerInundationSpread

// Start the dashboard
initDashboard();


