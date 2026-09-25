// strategic.js
// Layer 2 Strategic Monitoring Frontend

const API_BASE = window.API_BASE + "";
let map;
let markersLayer;
let currentChart = null;
let fullWatchlist = [];
let currentFilter = 'ALL';

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    loadWatchlist();

    document.getElementById("runway-filter").addEventListener("change", (e) => {
        loadWatchlist(e.target.value);
    });

    const runBtn = document.getElementById("btn-run-analysis");
    if (runBtn) {
        runBtn.addEventListener("click", triggerNewAnalysis);
    }
});

function initMap() {
    // Default to India center since we have data across multiple states now
    map = L.map('map').setView([20.5, 78.9], 5); 
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);
    markersLayer = L.featureGroup().addTo(map);
}

let pollInterval = null;

async function triggerNewAnalysis() {
    const btn = document.getElementById("btn-run-analysis");
    const statusDiv = document.getElementById("analysis-status");
    const statusText = document.getElementById("analysis-status-text");
    
    btn.disabled = true;
    btn.classList.add("opacity-50", "cursor-not-allowed");
    statusDiv.classList.remove("hidden");
    statusText.innerText = "Extracting Satellite Imagery...";
    
    try {
        const res = await fetch(`${API_BASE}/strategic/run-analysis`, { method: "POST" });
        const data = await res.json();
        
        if (data.status === "running") {
            pollInterval = setInterval(checkJobStatus, 2000);
        }
    } catch (e) {
        console.error("Analysis trigger failed", e);
        resetAnalysisUI("Error starting analysis.");
    }
}

async function checkJobStatus() {
    try {
        const res = await fetch(`${API_BASE}/strategic/job-status`);
        const data = await res.json();
        
        if (data.status === "completed") {
            clearInterval(pollInterval);
            document.getElementById("analysis-status-text").innerText = "Analysis Complete! Refreshing...";
            
            setTimeout(async () => {
                await loadWatchlist(document.getElementById("runway-filter").value);
                resetAnalysisUI();
                await fetch(`${API_BASE}/strategic/reset-job-status`, { method: "POST" });
            }, 1000);
            
        } else if (data.status === "error") {
            clearInterval(pollInterval);
            resetAnalysisUI("Analysis Failed.");
        }
    } catch (e) {
        console.error("Polling failed", e);
    }
}

function resetAnalysisUI(msg = null) {
    const btn = document.getElementById("btn-run-analysis");
    const statusDiv = document.getElementById("analysis-status");
    if (btn) {
        btn.disabled = false;
        btn.classList.remove("opacity-50", "cursor-not-allowed");
    }
    if (msg) {
        document.getElementById("analysis-status-text").innerText = msg;
        setTimeout(() => statusDiv.classList.add("hidden"), 3000);
    } else {
        statusDiv.classList.add("hidden");
    }
}

async function loadWatchlist(threshold = 48) {
    try {
        const res = await fetch(`${API_BASE}/strategic/watchlist?threshold_months=${threshold}`);
        const data = await res.json();
        fullWatchlist = data.watchlist;
        renderWatchlist();
    } catch (e) {
        console.error("Failed to load watchlist:", e);
    }
}

function filterWatchlist(type, element) {
    currentFilter = type;
    
    // Update tabs styling
    document.querySelectorAll('.border-b .flex-1').forEach(el => {
        el.classList.remove('active-tab', 'font-semibold', 'text-slate-200');
        el.classList.add('text-slate-400');
    });
    element.classList.add('active-tab', 'font-semibold', 'text-slate-200');
    element.classList.remove('text-slate-400');
    
    renderWatchlist();
}

