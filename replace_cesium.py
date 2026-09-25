import re

with open("dashboard/js/simulation_3d.js", "r", encoding="utf-8") as f:
    code = f.read()

# We want to replace from `  // Disable day/night sun lighting`
# down to `    // Reset state if rewound past start`

start_marker = "  // Disable day/night sun lighting"
end_marker = "    // Reset state if rewound past start"

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
    exit(1)

new_logic = """  // Disable day/night sun lighting
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
          return baseElev + getWaterLevel(time);
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

    // Reset state if rewound past start
"""

new_code = code[:start_idx] + new_logic + code[end_idx:]

# We also need to fix the checkInundation call, because we removed `latestFloodDs` logic.
# Wait, let's fix checkInundation.
fix_inundation = """
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
    
    // Handle stage transitions
    if (latestFloodIndex !== currentFloodIndex && latestFloodIndex >= 0) {
        // UI updates
        document.querySelectorAll('.stage-item').forEach(el => el.style.opacity = '0.5');
        const el = document.getElementById(ifIdx(latestFloodIndex));
        if (el) el.style.opacity = '1';
        
        // Camera Fly-to Choreography
        if (!flyInProgress) {
            flyInProgress = true;
            let dist = 10000;
            if (latestFloodIndex === 0) dist = 5000;
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
        
        currentFloodIndex = latestFloodIndex;
    }
  });
"""

# Let's find where checkInundation is in the code.
check_start = "    // Point-in-polygon advisory check"
check_end = "  viewer.clock.shouldAnimate = true;"
idx_c1 = new_code.find(check_start)
idx_c2 = new_code.find(check_end)
if idx_c1 != -1 and idx_c2 != -1:
    new_code = new_code[:idx_c1] + fix_inundation + new_code[idx_c2:]


# Update checkInundation function signature in the file
def_check_inundation = "function checkInundation(lat, lng, ds, entity, habId) {"
idx_d1 = new_code.find(def_check_inundation)
if idx_d1 != -1:
    idx_d2 = new_code.find("  if (isSubmerged) {", idx_d1)
    new_check = """function checkInundation(lat, lng, stageIndex, entity, habId) {
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
"""
    new_code = new_code[:idx_d1] + new_check + new_code[idx_d2:]

with open("dashboard/js/simulation_3d.js", "w", encoding="utf-8") as f:
    f.write(new_code)
print("Updated simulation_3d.js!")
