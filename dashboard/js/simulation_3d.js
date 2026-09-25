// Cesium token will be fetched from the backend config

let viewer;
let simulationData;
let habitationsData = [];
let allDataSources = [];
let isHabitationSubmerged = false;
let hydrographChart = null;

document.addEventListener('DOMContentLoaded', async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const habId = urlParams.get('hab_id');
  if (!habId) {
    alert("No habitation ID provided.");
    return;
  }

  try {
    document.getElementById('sim-loader-text').innerText = "Fetching Secure Config...";
    const configRes = await fetch(window.API_BASE + '/api/config');
    const config = await configRes.json();
    Cesium.Ion.defaultAccessToken = config.CESIUM_ION_TOKEN;

    document.getElementById('sim-loader-text').innerText = "Running Bathtub Simulation Engine...";

    const res = await fetch(`${window.API_BASE}/simulation/${habId}`);
    if (!res.ok) throw new Error("Simulation endpoint failed.");
    simulationData = await res.json();

    // Update UI Panels — clean name encoding
    const cleanName = (simulationData.habitation_name || '');
    document.getElementById('sim-hab-name').innerText = cleanName;
    document.getElementById('sim-hab-id').innerText = simulationData.habitation_id;
    document.getElementById('sim-rain-current').innerText = simulationData.trigger.current_rain_mm_hr.toFixed(1);
    document.getElementById('sim-rain-72h').innerText = simulationData.trigger.forecast_72h_mm.toFixed(1);
    document.getElementById('sim-trigger-status').innerText = simulationData.trigger.trigger_status;
    document.getElementById('sim-risk-multiplier').innerText = simulationData.trigger.risk_multiplier + "x";

    const triggerStatusEl = document.getElementById('sim-trigger-status');
    if (simulationData.trigger.trigger_status === 'CRITICAL') triggerStatusEl.style.backgroundColor = 'var(--danger)';
    else if (simulationData.trigger.trigger_status === 'ESCALATING') triggerStatusEl.style.backgroundColor = 'var(--warning)';

    document.getElementById('sim-loader-text').innerText = "Loading 3D Terrain...";
    await initCesiumViewer(simulationData);

    document.getElementById('sim-loader').style.display = 'none';

    // Enable the tour button now that Cesium has fully loaded
    const tourBtn = document.getElementById('sim-tour-btn');
    if (tourBtn) {
      tourBtn.disabled = false;
      tourBtn.style.cssText = 'padding: 6px 12px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: white; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 8px;';
      tourBtn.innerText = '🎓 Guided Tour';
      tourBtn.title = '';
    }

  } catch (e) {
    console.error(e);
    document.getElementById('sim-loader-text').innerText = "Error: " + e.message;
  }
});