function renderWatchlist() {
    const container = document.getElementById("watchlist-container");
    container.innerHTML = "";
    markersLayer.clearLayers();

    let filtered = fullWatchlist;
    if (currentFilter !== 'ALL') {
        filtered = fullWatchlist.filter(h => {
            if (currentFilter === 'erosion') return h.monitor_type === 'coastal_erosion';
            return h.monitor_type === currentFilter;
        });
    }

    if (filtered.length === 0) {
        container.innerHTML = `<div class="p-6 text-center text-slate-500 text-sm">No habitations found for this filter.</div>`;
        return;
    }

    filtered.forEach(hab => {
        const runwayBounds = hab.estimated_runway_months;
        const runwayText = Array.isArray(runwayBounds) ? `${runwayBounds[0]}-${runwayBounds[1]} mos` : `${runwayBounds} mos`;
        
        let badgeClass = "badge-moderate";
        if (hab.strategic_risk_class === "CRITICAL") badgeClass = "badge-critical";
        if (hab.strategic_risk_class === "HIGH") badgeClass = "badge-high";

        let typeIcon = "fa-location-dot";
        let typeText = "Unknown";
        if (hab.monitor_type === "glof_expansion") { typeIcon = "fa-mountain-sun"; typeText = "GLOF"; }
        else if (hab.monitor_type === "urban_flood_risk") { typeIcon = "fa-city"; typeText = "Urban Risk"; }
        else if (hab.monitor_type === "subsidence") { typeIcon = "fa-arrow-trend-down"; typeText = "Subsidence (InSAR)"; }
        else if (hab.monitor_type === "coastal_erosion") {
            typeIcon = hab.sub_type === "riverbank" ? "fa-water" : "fa-water";
            typeText = hab.sub_type === "riverbank" ? "Riverbank" : "Coastal";
        }

        const el = document.createElement("div");
        el.className = "watchlist-item";
        el.innerHTML = `
            <div class="flex justify-between items-start mb-1">
                <div class="font-bold text-slate-200">${hab.hab_name}</div>
                <span class="text-[10px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider ${badgeClass}">${hab.strategic_risk_class}</span>
            </div>
            <div class="text-xs text-slate-400 mb-2 font-mono flex gap-2">
                <span><i class="fa-solid ${typeIcon} text-slate-500"></i> ${typeText}</span>
                <span>|</span>
                <span class="text-blue-400 font-bold">Risk Score: ${hab.composite_risk_score?.toFixed(2) || 'N/A'}</span>
            </div>
            <div class="flex justify-between items-center text-sm">
                <div class="flex items-center gap-2">
                    <i class="fa-solid fa-hourglass-half text-slate-500"></i>
                    <span class="text-slate-300 font-medium">${runwayText} runway</span>
                </div>
                <div class="flex items-center gap-1 text-[10px] text-slate-400 font-mono" title="2011 Census Baseline Population">
                    <i class="fa-solid fa-users text-slate-500"></i> ${hab.population_2011 ? hab.population_2011.toLocaleString() : 'N/A'}
                </div>
            </div>
        `;
        el.onclick = () => openTrendDetail(hab.hab_id);
        container.appendChild(el);

        // Map Marker
        if (hab.lat && hab.lng) {
            let color = '#3b82f6';
    if (hab.monitor_type === "glof_expansion") color = '#06b6d4'; // Cyan
    else if (hab.monitor_type === "urban_flood_risk") color = '#8b5cf6'; // Purple
    else if (hab.monitor_type === "coastal_erosion") color = '#f59e0b'; // Amber/Orange
    else if (hab.monitor_type === "subsidence") color = '#ec4899'; // Pink
    
    const marker = L.circleMarker([hab.lat, hab.lng], {
        radius: 7,
        fillColor: color,
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
    }).addTo(map);
            
            marker.bindTooltip(`<b>${hab.hab_name}</b><br>${typeText} | Runway: ${runwayText}`, {permanent: false});
            marker.on('click', () => { openTrendDetail(hab.hab_id); });
            marker.addTo(markersLayer);
        }
    });
    
    if (markersLayer.getLayers().length > 0) {
        map.fitBounds(markersLayer.getBounds(), { padding: [50, 50], maxZoom: 10 });
    }
}

