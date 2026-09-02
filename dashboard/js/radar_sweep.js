// radar_sweep.js - Canvas overlay for the radar scanning effect

class RadarSweep {
  constructor(map) {
    this.map = map;
    this.canvas = document.createElement('canvas');
    this.canvas.style.position = 'absolute';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.pointerEvents = 'none';
    this.canvas.style.zIndex = '500';
    
    // Add canvas to map pane
    map.getPanes().overlayPane.appendChild(this.canvas);
    
    this.ctx = this.canvas.getContext('2d');
    this.angle = 0;
    this.isAnimating = false;
    
    // Resize handler
    this.resize = this.resize.bind(this);
    map.on('resize moveend', this.resize);
    this.resize();
  }
  
  resize() {
    const size = this.map.getSize();
    this.canvas.width = size.x;
    this.canvas.height = size.y;
    
    // Reset position relative to map pane
    const topleft = this.map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(this.canvas, topleft);
  }
  
  startSweep(durationMs = 2000) {
    if (this.isAnimating) return;
    
    this.isAnimating = true;
    this.angle = 0;
    this.startTime = performance.now();
    this.duration = durationMs;
    
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.centerX = w / 2;
    this.centerY = h / 2;
    this.radius = Math.max(w, h);
    
    requestAnimationFrame((t) => this.animate(t));
  }
  
  animate(timestamp) {
    if (!this.isAnimating) return;
    
    const elapsed = timestamp - this.startTime;
    const progress = Math.min(elapsed / this.duration, 1);
    
    // 1 full rotation
    this.angle = progress * Math.PI * 2;
    
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    if (progress < 1) {
      this.drawRadarSweep();
      requestAnimationFrame((t) => this.animate(t));
    } else {
      this.isAnimating = false;
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }
  
  drawRadarSweep() {
    this.ctx.save();
    this.ctx.translate(this.centerX, this.centerY);
    this.ctx.rotate(this.angle);
    
    const gradient = this.ctx.createLinearGradient(0, 0, 0, -this.radius);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.4)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');
    
    this.ctx.beginPath();
    this.ctx.moveTo(0, 0);
    this.ctx.arc(0, 0, this.radius, -Math.PI/2, 0);
    this.ctx.lineTo(0, 0);
    this.ctx.fillStyle = gradient;
    this.ctx.fill();
    
    // Leading edge line
    this.ctx.beginPath();
    this.ctx.moveTo(0, 0);
    this.ctx.lineTo(0, -this.radius);
    this.ctx.strokeStyle = 'rgba(96, 165, 250, 0.8)';
    this.ctx.lineWidth = 2;
    this.ctx.stroke();
    
    this.ctx.restore();
  }
}

// Will be initialized in map.js
window.RadarSweepOverlay = RadarSweep;