async function initCesiumViewer(data) {
  // Restore original working terrain (Ion world terrain with 3D elevation)
  // Now that we have a valid token, this will work perfectly.
  const terrainProvider = await Cesium.createWorldTerrainAsync();

  viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider: terrainProvider,
    timeline: true,
    animation: true,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    infoBox: false
  });

  // Initialize Chart.js Hydrograph
  const ctx = document.getElementById('hydrographChart');
  if (ctx && data.stages) {
    const labels = data.stages.map(s => s.stage_label);
    const dataPoints = data.stages.map(s => s.water_level_m);
    
    hydrographChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Water Level (m)',
          data: dataPoints,
          borderColor: '#60a5fa',
          backgroundColor: 'rgba(96, 165, 250, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#1d4ed8',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#94a3b8', font: {family: 'Inter', size: 10} }, grid: { color: '#334155' } },
          y: { ticks: { color: '#94a3b8', font: {family: 'Inter', size: 10} }, grid: { color: '#334155' }, beginAtZero: true }
        }
      }
    });
  }

  // Disable day/night sun lighting
  viewer.scene.globe.enableLighting = false;
  // Enable depth testing so water clips against terrain properly
  viewer.scene.globe.depthTestAgainstTerrain = true;

  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      credit: 'ESRI World Imagery'
    })
  );

  const start = Cesium.JulianDate.fromIso8601('2026-09-04T06:00:00Z');
  const stop = Cesium.JulianDate.addHours(start, 36, new Cesium.JulianDate());
  viewer.clock.startTime = start.clone();
  viewer.clock.stopTime = stop.clone();
  viewer.clock.currentTime = start.clone();
  viewer.clock.clockRange = Cesium.ClockRange.CLAMPED;
  viewer.clock.multiplier = 600;
  viewer.timeline.zoomTo(start, stop);

  // Load the max flood stage (T+36) as our basin boundary
  const maxStage = data.stages[data.stages.length - 1];
  let floodEntity = null;
  
  if (maxStage && maxStage.geojson && maxStage.geojson.features.length > 0) {
    const baseElev = maxStage.geojson.features[0].properties.base_elevation_m || 40; // Default if missing
    
    // Animate extrudedHeight based on time
    const getWaterLevel = (time) => {
      const hours = Cesium.JulianDate.secondsDifference(time, start) / 3600;
      let level = 0;
      for (let i = 0; i < data.stages.length - 1; i++) {
        const s1 = data.stages[i];
        const s2 = data.stages[i+1];
        if (hours >= s1.t_plus_hours && hours <= s2.t_plus_hours) {
          const t = (hours - s1.t_plus_hours) / (s2.t_plus_hours - s1.t_plus_hours);
          level = s1.water_level_m + t * (s2.water_level_m - s1.water_level_m);
          break;
        }
      }
      if (hours >= data.stages[data.stages.length-1].t_plus_hours) {
        level = data.stages[data.stages.length-1].water_level_m;
      }
      return level;
    };
    
    const getColor = (time) => {
      const hours = Cesium.JulianDate.secondsDifference(time, start) / 3600;
      let c1, c2, t = 0;
      
      const colors = [
        Cesium.Color.fromCssColorString('#bfdbfe').withAlpha(0.55),
        Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.65),
        Cesium.Color.fromCssColorString('#1d4ed8').withAlpha(0.75),
        Cesium.Color.fromCssColorString('#7f1d1d').withAlpha(0.85)
      ];
      
      for (let i = 0; i < data.stages.length - 1; i++) {
        const s1 = data.stages[i];
        const s2 = data.stages[i+1];
        if (hours >= s1.t_plus_hours && hours <= s2.t_plus_hours) {
          t = (hours - s1.t_plus_hours) / (s2.t_plus_hours - s1.t_plus_hours);
          c1 = colors[i];
          c2 = colors[i+1];
          break;
        }
      }
      if (!c1) return colors[3];
      return Cesium.Color.lerp(c1, c2, t, new Cesium.Color());
    };

    const ds = await Cesium.GeoJsonDataSource.load(maxStage.geojson, {
      stroke: Cesium.Color.TRANSPARENT,
      fill: Cesium.Color.TRANSPARENT,
      clampToGround: false
    });

    ds.entities.values.forEach(entity => {
      if (entity.polygon) {
        entity.polygon.height = baseElev - 10; // extend below river bed
        entity.polygon.perPositionHeight = false;
        
        entity.polygon.extrudedHeight = new Cesium.CallbackProperty((time) => {
          // Add a subtle wave/pulsing effect by modifying height slightly based on time
          const tSeconds = Cesium.JulianDate.secondsDifference(time, start);
          const wave = Math.sin(tSeconds / 2.0) * 0.5; // +/- 0.5m wave
          return baseElev + getWaterLevel(time) + wave;
        }, false);
        
        entity.polygon.material = new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty((time) => {
          return getColor(time);
        }, false));
      }
    });
    
    viewer.dataSources.add(ds);
    floodEntity = ds;
  }

  // Load Landslide Cone Stages - volumetric flow
  if (data.landslide_cone && data.landslide_cone.stages) {
    for (let i = 0; i < data.landslide_cone.stages.length; i++) {
      const stage = data.landslide_cone.stages[i];
      if (!stage.cone_geojson) continue;

      const stageStart = Cesium.JulianDate.addHours(start, stage.t_plus_hours, new Cesium.JulianDate());

      const ds = await Cesium.GeoJsonDataSource.load(stage.cone_geojson, {
        stroke: Cesium.Color.RED.withAlpha(0.8),
        strokeWidth: 3,
        clampToGround: false,
      });

      // Extrude into a volumetric flow
      ds.entities.values.forEach(entity => {
        if (entity.polygon) {
           entity.polygon.heightReference = Cesium.HeightReference.RELATIVE_TO_GROUND;
           entity.polygon.extrudedHeightReference = Cesium.HeightReference.RELATIVE_TO_GROUND;
           entity.polygon.height = 0;
           entity.polygon.extrudedHeight = 15;
           entity.polygon.material = Cesium.Color.ORANGERED.withAlpha(0.4 + (i * 0.1));
           entity.polyline = {
               positions: entity.polygon.hierarchy.getValue().positions,
               width: 3,
               material: new Cesium.PolylineDashMaterialProperty({
                   color: Cesium.Color.RED,
                   dashLength: 20
               }),
               clampToGround: true
           };
        }
      });

      ds.show = false;
      ds._stageStart = stageStart;
      ds._stageLabel = "Landslide " + stage.t_plus_hours + "h";
      ds._stageIndex = i;
      ds._type = 'landslide';

      viewer.dataSources.add(ds);
      allDataSources.push(ds);
    }
  }

  // Add Epicenter Habitation Marker
  const centerLng = data.landslide_cone.epicenter[1];
  const centerLat = data.landslide_cone.epicenter[0];
  const epicenterEntity = viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(centerLng, centerLat),
    point: {
      pixelSize: 14,
      color: Cesium.Color.LIME,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
    },
    label: {
      text: data.habitation_name,
      font: '14pt Inter',
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      outlineWidth: 2,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -15),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
    }
  });

  // Tick handler: Update UI & Landslide visibility
  let currentFloodIndex = -1;
  let activeStages = new Set();
  let flyInProgress = false;
  
  viewer.clock.onTick.addEventListener(async (clock) => {
    const hoursElapsed = Cesium.JulianDate.secondsDifference(clock.currentTime, start) / 3600;
    
    // Landslide accumulates normally
    allDataSources.forEach((ds) => {
      if (ds._type === 'landslide' && ds._stageStart) {
        const shouldShow = Cesium.JulianDate.greaterThanOrEquals(clock.currentTime, ds._stageStart);
        if (shouldShow && !ds.show) ds.show = true;
        else if (!shouldShow && ds.show) ds.show = false;
      }
    });

    let latestFloodIndex = -1;
    for (let i = data.stages.length - 1; i >= 0; i--) {
       if (hoursElapsed >= data.stages[i].t_plus_hours) {
           latestFloodIndex = i;
           break;
       }
    }

    // Reset state if rewound to beginning
    if (latestFloodIndex === -1 && currentFloodIndex !== -1) {
      isHabitationSubmerged = false;
      epicenterEntity.point.color = Cesium.Color.LIME;
      document.getElementById('sim-advisory-log').innerHTML =
        '<li class="empty-log">Simulation standing by. Awaiting clock start.</li>';
    }

    // Point-in-polygon advisory check
    if (latestFloodIndex >= 0 && !isHabitationSubmerged) {
      checkInundation(centerLat, centerLng, latestFloodIndex, epicenterEntity, data.habitation_id);
    }

    // Update Hydrograph Chart
    if (hydrographChart && latestFloodIndex >= 0) {
      hydrographChart.data.datasets[0].pointBackgroundColor = data.stages.map((_, i) => i === latestFloodIndex ? '#ef4444' : '#1d4ed8');
      hydrographChart.data.datasets[0].pointRadius = data.stages.map((_, i) => i === latestFloodIndex ? 6 : 4);
      hydrographChart.update('none');
    }
    
    // Handle stage transitions — compare BEFORE updating currentFloodIndex
    if (latestFloodIndex !== currentFloodIndex) {
        currentFloodIndex = latestFloodIndex;

        if (latestFloodIndex >= 0) {
            // Highlight the active stage in the legend
            document.querySelectorAll('.stage-item').forEach(el => el.style.opacity = '0.5');
            const el = document.getElementById(ifIdx(latestFloodIndex));
            if (el) el.style.opacity = '1';
            
            // Camera Fly-to Choreography: pull back as disaster grows
            if (!flyInProgress) {
                flyInProgress = true;
                let dist = 5000;
                if (latestFloodIndex === 1) dist = 8000;
                if (latestFloodIndex === 2) dist = 15000;
                if (latestFloodIndex === 3) dist = 25000;
                
                viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromDegrees(centerLng, centerLat, dist),
                    orientation: {
                        heading: Cesium.Math.toRadians(0.0),
                        pitch: Cesium.Math.toRadians(-35.0),
                    },
                    duration: 2.5,
                    complete: () => { flyInProgress = false; }
                });
            }
        }
    }
  });
  viewer.clock.shouldAnimate = true;

  // Fly to target
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(centerLng, centerLat, 15000),
    orientation: {
      heading: Cesium.Math.toRadians(0.0),
      pitch: Cesium.Math.toRadians(-45.0),
    },
    duration: 3
  });
}