async function openTrendDetail(habId) {
    try {
        const res = await fetch(`${API_BASE}/strategic/${habId}/detail`);
        const data = await res.json();
        const hab = data.detail;

        document.getElementById("trend-panel").style.display = "flex";
        document.getElementById("panel-hab-name").innerText = hab.hab_name;
        document.getElementById("panel-hab-id").innerText = hab.hab_id;

        const runwayBounds = hab.estimated_runway_months;
        document.getElementById("runway-text").innerText = Array.isArray(runwayBounds) ? `${runwayBounds[0]} to ${runwayBounds[1]} Months` : `${runwayBounds} Months`;

        // Cost of Inaction Banner
        const coiBanner = document.getElementById("coi-banner");
        if (hab.projected_exposed_population > 0) {
            coiBanner.classList.remove("hidden");
            document.getElementById("coi-text").innerText = `${hab.projected_exposed_population.toLocaleString()} People Exposed`;
        } else {
            coiBanner.classList.add("hidden");
        }

        // Precedent Banner
        const precBanner = document.getElementById("precedent-banner");
        if (hab.known_event) {
            precBanner.classList.remove("hidden");
            document.getElementById("precedent-text").innerText = hab.known_event;
        } else {
            precBanner.classList.add("hidden");
        }

        // Setup dynamic metrics card
        const mCard = document.getElementById("metrics-card");
        const mTitle = document.getElementById("metrics-title");
        const mPri = document.getElementById("metrics-primary");
        const mGrid = document.getElementById("metrics-grid");
        
        mCard.classList.remove("hidden");
        mGrid.innerHTML = "";
        
        let chartDataSets = [];
        let labels = [];

        if (hab.monitor_type === "glof_expansion") {
            mTitle.innerHTML = `<i class="fa-solid fa-mountain-sun mr-2"></i>Glacial Lake Risk`;
            mPri.className = "text-xs font-mono bg-slate-900 px-2 py-1 rounded text-cyan-400 border border-cyan-800";
            mPri.innerText = `GLOF Index: ${hab.glof_risk_index.toFixed(2)}`;
            
            mGrid.innerHTML = `
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Lake Growth (5 Yr)</div>
                    <div class="text-lg font-bold text-slate-200">${hab.lake_growth_pct_5yr > 0 ? '+' : ''}${hab.lake_growth_pct_5yr}%</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Glacier Ice Loss</div>
                    <div class="text-lg font-bold text-slate-200">${hab.glacier_ice_loss_pct}%</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Elevation</div>
                    <div class="text-lg font-bold text-slate-200">${hab.elevation_m}m</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Downstream</div>
                    <div class="text-xs font-medium text-slate-300 truncate" title="${hab.downstream_pop}">${hab.downstream_pop}</div>
                </div>
            `;

            labels = hab.trend_series.map(t => t.year.toString());
            chartDataSets = [{
                label: 'Lake Area (ha)',
                data: hab.trend_series.map(t => t.lake_area_ha),
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                borderWidth: 2, fill: true, tension: 0.4
            }];
            document.getElementById("chart-source").innerText = hab.source || "Sentinel-2 NDWI GEE";

        } else if (hab.monitor_type === "coastal_erosion") {
            const isRiver = hab.sub_type === "riverbank";
            mTitle.innerHTML = `<i class="fa-solid fa-water mr-2"></i>${isRiver ? 'Riverbank Erosion' : 'Coastal Vulnerability'}`;
            mPri.className = "text-xs font-mono bg-slate-900 px-2 py-1 rounded text-orange-400 border border-orange-800";
            mPri.innerText = `CVI Score: ${hab.cvi_score.toFixed(2)}`;

            mGrid.innerHTML = `
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Erosion Velocity</div>
                    <div class="text-lg font-bold text-slate-200">${hab.erosion_velocity_m_yr} m/yr</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">NDVI Loss</div>
                    <div class="text-lg font-bold text-slate-200">${hab.key_metrics.ndvi_loss.toFixed(4)}</div>
                </div>
                <div class="col-span-2">
                    <div class="text-[10px] text-slate-400 uppercase">SAR Water Body Area Chg</div>
                    <div class="text-lg font-bold text-slate-200">${(hab.key_metrics.sar_water_increase_m2 / 1000000).toFixed(2)} km²</div>
                </div>
            `;

            labels = hab.trend_series.map(t => t.year.toString());
            chartDataSets = [{
                label: 'Land Area (km²)',
                data: hab.trend_series.map(t => t.land_area_m2 / 1000000), // convert to km2
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2, fill: true, tension: 0.4
            }];
            document.getElementById("chart-source").innerText = hab.source || "Sentinel-2 GEE + NCSCM";

        } else if (hab.monitor_type === "subsidence") {
            mTitle.innerHTML = `<i class="fa-solid fa-arrow-trend-down mr-2"></i>InSAR Subsidence`;
            mPri.className = "text-xs font-mono bg-slate-900 px-2 py-1 rounded text-purple-400 border border-purple-800";
            mPri.innerText = `Velocity: ${hab.deformation_velocity_mm_yr.toFixed(1)} mm/yr`;

            mGrid.innerHTML = `
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Total Deformation</div>
                    <div class="text-lg font-bold text-red-400">${hab.key_metrics.total_deformation_mm} mm</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Acceleration Factor</div>
                    <div class="text-lg font-bold text-slate-200">${hab.key_metrics.acceleration_factor}x</div>
                </div>
            `;

            labels = hab.trend_series.map(t => t.year.toString());
            chartDataSets = [{
                label: 'Subsidence (mm)',
                data: hab.trend_series.map(t => t.subsidence_mm),
                borderColor: '#c084fc',
                backgroundColor: 'rgba(192, 132, 252, 0.1)',
                borderWidth: 2, fill: true, tension: 0.4
            }];
            document.getElementById("chart-source").innerText = hab.source || "Sentinel-1 InSAR + GEE";


        } else if (hab.monitor_type === "urban_flood_risk") {
            mTitle.innerHTML = `<i class="fa-solid fa-city mr-2"></i>Urban Flood Risk`;
            mPri.className = "text-xs font-mono bg-slate-900 px-2 py-1 rounded text-red-400 border border-red-800";
            mPri.innerText = `UFRI: ${hab.ufri_score.toFixed(2)}`;

            mGrid.innerHTML = `
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">Perm. Water Loss</div>
                    <div class="text-lg font-bold text-red-400">${hab.key_metrics.jrc_loss_pct > 0 ? '-' : ''}${hab.key_metrics.jrc_loss_pct}%</div>
                </div>
                <div>
                    <div class="text-[10px] text-slate-400 uppercase">City</div>
                    <div class="text-lg font-bold text-slate-200">${hab.city}</div>
                </div>
            `;

            const bt = hab.trend_series.built_area;
            const wt = hab.trend_series.wetland_area;
            labels = bt.map(t => t.year.toString());
            
            chartDataSets = [
                {
                    label: 'Built Area (ha)',
                    data: bt.map(t => t.built_area_ha),
                    borderColor: '#ef4444',
                    backgroundColor: 'transparent',
                    borderWidth: 2, tension: 0.3, yAxisID: 'y'
                },
                {
                    label: 'Wetland Area (ha)',
                    data: wt.map(t => t.wetland_area_ha),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2, fill: true, tension: 0.3, yAxisID: 'y1'
                }
            ];
            document.getElementById("chart-source").innerText = hab.source || "Sentinel-2 + JRC Surface Water";
        }
        
        // Append cross-cutting metrics (Deforestation & Encroachment) to the grid
        if (hab.forest_loss_pct_3yr !== undefined) {
            mGrid.innerHTML += `
                <div class="mt-2 border-t border-slate-700 pt-2 col-span-2 flex justify-between">
                    <div>
                        <div class="text-[10px] text-slate-400 uppercase"><i class="fa-solid fa-tree text-green-600 mr-1"></i>3-Yr Forest Loss</div>
                        <div class="text-sm font-bold ${hab.forest_loss_pct_3yr > 10 ? 'text-red-400' : 'text-slate-300'}">${hab.forest_loss_pct_3yr}%</div>
                    </div>
                    <div>
                        <div class="text-[10px] text-slate-400 uppercase"><i class="fa-solid fa-house-chimney-crack text-orange-600 mr-1"></i>5-Yr New Structs (Encroachment)</div>
                        <div class="text-sm font-bold text-slate-300">${hab.encroachment_new_buildings_5yr}</div>
                    </div>
                </div>
            `;
        }

        // Draw Chart
        document.getElementById("chart-card").classList.remove("hidden");
        const ctx = document.getElementById('trendChart').getContext('2d');
        if (currentChart) currentChart.destroy();
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: hab.monitor_type === 'urban_flood_risk', labels: { color: '#94a3b8' } } },
            scales: {
                x: { display: true, ticks: { color: '#64748b', font: { size: 9 } }, grid: { display: false } },
                y: { 
                    type: 'linear', display: true, position: 'left',
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        };

        if (hab.monitor_type === 'urban_flood_risk') {
            chartOptions.scales.y1 = {
                type: 'linear', display: true, position: 'right',
                grid: { drawOnChartArea: false },
                ticks: { color: '#10b981', font: { size: 10 } }
            };
        }
        
        currentChart = new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: chartDataSets },
            options: chartOptions
        });

        // Action Button triggers Layer 1 advisory
        document.getElementById("btn-relocate").onclick = () => {
            window.location.href = `advisory.html?hab_id=${hab.hab_id}&trigger=strategic`;
        };

        // Zoom map to the feature
        if (hab.lat && hab.lng) {
            map.flyTo([hab.lat, hab.lng], 12);
        }

    } catch (e) {
        console.error("Failed to load details:", e);
    }
}

