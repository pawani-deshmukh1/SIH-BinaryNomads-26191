import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

class RiskZone {
  final String id;
  final String name;
  final String hazard;
  final double risk;
  final Color color;
  final List<LatLng> points;

  const RiskZone({
    required this.id,
    required this.name,
    required this.hazard,
    required this.risk,
    required this.color,
    required this.points,
  });
}