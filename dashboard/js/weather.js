// weather.js - Handles the simulated weather escalation

let isSimulating = false;

function updateWeatherUI(rainNow, rain72h, multiplier) {
  document.getElementById('weather-current').textContent = rainNow.toFixed(1) + ' mm/hr';
  document.getElementById('weather-forecast').textContent = rain72h.toFixed(1) + ' mm';
  document.getElementById('weather-mult').textContent = multiplier.toFixed(1) + 'x';
  
  const multEl = document.getElementById('weather-mult');
  if (multiplier > 1.2) {
    multEl.style.color = 'var(--red)';
  } else {
    multEl.style.color = 'var(--accent)';
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
  updateWeatherUI(15.5, 210.4, 1.8);
  
  // 2. Fetch the map data again but with the multiplier forced to 1.8
  // Since we don't have a direct multiplier override in the backend /susceptibility/zone-map,
  // we'll just mock the response on the frontend by manually escalating the ORANGE to RED 
  // and YELLOW to ORANGE for the demo to show the UI reacting.
  
  setTimeout(() => {
    // trigger the visual map animation passing in the multiplier
    if (window.triggerInundationSpread) {
      window.triggerInundationSpread(1.8);
    }
    
    // Wait until animation finishes before showing banner
    setTimeout(() => {
      showBanner("⚠️ Critical: 72h forecast crossed 200mm. Zones escalated.");
    }, 4500);
    
    setTimeout(() => {
      // reset
      btn.textContent = 'Simulate Heavy Rain';
      btn.style.opacity = '1';
      btn.style.pointerEvents = 'auto';
      isSimulating = false;
    }, 10000); // stay simulated for 10s then user can click again
    
  }, 1000);
}

function showBanner(msg) {
  const banner = document.getElementById('alert-banner');
  banner.textContent = msg;
  banner.classList.add('show');
  setTimeout(() => {
    banner.classList.remove('show');
  }, 5000);
}