function closeTrendPanel() {
    document.getElementById("trend-panel").style.display = "none";
}

let guwahatiCharts = [];

async function openGuwahatiDeepDive() {
    document.getElementById('guwahati-modal').style.display = 'flex';
    
    try {
        // Fetch backtest
        const btRes = await fetch(`${API_BASE}/strategic/urban/guwahati/backtest`);
        const btData = await btRes.json();
        const bt = btData.backtest;
        
        const hitColor = bt.hit_rate_pct > 60 ? 'text-emerald-400' : 'text-orange-400';
        document.getElementById('guwahati-backtest-content').innerHTML = `
            <div class="mb-3">
                <div class="text-xs text-indigo-400 uppercase">Validation Events Tested</div>
                <ul class="list-disc pl-4 mt-1 text-slate-300">
                    ${bt.validation_events.map(e => `<li>${e}</li>`).join('')}
                </ul>
            </div>
            <div class="mb-3">
                <div class="text-xs text-indigo-400 uppercase">Model Top 3 Predicted Vulnerable Basins</div>
                <ul class="list-disc pl-4 mt-1 text-slate-300">
                    ${bt.top_predicted_basins.map(b => `<li>${b}</li>`).join('')}
                </ul>
            </div>
            <div class="mt-4 border-t border-indigo-500/50 pt-3">
                <div class="flex justify-between items-center">
                    <span class="uppercase tracking-widest text-xs font-bold text-slate-400">Concordance Hit-Rate</span>
                    <span class="text-2xl font-bold ${hitColor}">${bt.hit_rate_pct}%</span>
                </div>
                <p class="text-[10px] text-indigo-300 mt-1 italic">${bt.note}</p>
            </div>
        `;

        // Fetch Basins
        const res = await fetch(`${API_BASE}/strategic/urban/guwahati`);
        const data = await res.json();
        const basins = data.basins;

        const container = document.getElementById('guwahati-basins-container');
        container.innerHTML = '';
        
        // Clear old charts
        guwahatiCharts.forEach(c => c.destroy());
        guwahatiCharts = [];

        basins.forEach((basin, index) => {
            const riskColor = basin.risk_class === 'CRITICAL' ? 'text-red-400 border-red-500/50 bg-red-900/20' : 'text-orange-400 border-orange-500/50 bg-orange-900/20';
            
            const el = document.createElement('div');
            el.className = `border rounded-lg p-4 flex flex-col ${riskColor.split(' ').slice(1).join(' ')}`;
            
            el.innerHTML = `
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <h4 class="font-bold text-slate-200 text-sm">${basin.name}</h4>
                        <div class="text-[10px] text-slate-400 font-mono mt-1">${basin.basin_id} | ${basin.basin_geometrics.total_area_ha} ha</div>
                    </div>
                    <div class="text-right">
                        <div class="text-xs uppercase tracking-widest font-bold ${riskColor.split(' ')[0]}">UFRI Score</div>
                        <div class="text-xl font-bold text-white">${basin.ufri_score.toFixed(2)}</div>
                    </div>
                </div>
                
                <div class="text-xs text-slate-300 mb-3 bg-slate-900/50 p-2 rounded border border-slate-700">
                    <i class="fa-solid fa-satellite text-blue-400 mr-1"></i>
                    <strong>Stage 1/2 Validation:</strong> Pixel-verified against May 2025 SAR inundation.
                </div>
                
                <div class="grid grid-cols-2 gap-2 mb-4 text-xs">
                    <div class="bg-slate-800 p-2 rounded">
                        <div class="text-[10px] text-slate-400 uppercase">Built-up Growth</div>
                        <div class="font-bold text-red-400">+${basin.dynamic_metrics.concrete_growth_pct.toFixed(1)}%</div>
                    </div>
                    <div class="bg-slate-800 p-2 rounded">
                        <div class="text-[10px] text-slate-400 uppercase">Wetland Loss</div>
                        <div class="font-bold text-emerald-400">-${basin.dynamic_metrics.wetland_loss_pct.toFixed(1)}%</div>
                    </div>
                    <div class="bg-slate-800 p-2 rounded">
                        <div class="text-[10px] text-slate-400 uppercase">Pump Dependency</div>
                        <div class="font-bold text-orange-400">${basin.basin_geometrics.pump_dependency_score} / 1.0</div>
                    </div>
                    <div class="bg-slate-800 p-2 rounded">
                        <div class="text-[10px] text-slate-400 uppercase">Validation Flood</div>
                        <div class="font-bold text-indigo-400">${basin.validation_flood_extent_ha} ha</div>
                    </div>
                </div>

                <!-- Satellite Visual Validation Widget -->
                <div class="mb-4 bg-slate-950 rounded border border-slate-700 p-2">
                    <div class="flex justify-between items-center mb-2">
                        <div class="text-[10px] uppercase text-slate-400 font-bold">Satellite Evidence</div>
                        <div class="flex gap-2">
                            <button onclick="document.getElementById('vis-${index}').src='${basin.visual_optical}'" class="text-[9px] bg-slate-800 px-2 py-1 rounded hover:bg-slate-700 text-slate-300">Clean Optical</button>
                            <button onclick="document.getElementById('vis-${index}').src='${basin.visual_sar}'" class="text-[9px] bg-indigo-900 px-2 py-1 rounded hover:bg-indigo-800 text-indigo-200">SAR Flood Fusion</button>
                        </div>
                    </div>
                    <div class="w-full h-32 bg-black rounded overflow-hidden flex items-center justify-center">
                        <img id="vis-${index}" src="${basin.visual_sar}" class="h-full object-contain" onerror="this.src='images/dummy.jpg'"/>
                    </div>
                </div>

                <div class="h-32 w-full mt-auto relative bg-slate-900/30 rounded p-1 border border-slate-700">
                    <canvas id="guwahati-chart-${index}"></canvas>
                </div>
            `;
            container.appendChild(el);

            // Draw Chart
            const ctx = document.getElementById(`guwahati-chart-${index}`).getContext('2d');
            const bt = basin.trend_series;
            const labels = bt.map(t => t.year.toString());
            
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Built Area (ha)',
                            data: bt.map(t => t.built_ha),
                            borderColor: '#ef4444',
                            borderWidth: 2, tension: 0.3, yAxisID: 'y', pointRadius: 0
                        },
                        {
                            label: 'Wetland (ha)',
                            data: bt.map(t => t.wetland_ha),
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2, fill: true, tension: 0.3, yAxisID: 'y1', pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: true, ticks: { color: '#64748b', font: { size: 8 } }, grid: { display: false } },
                        y: { display: false, type: 'linear', position: 'left' },
                        y1: { display: false, type: 'linear', position: 'right' }
                    }
                }
            });
            guwahatiCharts.push(chart);
        });

    } catch (e) {
        console.error("Deep dive failed", e);
    }
}

function closeGuwahatiDeepDive() {
    document.getElementById('guwahati-modal').style.display = 'none';
}