function ifIdx(idx) {
  if (idx === 0) return 'stage-0';
  if (idx === 1) return 'stage-6';
  if (idx === 2) return 'stage-18';
  if (idx === 3) return 'stage-36';
}

// ── Instant time-jump: clicking a stage legend item teleports the clock ──
function jumpToStage(tPlusHours) {
  if (!viewer) return;
  const start = viewer.clock.startTime;
  const target = Cesium.JulianDate.addHours(start, tPlusHours, new Cesium.JulianDate());
  viewer.clock.currentTime = target.clone();
  // Pause so the user can inspect that exact moment
  viewer.clock.shouldAnimate = false;
  // Flash the clicked stage item
  document.querySelectorAll('.stage-item').forEach(el => el.classList.remove('stage-active'));
  const stageMap = {0: 'stage-0', 6: 'stage-6', 18: 'stage-18', 36: 'stage-36'};
  const el = document.getElementById(stageMap[tPlusHours]);
  if (el) el.classList.add('stage-active');
  // Auto-resume after 2s so the simulation can continue
  setTimeout(() => { if (viewer) viewer.clock.shouldAnimate = true; }, 2000);
}

function checkInundation(lat, lng, stageIndex, entity, habId) {
  const pt = turf.point([lng, lat]);
  let isSubmerged = false;

  const stageData = simulationData.stages[stageIndex];
  if (stageData && stageData.geojson && stageData.geojson.features.length > 0) {
    const poly = stageData.geojson.features[0];
    try { if (turf.booleanPointInPolygon(pt, poly)) isSubmerged = true; } catch (e) { }
  }

  const lsStageData = simulationData.landslide_cone.stages[stageIndex];
  if (lsStageData && lsStageData.cone_geojson && lsStageData.cone_geojson.features.length > 0) {
    const lsPoly = lsStageData.cone_geojson.features[0];
    try { if (turf.booleanPointInPolygon(pt, lsPoly)) isSubmerged = true; } catch (e) { }
  }
  if (isSubmerged) {
    isHabitationSubmerged = true;
    entity.point.color = Cesium.Color.RED;

    // Derive the label from stageIndex
    const stageLabel = simulationData.stages[stageIndex]
      ? simulationData.stages[stageIndex].stage_label
      : `Stage ${stageIndex}`;

    // Trigger Dramatic FLOOD ALERT Overlay
    const alertOverlay = document.getElementById('sim-alert-overlay');
    if (alertOverlay) {
      document.getElementById('sim-alert-time').innerText = "AT " + stageLabel.toUpperCase();
      alertOverlay.style.display = 'flex';
      void alertOverlay.offsetWidth; // Force reflow
      alertOverlay.style.opacity = '1';
      setTimeout(() => {
        alertOverlay.style.opacity = '0';
        setTimeout(() => alertOverlay.style.display = 'none', 300);
      }, 2000);
    }

    const ul = document.getElementById('sim-advisory-log');
    const emptyLog = ul.querySelector('.empty-log');
    if (emptyLog) emptyLog.remove();

    const li = document.createElement('li');
    li.innerHTML = `<strong>${stageLabel}</strong>: ${simulationData.habitation_name} breached! Triggering Evacuation Advisory...`;
    li.style.color = "var(--danger)";
    ul.appendChild(li);

    fetch(window.API_BASE + '/advisory/' + habId).then(r => r.json()).then(res => {
      const plan = res?.advisory?.relocation_plan;
      const site = plan?.recommended_site;
      const hostOptions = res?.advisory?.host_community_options || [];
      
      let approved = true;
      if (site && site.is_overflow) {
          approved = confirm(`[HUMAN-IN-THE-LOOP AUTHORIZATION]\n\nThe primary safe zone has exceeded Sphere Standards capacity.\nDynamic Optimization Engine suggests re-routing to: ${site.name}.\n\nApprove this dynamic re-routing?`);
      }

      const li2 = document.createElement('li');
      if (!approved) {
          li2.innerHTML = `❌ Dynamic Re-routing Rejected by Commander. Awaiting manual override.`;
          li2.style.color = "var(--orange)";
          ul.appendChild(li2);
          return;
      }

      const siteName = site?.name || 'N/A';
      const siteDistrict = site?.district ? ', ' + site.district : '';
      li2.innerHTML = `✅ Relocate to: <strong>${siteName}${siteDistrict}</strong>`;
      ul.appendChild(li2);

      if (hostOptions.length > 0) {
          const li3 = document.createElement('li');
          li3.innerHTML = `✅ Option B Available: <strong>${hostOptions.length} Host Communities</strong> (Split routing)`;
          li3.style.color = "var(--success)";
          ul.appendChild(li3);
      }

      // Helper function to draw a route in Cesium from geojson and animate a vehicle
      const drawCesiumRoute = (routeGeojson, baseColorHex, kachaColorHex, addVehicle = false) => {
          if (!routeGeojson || !routeGeojson.features) return;
          
          let allPositions = [];
          
          routeGeojson.features.forEach(feat => {
              let flatCoords = [];
              if (!feat.geometry || !feat.geometry.coordinates) return;
              feat.geometry.coordinates.forEach(c => { 
                  flatCoords.push(c[0]); flatCoords.push(c[1]); 
                  allPositions.push(Cesium.Cartesian3.fromDegrees(c[0], c[1]));
              });
              
              let color = Cesium.Color.fromCssColorString(baseColorHex);
              let dashLen = 0;
              if (feat.properties.segment_type === 'kacha_way') {
                  color = Cesium.Color.fromCssColorString(kachaColorHex);
                  dashLen = 20.0;
              } else if (feat.properties.segment_type === 'blocked' || ['ERROR', 'ISOLATED', 'BLOCKED'].includes(feat.properties.route_status)) {
                  color = Cesium.Color.RED;
              }
              
              const material = dashLen > 0 
                  ? new Cesium.PolylineDashMaterialProperty({ color: color, dashLength: dashLen })
                  : color;
                  
              viewer.entities.add({
                  polyline: {
                      positions: Cesium.Cartesian3.fromDegreesArray(flatCoords),
                      width: feat.properties.segment_type === 'kacha_way' ? 4 : 8,
                      material: new Cesium.PolylineGlowMaterialProperty({
                          glowPower: 0.2,
                          color: color
                      }),
                      clampToGround: true
                  }
              });
          });
          
          if (addVehicle && allPositions.length > 1) {
              const positionProperty = new Cesium.SampledPositionProperty();
              // Animate vehicle over the first 6 hours of simulation
              const tripStart = start.clone();
              const tripEnd = Cesium.JulianDate.addHours(start, 6, new Cesium.JulianDate());
              
              // Simplistic constant speed allocation
              const totalNodes = allPositions.length;
              for (let i = 0; i < totalNodes; i++) {
                  const t = i / (totalNodes - 1);
                  const nodeTime = Cesium.JulianDate.addSeconds(tripStart, t * 6 * 3600, new Cesium.JulianDate());
                  positionProperty.addSample(nodeTime, allPositions[i]);
              }
              
              viewer.entities.add({
                  position: positionProperty,
                  point: {
                      pixelSize: 15,
                      color: Cesium.Color.YELLOW,
                      outlineColor: Cesium.Color.BLACK,
                      outlineWidth: 2,
                      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
                  },
                  label: {
                      text: "🚌 Evacuation Convoy",
                      font: '10pt Inter',
                      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                      pixelOffset: new Cesium.Cartesian2(0, -15),
                      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
                  }
              });
          }
      };

      // 1. Draw Formal Safe Zone (BLUE)
      if (site && site.lat && site.lng) {
         viewer.entities.add({
             position: Cesium.Cartesian3.fromDegrees(site.lng, site.lat),
             point: { pixelSize: 14, color: Cesium.Color.DODGERBLUE, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
             label: { text: "Safe Zone: " + site.name, font: '14pt Inter', style: Cesium.LabelStyle.FILL_AND_OUTLINE, verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -15) }
         });
         
         if (plan.verified_route) {
             drawCesiumRoute(plan.verified_route, '#3b82f6', '#60a5fa', true); // true = add vehicle!
         } else {
             // Fallback straight line
             viewer.entities.add({
                 polyline: {
                     positions: Cesium.Cartesian3.fromDegreesArray([lng, lat, site.lng, site.lat]),
                     width: 4, material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.DODGERBLUE, dashLength: 20 }), clampToGround: true
                 }
             });
         }
      }

      // 2. Draw Host Communities (GREEN)
      hostOptions.forEach(h => {
          if (h.lat && h.lng) {
              const splitPop = h.assigned_population || 0;
              viewer.entities.add({
                 position: Cesium.Cartesian3.fromDegrees(h.lng, h.lat),
                 point: { pixelSize: 12, color: Cesium.Color.LIME, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
                 label: { text: "Option B: " + h.name + " (" + splitPop + " pax)", font: '12pt Inter', style: Cesium.LabelStyle.FILL_AND_OUTLINE, verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -15) }
              });

              if (h.route_geojson) {
                  drawCesiumRoute(h.route_geojson, '#22c55e', '#22c55e');
              } else {
                  viewer.entities.add({
                      polyline: {
                          positions: Cesium.Cartesian3.fromDegreesArray([lng, lat, h.lng, h.lat]),
                          width: 4, material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.LIME, dashLength: 20 }), clampToGround: true
                      }
                  });
              }
          }
      });

      // Automatically zoom camera to fit origin and destination
      if (site && site.lat && site.lng) {
          const startCartesian = Cesium.Cartesian3.fromDegrees(lng, lat);
          const destCartesian = Cesium.Cartesian3.fromDegrees(site.lng, site.lat);
          const boundingSphere = Cesium.BoundingSphere.fromPoints([startCartesian, destCartesian]);
          viewer.camera.flyToBoundingSphere(boundingSphere, { duration: 3.0 });
      }
    });
  }
}


// UI Speed Controls
window.setSimSpeed = function(speed) {
  if (!viewer) return;
  viewer.clock.multiplier = 600 * speed;
  viewer.clock.shouldAnimate = true;
};

window.stepSim = function() {
  if (!viewer) return;
  const start = viewer.clock.startTime;
  const current = viewer.clock.currentTime;
  let hours = Cesium.JulianDate.secondsDifference(current, start) / 3600;
  if (hours < 6) hours = 6;
  else if (hours < 18) hours = 18;
  else if (hours < 36) hours = 36;
  else hours = 0;
  jumpToStage(hours);
};
