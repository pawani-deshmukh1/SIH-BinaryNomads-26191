# 🚨 DISHA — Dynamic Intelligence System for Hazard Action

**Team:** Binary Nomads  
**Hackathon:** Smart India Hackathon (SIH) 2026  
**Problem Statement:** SIH26191 — Ministry of Home Affairs (NDRF / DM Division)  

---

## 📖 Overview

**DISHA** is an AI-driven, multi-layered decision support platform designed to answer the core challenge of SIH26191: *Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations.* 

Unlike traditional platforms that only act during a crisis, DISHA spans **long-term strategy, proactive evacuation, and post-disaster self-calibrating response** through a unified, 4-Layer architecture.

---

## 📸 Platform Previews

Here is DISHA in action, demonstrating our end-to-end disaster intelligence pipeline:

**1. Proactive Habitation Analysis & Multiple Safe Relocation Zone Routing (with Sachet Assist)**
![Proactive Habitation Analysis & Relocation Routing](disha_visuals/1.png)

**2. High-Fidelity UFRI Analysis of Guwahati City for Proactive DM and MHA Planning**
![High-Fidelity UFRI Analysis of Guwahati City](disha_visuals/2.png)

**3. Human-in-the-Loop Self-Healing Pipeline for Continuous AI Model Calibration**
![Human-in-the-Loop Self-Healing Pipeline](disha_visuals/3.png)

**4. 3D Disaster Simulation with 36-Hour Lead Time Based on Real-Time Forecasts**
![3D Disaster Simulation](disha_visuals/4.png)

**5. Long-Term Strategic Observatory for Tracking Multi-Hazard Risks and Urban Trends**
![Long-Term Strategic Observatory](disha_visuals/5.png)

---

## 🏗️ The 4-Layer Architecture

DISHA is built on a highly modular 4-layer system, each operating on a different timescale and serving a specific disaster management goal.

### 🟡 Layer 0: The Reactive Layer (Hours to Days)
**Goal:** Detect hyper-local, fast-developing atmospheric threats before they manifest on the ground.
- **How it works:** Uses a **Thermodynamic XGBoost model** to process meteorological and sensor data, identifying rapidly developing events like heavy rain and Cloudbursts. Gives authorities critical lead time to mobilize teams.

### 🟢 Layer 1: The Proactive Layer (The Core SIH26191 Mandate)
**Goal:** Map immediate danger, calculate safe capacities, and optimize relocation routes before the disaster strikes.
This is the core pipeline addressing the SIH problem statement (**IDENTIFY → ASSESS → PRIORITIZE → RELOCATE**).
- **Red Zone Mapping:** **XGBoost Proactive Models** for both Flood and Landslide assess geological, meteorological, and topological data to declare hazard susceptibility.
- **Relocation Engine:** AI-optimized bipartite matching assigns vulnerable populations to safe zones based on strict **Carrying Capacity** constraints.
- **Dynamic Routing:** Instantly routes convoys around flooded roads using OSMnx and an **OSRM Fallback Engine**, generating unpaved "Kacha Way" detours if a community is isolated.

### 🔵 Layer 2: The Strategic Observatory (Months to Years)
**Goal:** Long-term urban planning and vulnerability tracking.
- **UFRI (Urban Flood Risk Index) Deep Dive:** XGBoost models are highly effective for stable terrain, but rapid, chaotic urbanization kills terrain stability, rendering standard XGBoost predictions ineffective in cities. For our MVP, we chose **Guwahati** to implement the UFRI. It is a forensic 10-layer spatial intelligence model computing live flood risk using the Rational Method (`Q = CiA`), flagging critical drainage thresholds before city-wide flooding occurs.
- **Long-term Watchlist:** Monitors slow-moving disasters like Coastal Erosion and Glacial Lake Outburst Floods (GLOF).

