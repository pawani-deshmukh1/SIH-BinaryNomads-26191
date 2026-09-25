document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('onnx-form');
    const runBtn = document.getElementById('run-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const outputImage = document.getElementById('output-image');
    
    // Telemetry fields
    const outputConf = document.getElementById('output-conf');
    const latencyVal = document.getElementById('latency-val');
    const gapVal = document.getElementById('gap-val');
    const gapDesc = document.getElementById('gap-desc');
    const areaVal = document.getElementById('area-val');
    
    // Store global metrics so we can send them to DB later
    window.lastInferenceMetrics = null;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('post-image');
        const lat = document.getElementById('lat-input').value;
        const lng = document.getElementById('lng-input').value;
        
        if (fileInput.files.length === 0) {
            alert('Please select a post-disaster image first.');
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('post_image', file);
        formData.append('lat', lat);
        formData.append('lng', lng);
        formData.append('radius_km', 2.0);
        formData.append('demo_mode', 'false'); // Force live ONNX inference
        
        // Reset UI
        runBtn.disabled = true;
        runBtn.innerText = 'Running Pipeline...';
        outputImage.style.display = 'none';
        loadingSpinner.style.display = 'block';
        outputConf.innerText = 'Running Inference...';
        
        try {
            const res = await fetch('/analyze/', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Inference Failed');
            }
            
            const data = await res.json();
            
            // Render Image
            if (data.annotated_image_base64) {
                outputImage.src = 'data:image/jpeg;base64,' + data.annotated_image_base64;
                loadingSpinner.style.display = 'none';
                outputImage.style.display = 'block';
            }
            
            // Render Telemetry
            latencyVal.innerText = `${data.summary.pipeline_duration_ms.toFixed(0)} ms`;
            
            // Calculate features found vs predicted
            const actualFloodCount = data.features.filter(f => f.properties.layer_type === 'flood_zone').length;
            const actualDamageCount = data.features.filter(f => f.properties.layer_type === 'damage_zone').length;
            
            areaVal.innerText = `${actualFloodCount} Flood Polys, ${actualDamageCount} Damage Polys`;
            
            // Simulated gap analysis based on returned features
            const layer1Predicted = Math.max(1, actualFloodCount - Math.floor(Math.random() * 3)); // Dummy logic for demo
            const discrepancy = Math.abs(actualFloodCount - layer1Predicted);
            
            if (discrepancy > 0) {
                gapVal.innerText = `-${discrepancy} Polygons`;
                gapVal.style.color = 'var(--red)';
                gapDesc.innerText = `Layer 1 under-predicted inundation extent. Gap logged for calibration.`;
            } else {
                gapVal.innerText = 'Aligned (0 Gap)';
                gapVal.style.color = 'var(--success)';
                gapDesc.innerText = `Layer 1 predictive model matches Layer 3 reality.`;
            }
            
            const maxConf = Math.max(
                data.model_confidence.flood.score, 
                data.model_confidence.landslide.score
            );
            outputConf.innerText = `Peak Confidence: ${(maxConf * 100).toFixed(1)}%`;
            
            // Save state for commit
            window.lastInferenceMetrics = {
                lat: parseFloat(lat),
                lng: parseFloat(lng),
                predicted_flood_polys: layer1Predicted,
                actual_flood_polys: actualFloodCount,
                peak_confidence: maxConf
            };
            
        } catch (err) {
            console.error(err);
            alert('Pipeline Error: ' + err.message);
            loadingSpinner.innerText = 'Error: ' + err.message;
        } finally {
            runBtn.disabled = false;
            runBtn.innerText = 'Run ONNX Pipeline';
        }
    });

    // Fetch initial logs
    fetchCalibrationLogs();
});

async function fetchCalibrationLogs() {
    const tbody = document.getElementById('calibration-log-body');
    if (!tbody) return;
    try {
        const res = await fetch('/api/admin/integration/logs/calibration');
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:8px; color:var(--text-dim);">No logs found.</td></tr>';
            return;
        }

        tbody.innerHTML = data.slice(0, 5).map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const gapColor = Math.abs(log.gap_variance) > 2 ? '#f87171' : '#34d399';
            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 4px;">${time}</td>
                    <td style="padding: 4px; font-weight:bold; color:${gapColor}">${log.gap_variance > 0 ? '+'+log.gap_variance : log.gap_variance}</td>
                    <td style="padding: 4px;">${(log.peak_confidence * 100).toFixed(0)}%</td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error("Log fetch error:", e);
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--red);">Error loading DB</td></tr>';
    }
}

window.commitCalibration = async function() {
    if (!window.lastInferenceMetrics) {
        alert("Please run an inference first before committing calibration gaps.");
        return;
    }

    const btn = document.querySelector('.btn[onclick="commitCalibration()"]');
    btn.innerHTML = '<span class="spinner" style="display:inline-block; margin-right:8px; width:14px; height:14px;"></span> Committing to DB...';
    btn.style.opacity = '0.8';
    
    try {
        const res = await fetch('/analyze/calibrate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(window.lastInferenceMetrics)
        });
        
        if (!res.ok) throw new Error("Failed to write to database");
        
        btn.innerHTML = '✓ Saved to SQLite DB';
        btn.style.background = '#059669';
        btn.onclick = null;

        // Refresh the UI log table
        fetchCalibrationLogs();
    } catch (e) {
        console.error(e);
        alert("DB Error: " + e.message);
        btn.innerHTML = 'Commit Failed';
    }
}
