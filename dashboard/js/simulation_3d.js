Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6Ijd4eTktYUF0N2FybDRhbGMiLCJqdGkiOiJhNTI3MWI5MS1jZDRkLTQ0MGItYTMzNy0yYTJiZTlhOWQwYmUiLCJpZCI6NDc5OTcyLCJpc3MiOiJodHRwczovL2FwaS5jZXNpdW0uY29tIiwiYXVkIjoidW5kZWZpbmVkX2RlZmF1bHQiLCJpYXQiOjE3ODg0NDI5ODZ9.4Aq7limiGVKqhf4hQW8KrQKY99V_NKVo4y1Oq0ooZUE';

let viewer;
let simulationData;
let habitationsData = [];
let allDataSources = [];
let isHabitationSubmerged = false;

document.addEventListener('DOMContentLoaded', async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const habId = urlParams.get('hab_id');
  if (!habId) {
    alert("No habitation ID provided.");
    return;
  }

  try {
    document.getElementById('sim-loader-text').innerText = "Running Bathtub Simulation Engine...";

    const res = await fetch(`http://127.0.0.1:8000/simulation/${habId}`);
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

  } catch(e) {
    console.error(e);
    document.getElementById('sim-loader-text').innerText = "Error: " + e.message;
  }
});

async function initCesiumViewer(data) {
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

  // Disable day/night sun lighting — always show full brightness
  viewer.scene.globe.enableLighting = false;

  // ESRI World satellite tiles (free, no license needed, great India coverage)
  // NOTE: Must be served via http:// (not file://) for CORS to work
  viewer.imageryLayers.removeAll();
  viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      credit: 'ESRI World Imagery'
    })
  );

  // Clock: force start at daytime (06:00 UTC = noon India IST)
  const start = Cesium.JulianDate.fromIso8601('2026-09-04T06:00:00Z');
  const stop  = Cesium.JulianDate.addHours(start, 36, new Cesium.JulianDate());
  viewer.clock.startTime   = start.clone();
  viewer.clock.stopTime    = stop.clone();
  viewer.clock.currentTime = start.clone();
  viewer.clock.clockRange  = Cesium.ClockRange.CLAMPED;
  viewer.clock.multiplier  = 600;
  viewer.timeline.zoomTo(start, stop);

  // Stage colors: light blue → medium blue → dark blue → red
  const stageColors = [
    Cesium.Color.DEEPSKYBLUE.withAlpha(0.45),
    Cesium.Color.DODGERBLUE.withAlpha(0.55),
    Cesium.Color.ROYALBLUE.withAlpha(0.65),
    Cesium.Color.CRIMSON.withAlpha(0.70),
  ];

  // Load Flood Stages
  for (let i = 0; i < data.stages.length; i++) {
    const stage = data.stages[i];
    if (!stage.geojson) continue;

    const stageStart = Cesium.JulianDate.addHours(start, stage.t_plus_hours, new Cesium.JulianDate());

    const ds = await Cesium.GeoJsonDataSource.load(stage.geojson, {
      fill: stageColors[i],
      stroke: Cesium.Color.WHITE.withAlpha(0.3),
      strokeWidth: 2,
      extrudedHeight: stage.water_level_m,
      clampToGround: false,
    });

    ds.show = false;
    ds._stageStart = stageStart;
    ds._stageLabel = stage.stage_label;
    ds._stageIndex = i;
    ds._type = 'flood';

    viewer.dataSources.add(ds);
    allDataSources.push(ds);
  }

  // Load Landslide Cone Stages
  if (data.landslide_cone && data.landslide_cone.stages) {
    for (let i = 0; i < data.landslide_cone.stages.length; i++) {
      const stage = data.landslide_cone.stages[i];
      if (!stage.cone_geojson) continue;

      const stageStart = Cesium.JulianDate.addHours(start, stage.t_plus_hours, new Cesium.JulianDate());

      const ds = await Cesium.GeoJsonDataSource.load(stage.cone_geojson, {
        fill: Cesium.Color.ORANGERED.withAlpha(0.3 + (i * 0.1)),
        stroke: Cesium.Color.RED.withAlpha(0.8),
        strokeWidth: 2,
        clampToGround: true,
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
      outlineWidth: 2
    },
    label: {
      text: data.habitation_name,
      font: '14pt Inter',
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      outlineWidth: 2,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -15)
    }
  });

  // ─────────────────────────────────────────────────────────────────────
  // TICK HANDLER: Show ONLY the latest active flood stage at each moment
  // This makes the flood polygon visibly GROW as each stage activates:
  //   T+0 (small polygon) → T+6 (bigger) → T+18 (bigger) → T+36 (largest)
  // ─────────────────────────────────────────────────────────────────────
  let activeStages = new Set();
  let currentFloodIndex = -1;

  viewer.clock.onTick.addEventListener(async (clock) => {
    // Find the highest flood stage that should be active right now
    let latestFloodDs = null;
    let latestFloodIndex = -1;

    allDataSources.forEach((ds) => {
      if (ds._type === 'flood' && ds._stageStart) {
        const active = Cesium.JulianDate.greaterThanOrEquals(clock.currentTime, ds._stageStart);
        if (active && ds._stageIndex > latestFloodIndex) {
          latestFloodIndex = ds._stageIndex;
          latestFloodDs = ds;
        }
      }
    });

    // Show ONLY the latest flood stage, hide all others
    let newlyRevealedFlood = false;
    allDataSources.forEach((ds) => {
      if (ds._type === 'flood') {
        const shouldShow = (ds === latestFloodDs);
        if (shouldShow && !ds.show) {
          ds.show = true;
          activeStages = new Set([ds._stageIndex]);
          newlyRevealedFlood = true;
        } else if (!shouldShow && ds.show) {
          ds.show = false;
        }
      }

      // Landslide accumulates normally (each stage stays visible)
      if (ds._type === 'landslide' && ds._stageStart) {
        const shouldShow = Cesium.JulianDate.greaterThanOrEquals(clock.currentTime, ds._stageStart);
        if (shouldShow && !ds.show) ds.show = true;
        else if (!shouldShow && ds.show) ds.show = false;
      }
    });

    // Reset state if rewound past start
    if (latestFloodIndex === -1 && currentFloodIndex !== -1) {
      isHabitationSubmerged = false;
      epicenterEntity.point.color = Cesium.Color.LIME;
      document.getElementById('sim-advisory-log').innerHTML =
        '<li class="empty-log">Simulation standing by. Awaiting clock start.</li>';
      activeStages.clear();
    }
    currentFloodIndex = latestFloodIndex;

    // Update legend highlight
    if (newlyRevealedFlood) {
      document.querySelectorAll('.stage-item').forEach(el => el.style.opacity = '0.5');
      activeStages.forEach(idx => {
        const el = document.getElementById(ifIdx(idx));
        if (el) el.style.opacity = '1';
      });
    }

    // Point-in-polygon advisory check
    if (latestFloodDs && !isHabitationSubmerged) {
      checkInundation(centerLat, centerLng, latestFloodDs, epicenterEntity, data.habitation_id);
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

function checkInundation(lat, lng, ds, entity, habId) {
  if (!ds.entities.values || ds.entities.values.length === 0) return;

  const pt = turf.point([lng, lat]);
  let isSubmerged = false;

  const stageData = simulationData.stages[ds._stageIndex];
  if (stageData && stageData.geojson && stageData.geojson.features.length > 0) {
    const poly = stageData.geojson.features[0];
    try { if (turf.booleanPointInPolygon(pt, poly)) isSubmerged = true; } catch(e) {}
  }

  const lsStageData = simulationData.landslide_cone.stages[ds._stageIndex];
  if (lsStageData && lsStageData.cone_geojson && lsStageData.cone_geojson.features.length > 0) {
    const lsPoly = lsStageData.cone_geojson.features[0];
    try { if (turf.booleanPointInPolygon(pt, lsPoly)) isSubmerged = true; } catch(e) {}
  }

  if (isSubmerged) {
    isHabitationSubmerged = true;
    entity.point.color = Cesium.Color.RED;

    const ul = document.getElementById('sim-advisory-log');
    const emptyLog = ul.querySelector('.empty-log');
    if (emptyLog) emptyLog.remove();

    const li = document.createElement('li');
    li.innerHTML = `<strong>${ds._stageLabel}</strong>: ${simulationData.habitation_name} breached! Triggering Evacuation Advisory...`;
    li.style.color = "var(--danger)";
    ul.appendChild(li);

    fetch('http://127.0.0.1:8000/advisory/' + habId).then(r => r.json()).then(res => {
      const li2 = document.createElement('li');
      const site = res?.advisory?.relocation_plan?.recommended_site;
      const siteName = site?.name || 'N/A';
      const siteDistrict = site?.district ? ', ' + site.district : '';
      li2.innerHTML = `✅ Relocate to: <strong>${siteName}${siteDistrict}</strong>`;
      ul.appendChild(li2);
    });
  }
}