### 🔴 Layer 3: Damage Assessment & Self-Calibration (Post-Disaster)
**Goal:** Ground-truth validation and continuous model improvement.
- **Vision Models:** We deploy 3 computer vision models (Flood, Landslide, and Building Damage) post-disaster. 
- **Self-Calibration Loop:** The visual outputs from these models are directly compared against the Layer 1 XGBoost model predictions. The discrepancies and recordings are logged so that new data is continually collected, allowing the core XGBoost models to be upgraded and fine-tuned over time.

---

## 🧠 The 7 AI Models of DISHA

DISHA is powered by an ensemble of 7 distinct AI models working in harmony:

1. **Thermodynamic Heavy Rain Detection:** (XGBoost) - *Layer 0*
2. **Flood Proactive Model:** (XGBoost) - *Layer 1*
3. **Landslide Proactive Model:** (XGBoost) - *Layer 1*
4. **Flood Vision Model:** (ONNX U-Net) - *Layer 3 Validation*
5. **Landslide Vision Model:** (ONNX ResNet50) - *Layer 3 Validation*
6. **Damage Vision Model:** (ONNX Siamese ResNet50) - *Layer 3 Assessment*
7. **Integration Agent & RAG:** (Groq LLM) - Serves as the AI brain for the UFRI spatial analysis and auto-generates tactical briefings and field-ops alerts based on telemetry data.

---

## 👥 Stakeholder Views: DM vs. MHA

DISHA recognizes that Disaster Management (DM) forces on the ground and the Ministry of Home Affairs (MHA) have very different informational needs.
- **DM (Disaster Management) View:** Granular, hyper-local, and highly actionable. Used by NDRF, SDMA, DDMA, and NDMA forces. These dashboards show exact evacuation routes, individual building damage, carrying capacities of local schools/camps, and real-time alerts.
- **MHA (Ministry of Home Affairs) View:** Aggregated, strategic oversight. The MHA actively uses the UFRI spatial explainer (Guwahati 3D simulation) to interface with the Ministry of Housing and Urban Affairs (MoUHA). It provides the concrete data needed to prevent infrastructure from being built in high-risk zones, stop deforestation in critical drainage paths, and drive inter-ministerial policy compromises based on undeniable spatial intelligence.

---

## 🚀 Advanced Platform Features

### 🌍 3D Simulation
To truly understand urban vulnerability, DISHA includes a high-fidelity **3D Guwahati Deep-Dive** (built on WebGL/Cesium logic). It visualizes the **UFRI** spatially, allowing operators to see exactly how water will pool in urban basins, which specific wards will drown first, and where drainage infrastructure is failing geometrically.

### 👮 Field Ops & SAR App
DISHA extends beyond the command center directly to the responders. The **Field Ops** module (and the connected `sar_app` Flutter application) connects ground teams with the Common Operating Picture (COP). Responders receive hazard-aware routes and can push live ground-truth data back to the central server.

---

## 🔮 Phase 2 / Future Scope

While the MVP fully answers the SIH26191 mandate, DISHA is architected to scale into a national grid. Future expansions include:
- **GRU Models for Urban Flood Forecasting:** Implementing Gated Recurrent Unit (GRU) time-series forecasting to predict urban inundation hours in advance, once richer temporal flow datasets are acquired.
- **Live On-Field Sensor Integration:** Connecting directly with municipal IoT water level sensors for zero-latency triggers instead of relying solely on remote satellite or generic CWC data.
- **RAG-Powered SOS Triage & Noise Filtering:** Using LLMs to intelligently prioritize ground-truth panic. For example: distinguishing between a high volume of SOS calls from a safe zone (low physical threat / high panic) vs. a low volume of calls from a deeply inundated red zone (high physical threat / connectivity lost), allowing the AI to dynamically direct DM forces to the actual high-risk area first.

---

## 💻 Setup & Installation

### Backend (FastAPI + ONNX/XGBoost)
```bash
git clone https://github.com/pawani-deshmukh1/BINARY-NOMADS-SIH26191-DISHA.git
cd BINARY-NOMADS-SIH26191-DISHA/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### Frontend (Dashboard)
```bash
cd dashboard
npx serve .
```

*Built with ❤️ by Team Binary Nomads for SIH 2026.*
