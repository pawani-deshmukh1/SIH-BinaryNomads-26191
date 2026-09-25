// weather.js - Handles the simulated weather escalation

let isSimulating = false;

function updateWeatherUI(rainNow, rain72h, multiplier) {
  const curEl = document.getElementById('weather-current');
  const forEl = document.getElementById('weather-forecast');
  const multEl = document.getElementById('weather-mult');
  
  if (curEl) curEl.textContent = rainNow.toFixed(1) + ' mm/hr';
  if (forEl) forEl.textContent = rain72h.toFixed(1) + ' mm';
  if (multEl) {
    multEl.textContent = multiplier.toFixed(1) + 'x';
    if (multiplier > 1.2) {
      multEl.style.color = 'var(--red)';
    } else {
      multEl.style.color = 'var(--accent)';
    }
  }
}

async function simulateMonsoon() {
  if (isSimulating) return;
  isSimulating = true;
  
  const btn = document.getElementById('btn-sim-rain');
  btn.textContent = 'Simulating...';
  btn.style.opacity = '0.7';
  btn.style.pointerEvents = 'none';

  // 1. Update weather UI immediately to show the "forecast" spiked
  updateWeatherUI(15.5, 210.4, 3.0);
  
  // 2. Fetch the real fused risk for vulnerable habitations from the backend
  const promises = [];
  
  currentHabitations.forEach(hab => {
      // Only escalate the ones that already have some base risk to save time
      if (hab.zone === 'ORANGE' || hab.zone === 'YELLOW' || hab.zone === 'RED') {
          const p = fetch(`${window.API_BASE}/live-risk/?lat=${hab.lat}&lng=${hab.lng}&habitation_id=${hab.id}&simulate_weather=true`)
              .then(r => r.json())
              .then(data => {
                  if (data.status === 'success') {
                      hab.zone = data.fusion.final_zone;
                      
                      // Visually update the marker on the map immediately
                      if (mapMarkers[hab.id]) {
                          mapMarkers[hab.id].setStyle({
                              fillColor: ZONE_COLORS[hab.zone],
                              radius: hab.zone === 'RED' ? 10 : 8
                          });
                          
                          if (hab.zone === 'RED') {
                              mapMarkers[hab.id].getElement()?.classList.add('marker-pulse-RED');
                              mapMarkers[hab.id].getElement()?.classList.remove('marker-glow-ORANGE');
                          } else if (hab.zone === 'ORANGE') {
                              mapMarkers[hab.id].getElement()?.classList.add('marker-glow-ORANGE');
                          }
                      }
                  }
              }).catch(e => console.error(e));
          promises.push(p);
      }
  });

  Promise.all(promises).then(() => {
      // Re-render sidebar list with new zones
      renderHabitations();
      updateSidebarCounts();
      
      // Trigger the visual map animation
      if (window.triggerInundationSpread) {
        window.triggerInundationSpread(3.0);
      }
      
      // Wait until animation finishes before showing banner
      setTimeout(() => {
        showBanner("🔴 CLOUDBURST DETECTED: Triggering Cascading Risk Protocol & Comms Offline. Cell towers at risk.");
      }, 4500);
      
      setTimeout(() => {
        // reset
        btn.textContent = 'Simulate Heavy Rain';
        btn.style.opacity = '1';
        btn.style.pointerEvents = 'auto';
        isSimulating = false;
      }, 10000); // stay simulated for 10s then user can click again
  });
}

function showBanner(msg) {
  const banner = document.getElementById('alert-banner');
  banner.textContent = msg;
  banner.classList.add('show');
  setTimeout(() => {
    banner.classList.remove('show');
  }, 7000);
}

// -- LAYER B MODAL LOGIC --

function openLayerBModal() {
  const modal = document.getElementById('layer-b-modal');
  modal.style.display = 'flex';
  
  const listEl = document.getElementById('layer-b-list');
  listEl.innerHTML = '<div style="text-align: center; color: var(--text-dim);">Loading regional telemetry...</div>';
  
  const urlParams = new URLSearchParams(window.location.search);
  const region = urlParams.get('region') || 'assam';
  
  fetch(`${window.API_BASE}/weather-grid/?region=${region}`)
    .then(res => res.json())
    .then(data => {
      listEl.innerHTML = '';
      if (!data.features || data.features.length === 0) {
        listEl.innerHTML = '<div style="text-align: center; color: var(--text-dim);">No telemetry data available.</div>';
        return;
      }
      
      let html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
      
      // Sort: Danger areas first, then clear
      const sortedFeatures = data.features.sort((a, b) => {
        if (a.properties.alert_level !== 'clear' && b.properties.alert_level === 'clear') return -1;
        if (a.properties.alert_level === 'clear' && b.properties.alert_level !== 'clear') return 1;
        return b.properties.rain_24h_mm - a.properties.rain_24h_mm;
      });
      
      sortedFeatures.forEach(cell => {
        const p = cell.properties;
        const isDanger = p.alert_level !== 'clear';
        const textColor = isDanger ? 'var(--red)' : 'var(--text)';
        const bg = isDanger ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.05)';
        const border = isDanger ? '1px solid var(--red)' : '1px solid var(--border)';
        const icon = isDanger ? (p.alert_level === 'cyclonic' ? '🌀' : (p.alert_level === 'cloudburst' ? '⛈️' : '🌧️')) : '🌤️';
        const name = p.name || 'Unknown Area';
        
        html += `
          <div style="padding: 12px; border-radius: 6px; background: ${bg}; border: ${border}; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: bold; color: ${textColor};">${icon} ${name}</div>
              <div style="font-size: 11px; color: var(--text-dim); margin-top: 4px;">Status: ${p.alert_level.toUpperCase()}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-weight: bold; color: ${textColor};">${p.rain_24h_mm.toFixed(1)} mm/24h</div>
              <div style="font-size: 11px; color: var(--text-dim); margin-top: 4px;">Wind: ${p.wind_speed_kmh} km/h</div>
            </div>
          </div>
        `;
      });
      html += '</div>';
      listEl.innerHTML = html;
    })
    .catch(err => {
      listEl.innerHTML = '<div style="text-align: center; color: var(--red);">Failed to load telemetry.</div>';
      console.error(err);
    });
}

function closeLayerBModal() {
  document.getElementById('layer-b-modal').style.display = 'none';
}
