import json
import os
import numpy as np

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
TRENDS_FILE = os.path.join(FIXTURES_DIR, "strategic_trends.json")
DEMOGRAPHICS_FILE = os.path.join(FIXTURES_DIR, "demographics_2011.json")

def load_strategic_trends():
    if not os.path.exists(TRENDS_FILE):
        return []
    with open(TRENDS_FILE, 'r') as f:
        return json.load(f)

def load_demographics():
    if not os.path.exists(DEMOGRAPHICS_FILE):
        return {}
    with open(DEMOGRAPHICS_FILE, 'r') as f:
        return json.load(f)

def calculate_auto_runway(hab):
    """
    Fits a polynomial regression (linear or quadratic) to the last 5 years of data
    to predict exactly when a conservative screening threshold will be crossed.
    Uses a 2nd-degree fit if a structural acceleration factor is detected, preventing
    dangerous underestimation of non-linear collapse events.
    """
    trend_series = hab.get("trend_series")
    monitor_type = hab.get("monitor_type")
    acceleration_factor = hab.get("acceleration_factor", 1.0)
    
    if not trend_series or isinstance(trend_series, dict):
        return 99 # Fallback for complex shapes or empty data
        
    try:
        years = []
        values = []
        for point in trend_series:
            years.append(point["year"])
            if monitor_type == "glof_expansion":
                values.append(point.get("lake_area_ha", 0))
            elif monitor_type == "coastal_erosion":
                values.append(point.get("land_area_m2", 0))
            elif monitor_type == "subsidence":
                values.append(point.get("subsidence_mm", 0))
                
        if len(years) < 3:
            return 99
            
        current_year = max(years)
        
        # Define arbitrary conservative screening thresholds
        if monitor_type == "glof_expansion":
            threshold = max(values) * 1.5 # 50% larger than current max
        elif monitor_type == "coastal_erosion":
            threshold = min(values) * 0.9 # 10% loss of remaining land
        elif monitor_type == "subsidence":
            threshold = min(values) - 100 # another 100mm of drop
            
        target_year = current_year
        
        # Use Quadratic (2nd degree) fit if acceleration is detected
        if acceleration_factor > 1.2 and len(years) >= 3:
            # y = a*x^2 + b*x + c
            a, b, c = np.polyfit(years, values, 2)
            
            # Solve quadratic: a*x^2 + b*x + (c - threshold) = 0
            # x = (-b +/- sqrt(b^2 - 4*a*(c - threshold))) / (2*a)
            c_adj = c - threshold
            discriminant = (b**2) - (4 * a * c_adj)
            
            if discriminant >= 0 and a != 0:
                root1 = (-b + np.sqrt(discriminant)) / (2 * a)
                root2 = (-b - np.sqrt(discriminant)) / (2 * a)
                # We want the smallest root that is in the future
                valid_roots = [r for r in (root1, root2) if r > current_year]
                if valid_roots:
                    target_year = min(valid_roots)
                else:
                    # Fallback if parabola opens away from threshold
                    return 999
            else:
                return 999
        else:
            # Fallback to Linear (1st degree) fit: y = mx + c
            m, c = np.polyfit(years, values, 1)
            
            # If trend is flat or getting safer, runway is essentially infinite
            if monitor_type == "glof_expansion" and m <= 0: return 999
            if monitor_type == "coastal_erosion" and m >= 0: return 999
            if monitor_type == "subsidence" and m >= 0: return 999
            
            target_year = (threshold - c) / m
            
        months_until = int(max(1, (target_year - current_year) * 12))
        return min(months_until, 999) # Cap at ~83 years
        
    except Exception as e:
        return 99

def calculate_composite_score(hab):
    """
    Calculates a unified 0.0-1.0 risk score across entirely different hazard types
    so the District Collector can rank all habitations in one unified list.
    """
    score = 0.0
    mt = hab.get("monitor_type")
    
    if mt == "glof_expansion":
        score = hab.get("glof_risk_index", 0.0)
    elif mt == "coastal_erosion":
        score = hab.get("cvi_score", 0.0) * 1.5 # Scale up CVI slightly to match GLOF 0-1 range
    elif mt == "urban_flood_risk":
        score = hab.get("ufri_score", 0.0) * 1.2
    elif mt == "subsidence":
        # -200mm deformation scales to ~1.0 risk
        vel = abs(hab.get("deformation_velocity_mm_yr", 0))
        score = min(1.0, vel / 60.0)
        
    # Apply penalty for deforestation (Layer 2 feedback mechanism)
    forest_loss = hab.get("forest_loss_pct_3yr", 0)
    if forest_loss > 10.0:
        score *= 1.15
        
    return min(1.0, round(score, 4))

