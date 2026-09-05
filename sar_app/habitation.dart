class Habitation {
  final String name;
  final String district;
  final String type;
  final double lat;
  final double lon;
  final int population;
  final double vulnerability;
  final double riskScore;
  final double floodRisk;
  final double landslideRisk;
  final double infrastructureRisk;
  final double risk;
  final bool relocationRequired;

  const Habitation({
    required this.name,
    required this.district,
    required this.type,
    required this.lat,
    required this.lon,
    required this.population,
    required this.vulnerability,
    required this.riskScore,
    required this.floodRisk,
    required this.landslideRisk,
    required this.infrastructureRisk,
    required this.risk,
    required this.relocationRequired,
  });

  factory Habitation.fromJson(Map<String, dynamic> json) {
    double number(dynamic value) {
      if (value is num) return value.toDouble();
      return double.tryParse(value?.toString() ?? '') ?? 0.0;
    }

    int integer(dynamic value) {
      if (value is num) return value.toInt();
      return int.tryParse(value?.toString() ?? '') ?? 0;
    }

    bool boolean(dynamic value) {
      if (value is bool) return value;
      if (value is String) {
        return value.toLowerCase() == 'true';
      }
      return false;
    }

    return Habitation(
      name: json['name']?.toString() ?? 'Unknown',
      district: json['district']?.toString() ?? '',
      type: json['type']?.toString() ?? '',
      lat: number(json['lat']),
      lon: number(json['lon']),
      population: integer(json['population']),
      vulnerability: number(json['vulnerability']),
      riskScore: number(json['riskScore'] ?? json['risk_score']),
      floodRisk: number(json['floodRisk'] ?? json['flood_risk']),
      landslideRisk:
          number(json['landslideRisk'] ?? json['landslide_risk']),
      infrastructureRisk:
          number(json['infrastructureRisk'] ?? json['infrastructure_risk']),
      risk: number(json['risk']),
      relocationRequired:
          boolean(json['relocationRequired'] ?? json['relocation_required']),
    );
  }
}