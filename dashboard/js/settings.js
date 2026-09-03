let currentSettings = null;

function openSettingsModal() {
  document.getElementById('settings-modal').style.display = 'flex';
  fetchSettings();
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

async function fetchSettings() {
  const formDiv = document.getElementById('settings-form');
  formDiv.innerHTML = '<div style="text-align: center; color: var(--text-dim);">Loading settings...</div>';
  
  try {
    const res = await fetch('http://127.0.0.1:8000/settings/');
    const data = await res.json();
    currentSettings = data.current; // the backend wraps it in {current, defaults, _description}
    renderSettingsForm();
  } catch (err) {
    formDiv.innerHTML = `<div style="color: var(--danger);">Failed to load settings: ${err.message}</div>`;
  }
}

function renderSettingsForm() {
  if (!currentSettings) return;
  const formDiv = document.getElementById('settings-form');
  
  let html = '';
  
  // Helper to build an input row
  const buildInput = (path, label, value, tooltip, step=0.1) => {
    return `
      <div style="margin-bottom: 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <label style="font-size:13px; font-weight:600; color:var(--text);">${label}</label>
          <div class="tooltip" style="cursor:help; background:var(--accent); color:white; border-radius:50%; width:16px; height:16px; display:inline-flex; align-items:center; justify-content:center; font-size:10px; font-weight:bold; position:relative;" title="${tooltip}">i</div>
        </div>
        <input type="number" step="${step}" id="${path}" value="${value}" style="width:100%; padding:8px; border-radius:4px; border:1px solid rgba(255,255,255,0.2); background:rgba(0,0,0,0.3); color:white; font-family:'Inter', sans-serif;">
      </div>
    `;
  };

  html += `<h4 style="color:var(--accent); margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:4px;">Cascading Hazards</h4>`;
  html += buildInput('cascading_hazards.cascading_multiplier', 'Cascading Risk Multiplier', currentSettings.cascading_hazards.cascading_multiplier, 'Amplifies landslide risk when soil is saturated by severe flooding (Physics/Geotech modeling).', 0.1);
  html += buildInput('cascading_hazards.adjacency_buffer_m', 'Adjacency Buffer (meters)', currentSettings.cascading_hazards.adjacency_buffer_m, 'Distance in meters to check if a landslide zone is affected by nearby flood waters (Groundwater seepage).', 10);

  html += `<h4 style="color:var(--accent); margin-top:24px; margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:4px;">Sphere Standards (Logistics)</h4>`;
  html += buildInput('sphere_standards.m2_per_person', 'Area Per Person (m²)', currentSettings.sphere_standards.m2_per_person, 'UNHCR minimum emergency standard for camp surface area. Default is 3.5m².', 0.5);
  html += buildInput('sphere_standards.max_slope_deg', 'Max Terrain Slope (°)', currentSettings.sphere_standards.max_slope_deg, 'Maximum allowable incline for setting up relief camps safely. (>8° introduces runoff/mudslide risk).', 1);
  html += buildInput('sphere_standards.water_litres_per_person', 'Daily Water Required (L)', currentSettings.sphere_standards.water_litres_per_person, 'Litres of water required per person per day (WASH standard).', 1);

  html += `<h4 style="color:var(--accent); margin-top:24px; margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:4px;">Multi-Hazard Risk Fusion</h4>`;
  html += buildInput('risk_fusion.damage_weight', 'Structural Damage Weight', currentSettings.risk_fusion.damage_weight, 'AHP Weight applied to structural damage when calculating total fused risk.', 0.05);
  html += buildInput('risk_fusion.flood_weight', 'Flood Extent Weight', currentSettings.risk_fusion.flood_weight, 'AHP Weight applied to flood inundation extent.', 0.05);
  html += buildInput('risk_fusion.landslide_weight', 'Landslide Weight', currentSettings.risk_fusion.landslide_weight, 'AHP Weight applied to landslide hazard zones.', 0.05);

  formDiv.innerHTML = html;
}

async function saveSettings() {
  if (!currentSettings) return;
  
  // Helper to read back the values
  const getVal = (path) => parseFloat(document.getElementById(path).value);
  
  currentSettings.cascading_hazards.cascading_multiplier = getVal('cascading_hazards.cascading_multiplier');
  currentSettings.cascading_hazards.adjacency_buffer_m = getVal('cascading_hazards.adjacency_buffer_m');
  
  currentSettings.sphere_standards.m2_per_person = getVal('sphere_standards.m2_per_person');
  currentSettings.sphere_standards.max_slope_deg = getVal('sphere_standards.max_slope_deg');
  currentSettings.sphere_standards.water_litres_per_person = getVal('sphere_standards.water_litres_per_person');
  
  currentSettings.risk_fusion.damage_weight = getVal('risk_fusion.damage_weight');
  currentSettings.risk_fusion.flood_weight = getVal('risk_fusion.flood_weight');
  currentSettings.risk_fusion.landslide_weight = getVal('risk_fusion.landslide_weight');

  try {
    const res = await fetch('http://127.0.0.1:8000/settings/', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(currentSettings)
    });
    
    if (res.ok) {
      closeSettingsModal();
      // Inform the user and reload the map to reflect changes
      const banner = document.getElementById('alert-banner');
      banner.innerHTML = '✅ Configuration saved successfully! Live pipeline recalibrated.';
      banner.style.backgroundColor = 'var(--success)';
      banner.style.display = 'block';
      setTimeout(() => { banner.style.display = 'none'; banner.style.backgroundColor = 'rgba(239, 68, 68, 0.9)'; }, 3000);
      
      // Re-trigger the radar sweep to fetch new data
      if (typeof performRadarSweep === 'function') {
        performRadarSweep();
      }
    } else {
      alert("Failed to save settings: " + await res.text());
    }
  } catch (err) {
    alert("Error saving settings: " + err.message);
  }
}
