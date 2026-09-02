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
      lat: f.geometry.coordinates[1],
      lng: f.geometry.coordinates[0]
    }));
    
    // 2. Fetch Safe Zones (just for visualization)
    await fetchSafeZones();
    
    // 3. Render everything
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
        fillColor: '#22c55e',
        color: '#ffffff',
        weight: 2,
        fillOpacity: 0.9,
      }).addTo(map);
      
      marker.bindPopup(`<strong>★ Safe Zone</strong><br>${sz.properties.name}<br>Capacity: ${sz.properties.capacity}`);
      safeZoneMarkers.push(marker);
    });
  } catch(err) {
    console.error("Could not load safe zones:", err);
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
        <p style="font-size:11px; color:var(--red); font-weight:600; margin-top:2px;">
          ⚠ Vuln: ${hab.vulnerability}% SC/ST
        </p>
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


