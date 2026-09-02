let currentUtterance = null;

function speakText(htmlText) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  
  const textToSpeak = htmlText
    .replace(/<br\s*[\/]?>/gi, '. ') // Add pauses for line breaks
    .replace(/<[^>]*>?/gm, '')       // Remove other HTML tags
    .replace(/\s+/g, ' ');           // Clean up spaces
    
  currentUtterance = new SpeechSynthesisUtterance(textToSpeak);
  
  const voices = window.speechSynthesis.getVoices();
  const preferredVoice = voices.find(v => v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Microsoft Mark')) || voices.find(v => v.lang.startsWith('en'));
  
  if (preferredVoice) {
    currentUtterance.voice = preferredVoice;
  }
  
  currentUtterance.rate = 0.85; // Slower, more deliberate pacing
  
  // Fix for Chrome bug where speak() right after cancel() is ignored
  setTimeout(() => {
    window.speechSynthesis.speak(currentUtterance);
  }, 150);
}

function startMainTutorial() {
  const intro = introJs();

  intro.setOptions({
    showProgress: true,
    showBullets: false,
    exitOnOverlayClick: false,
    tooltipClass: 'custom-intro-tooltip',
    steps: [
      {
        intro: "<b>Welcome to DISHA</b><br><br>Let's take a quick tour of how our AI predicts disasters and manages carrying capacity. This will explain the logic behind the scenes."
      },
      {
        element: document.querySelector('#map'),
        intro: "<b>The Global View</b><br><br>This map plots all vulnerable habitations. Our XGBoost model (trained on NASA catalogs & HydroRIVERS) analyzes the terrain (slope, ruggedness, drainage) of every single dot to predict baseline Flood and Landslide risks.",
        position: 'right'
      },
      {
        element: document.querySelector('.status-grid'),
        intro: "<b>Risk Overview</b><br><br>Habitations are sorted into zones based on their AI risk score.<br><br><span style='color: #ef4444'>RED:</span> >70% Risk<br><span style='color: #f97316'>ORANGE:</span> 45-70% Risk<br><span style='color: #eab308'>YELLOW:</span> 25-45% Risk",
        position: 'left'
      },
      {
        element: document.querySelector('.weather-trigger'),
        intro: "<b>Live Weather Trigger (Layer B)</b><br><br>We pull live 72-hour rainfall forecasts from Open-Meteo. If rainfall exceeds standard thresholds, it generates a 'Risk Multiplier' which dynamically escalates baseline terrain scores. This is our autonomous early warning trigger.",
        position: 'left'
      },
      {
        element: document.querySelector('#hab-list'),
        intro: "<b>Demography & Vulnerability</b><br><br>The sidebar lists all communities prioritized by their Risk Zone AND their social Vulnerability (SC/ST percentage). The AI always prioritizes the most vulnerable populations first.",
        position: 'left'
      },
      {
        intro: "<b>Triggering the COP</b><br><br>Now, try clicking on any of the habitations (dots) in the sidebar or map. It will slide open an advisory panel. From there, click <b>'Advanced Analysis (COP) & Simulation'</b> to see the deep dive for that specific community!"
      }
    ]
  });

  intro.onafterchange(function() {
    setTimeout(() => {
      const tooltip = document.querySelector('.introjs-tooltiptext');
      if (tooltip) {
        speakText(tooltip.innerHTML);
      }
    }, 300); // Wait for popup to render
  });

  intro.onexit(function() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  });

  intro.start();
  
  // Speak the first step immediately
  if (intro._options.steps[0] && intro._options.steps[0].intro) {
    speakText(intro._options.steps[0].intro);
  }
}