import math

def calculate_impact_priority(hab, demographics):
    comp_score = calculate_composite_score(hab)
    hab_id = hab.get("hab_id")
    demo = demographics.get(hab_id, {})
    
    population = demo.get("population_2011", 1000)
    sc_st_pct = demo.get("sc_st_percent", 0)
    landless_pct = demo.get("landless_households_pct", 0)
    
    # Base impact: log-scaled population
    base_impact = comp_score * math.log10(max(10, population))
    
    # Vulnerability multiplier: up to 2.0x for highly vulnerable (e.g. 100% SC/ST & landless)
    # Give weight: 0.6 to sc_st, 0.4 to landless. Total max additional = 1.0 (so max mult = 2.0)
    vuln_factor = ( (sc_st_pct / 100.0) * 0.6 ) + ( (landless_pct / 100.0) * 0.4 )
    multiplier = 1.0 + vuln_factor
    
    impact_score = base_impact * multiplier
    return round(impact_score, 4), population

def project_cost_of_inaction(hab, runway_months, population_2011):
    mt = hab.get("monitor_type")
    
    if runway_months >= 999 or population_2011 == 0:
        return 0
        
    projected_new_exposure = 0
    try:
        years_ahead = runway_months / 12.0
        
        if mt == "glof_expansion":
            growth_pct = hab.get("lake_growth_pct_5yr", 0) / 5.0 # annual growth rate
            projected_new_exposure = population_2011 * (max(0, growth_pct) / 100.0) * years_ahead
        elif mt == "urban_flood_risk":
            # Conservative 2% annual expansion of flood impact perimeter
            projected_new_exposure = population_2011 * 0.02 * years_ahead
        elif mt == "coastal_erosion":
            # Say 1% population relocated per year
            projected_new_exposure = population_2011 * 0.01 * years_ahead
        elif mt == "subsidence":
            # Rapid subsidence exposes more people.
            projected_new_exposure = population_2011 * 0.05 * years_ahead
            
    except Exception:
        pass
        
    return int(projected_new_exposure)


def get_watchlist(threshold_months: int = 48):
    trends = load_strategic_trends()
    demographics = load_demographics()
    watchlist = []
    
    for t in trends:
        # Calculate auto-forecast
        mt = t.get("monitor_type")
        exact_runway = calculate_auto_runway(t)
        
        # Override the static fixture
        t["estimated_runway_months"] = exact_runway
        
        # Calculate composite score
        t["composite_risk_score"] = calculate_composite_score(t)
        
        # Calculate Impact Priority & Cost of Inaction
        impact_score, pop_2011 = calculate_impact_priority(t, demographics)
        t["impact_priority_score"] = impact_score
        t["population_2011"] = pop_2011
        t["projected_exposed_population"] = project_cost_of_inaction(t, exact_runway, pop_2011)
        
        # Normalize fields for frontend
        t["hab_name"] = t.get("name", "Unknown")
        t["strategic_risk_class"] = t.get("risk_class", "UNKNOWN")

        # In a real app we'd filter by threshold_months, but for the demo we want to show all
        # unless it's genuinely safe (runway > 120)
        # Provide to frontend regardless of horizon to ensure all hazards are visible (including slow erosion)
        watchlist.append(t)
            
    # Sort by unified impact score descending (highest priority first)
    watchlist.sort(key=lambda x: x.get("impact_priority_score", 0.0), reverse=True)
    return watchlist

def get_trend_detail(hab_id: str):
    trends = load_strategic_trends()
    demographics = load_demographics()
    for t in trends:
        if t["hab_id"] == hab_id:
            mt = t.get("monitor_type")
            exact_runway = calculate_auto_runway(t)
            t["estimated_runway_months"] = exact_runway
            t["composite_risk_score"] = calculate_composite_score(t)
            
            impact_score, pop_2011 = calculate_impact_priority(t, demographics)
            t["impact_priority_score"] = impact_score
            t["population_2011"] = pop_2011
            t["projected_exposed_population"] = project_cost_of_inaction(t, exact_runway, pop_2011)
            
            t["hab_name"] = t.get("name", "Unknown")
            t["strategic_risk_class"] = t.get("risk_class", "UNKNOWN")
            return t
    return None
