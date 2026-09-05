import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../../models/habitation.dart';
import '../../models/relocation_site.dart';

const bg = Color(0xFF071018);
const panel = Color(0xFF0C1721);
const panel2 = Color(0xFF111F2B);
const border = Color(0xFF20313D);
const cyan = Color(0xFF35D0BA);
const blue = Color(0xFF4CA6FF);
const red = Color(0xFFFF5263);
const orange = Color(0xFFFFA94D);
const yellow = Color(0xFFFFD166);
const green = Color(0xFF43D17A);
const muted = Color(0xFF8293A0);

const String backendBaseUrl =
    'https://sih-binarynomads-26191.onrender.com';

enum RiskLevel {
  critical,
  high,
  moderate,
  low,
}

RiskLevel riskLevelFromScore(double score) {
  if (score >= 80) {
    return RiskLevel.critical;
  }

  if (score >= 60) {
    return RiskLevel.high;
  }

  if (score >= 40) {
    return RiskLevel.moderate;
  }

  return RiskLevel.low;
}

Color riskColor(RiskLevel risk) {
  switch (risk) {
    case RiskLevel.critical:
      return red;
    case RiskLevel.high:
      return orange;
    case RiskLevel.moderate:
      return yellow;
    case RiskLevel.low:
      return green;
  }
}

String riskText(RiskLevel risk) {
  switch (risk) {
    case RiskLevel.critical:
      return 'CRITICAL';
    case RiskLevel.high:
      return 'HIGH';
    case RiskLevel.moderate:
      return 'MODERATE';
    case RiskLevel.low:
      return 'LOW';
  }
}

Widget riskBadge(RiskLevel risk) {
  final color = riskColor(risk);

  return Container(
    padding: const EdgeInsets.symmetric(
      horizontal: 9,
      vertical: 5,
    ),
    decoration: BoxDecoration(
      color: color.withOpacity(.12),
      borderRadius: BorderRadius.circular(8),
      border: Border.all(
        color: color.withOpacity(.3),
      ),
    ),
    child: Text(
      riskText(risk),
      style: TextStyle(
        color: color,
        fontSize: 10,
        fontWeight: FontWeight.w900,
        letterSpacing: .7,
      ),
    ),
  );
}

class RedZone {
  final String primaryHazard;
  final double riskScore;
  final String colorTier;
  final List<LatLng> points;

  const RedZone({
    required this.primaryHazard,
    required this.riskScore,
    required this.colorTier,
    required this.points,
  });

  factory RedZone.fromJson(Map<String, dynamic> json) {
    final properties =
        (json['properties'] as Map?)?.cast<String, dynamic>() ??
            <String, dynamic>{};

    final geometry =
        (json['geometry'] as Map?)?.cast<String, dynamic>() ??
            <String, dynamic>{};

    final rawCoordinates = geometry['coordinates'];

    final points = <LatLng>[];

    if (rawCoordinates is List && rawCoordinates.isNotEmpty) {
      final firstRing = rawCoordinates.first;

      if (firstRing is List) {
        for (final item in firstRing) {
          if (item is List && item.length >= 2) {
            final lon = (item[0] as num?)?.toDouble();
            final lat = (item[1] as num?)?.toDouble();

            if (lat != null && lon != null) {
              points.add(
                LatLng(lat, lon),
              );
            }
          }
        }
      }
    }

    return RedZone(
      primaryHazard:
          properties['primary_hazard']?.toString() ?? 'unknown',
      riskScore:
          ((properties['risk_score'] as num?)?.toDouble() ?? 0) * 100,
      colorTier:
          properties['color_tier']?.toString().toLowerCase() ?? 'orange',
      points: points,
    );
  }

  Color get color {
    switch (colorTier) {
      case 'red':
        return red;
      case 'yellow':
        return yellow;
      case 'green':
        return green;
      default:
        return orange;
    }
  }
}

class RiskMapApi {
  static Uri uri(String path) {
    return Uri.parse('$backendBaseUrl$path');
  }

  static Future<bool> healthCheck() async {
    try {
      final response = await http
          .get(
            uri('/health'),
            headers: {
              'Accept': 'application/json',
            },
          )
          .timeout(
            const Duration(seconds: 45),
          );

      return response.statusCode >= 200 &&
          response.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  static Future<List<RedZone>> fetchRedZones() async {
    Object? lastError;

    // Render can take time to wake up from sleep.
    // Try twice before declaring the backend unavailable.
    for (int attempt = 1; attempt <= 2; attempt++) {
      try {
        final response = await http
            .get(
              uri('/red-zones/'),
              headers: {
                'Accept': 'application/json',
              },
            )
            .timeout(
              const Duration(seconds: 45),
            );

        if (response.statusCode < 200 ||
            response.statusCode >= 300) {
          throw Exception(
            'Backend returned HTTP ${response.statusCode}: ${response.body}',
          );
        }

        final decoded = jsonDecode(response.body);

        if (decoded is! Map) {
          throw Exception(
            'Invalid response format from backend.',
          );
        }

        final features = decoded['features'];

        if (features is! List) {
          throw Exception(
            'Backend response does not contain a valid "features" list.',
          );
        }

        final zones = features
            .whereType<Map>()
            .map(
              (feature) => RedZone.fromJson(
                feature.cast<String, dynamic>(),
              ),
            )
            .where(
              (zone) => zone.points.length >= 3,
            )
            .toList();

        return zones;
      } catch (e) {
        lastError = e;

        if (attempt < 2) {
          await Future.delayed(
            const Duration(seconds: 2),
          );
        }
      }
    }

    throw Exception(
      'Unable to reach DISHA backend after retries: $lastError',
    );
  }
}
class RiskMapScreen extends StatefulWidget {
  const RiskMapScreen({
    super.key,
  });

  @override
  State<RiskMapScreen> createState() => _RiskMapScreenState();
}

class _RiskMapScreenState extends State<RiskMapScreen> {
  final MapController mapController = MapController();

  Habitation? selected;

  String activeLayer = 'RISK';

  late Future<List<RedZone>> _redZonesFuture;

  bool backendOnline = false;

  // ===========================================================================
  // DEMO HABITATIONS
  // ===========================================================================

  final List<Habitation> habitations = const [
    Habitation(
      name: 'Borigaon',
      district: 'Assam',
      type: 'Vulnerable Habitation',
      lat: 26.304,
      lon: 92.620,
      population: 1240,
      vulnerability: 82,
      riskScore: 91,
      floodRisk: 68,
      landslideRisk: 54,
      infrastructureRisk: 76,
      risk: 91,
      relocationRequired: true,
    ),
    Habitation(
      name: 'North Borigaon',
      district: 'Assam',
      type: 'Rural Settlement',
      lat: 26.335,
      lon: 92.655,
      population: 820,
      vulnerability: 67,
      riskScore: 78,
      floodRisk: 72,
      landslideRisk: 42,
      infrastructureRisk: 64,
      risk: 78,
      relocationRequired: true,
    ),
    Habitation(
      name: 'River Belt Colony',
      district: 'Assam',
      type: 'Flood-Prone Habitation',
      lat: 26.265,
      lon: 92.590,
      population: 560,
      vulnerability: 58,
      riskScore: 64,
      floodRisk: 84,
      landslideRisk: 28,
      infrastructureRisk: 51,
      risk: 64,
      relocationRequired: true,
    ),
    Habitation(
      name: 'Hill Edge Hamlet',
      district: 'Assam',
      type: 'Hillside Habitation',
      lat: 26.375,
      lon: 92.570,
      population: 410,
      vulnerability: 43,
      riskScore: 48,
      floodRisk: 32,
      landslideRisk: 71,
      infrastructureRisk: 39,
      risk: 48,
      relocationRequired: false,
    ),
  ];

  // ===========================================================================
  // DEMO RELOCATION SITES
  //
  // IMPORTANT:
  // RelocationSite does not contain lat/lon.
  // Coordinates are provided by siteCoordinate() below.
  // ===========================================================================

  final List<RelocationSite> relocationSites = const [
    RelocationSite(
      name: 'Relief Zone Alpha',
      type: 'Emergency Relief Zone',
      capacity: 1850,
      currentPopulation: 1240,
      distance: 3.4,
      elevation: 42,
      suitability: 94,
      access: 'Excellent',
      safety: 'Very High',
    ),
    RelocationSite(
      name: 'Community Ground Beta',
      type: 'Community Relocation Site',
      capacity: 1420,
      currentPopulation: 820,
      distance: 4.8,
      elevation: 35,
      suitability: 87,
      access: 'Good',
      safety: 'High',
    ),
    RelocationSite(
      name: 'Highland Shelter Gamma',
      type: 'Highland Shelter',
      capacity: 2200,
      currentPopulation: 560,
      distance: 8.2,
      elevation: 68,
      suitability: 81,
      access: 'Moderate',
      safety: 'Very High',
    ),
  ];

  // ===========================================================================
  // RELOCATION SITE MAP COORDINATES
  // ===========================================================================

  LatLng siteCoordinate(String name) {
    switch (name) {
      case 'Relief Zone Alpha':
        return const LatLng(26.345, 92.690);

      case 'Community Ground Beta':
        return const LatLng(26.285, 92.675);

      case 'Highland Shelter Gamma':
        return const LatLng(26.410, 92.610);

      default:
        return const LatLng(26.300, 92.620);
    }
  }

  @override
  void initState() {
    super.initState();
    _loadBackendData();
  }

  void _loadBackendData() {
  _redZonesFuture = RiskMapApi.fetchRedZones().then(
    (zones) {
      if (mounted) {
        setState(() {
          backendOnline = true;
        });
      }

      return zones;
    },
  ).catchError((error) {
    if (mounted) {
      setState(() {
        backendOnline = false;
      });
    }

    throw error;
  });
}
  void _refresh() {
    setState(() {
      _loadBackendData();
    });
  }

  List<RedZone> _visibleZones(
    List<RedZone> zones,
  ) {
    if (activeLayer == 'FLOOD') {
      return zones
          .where(
            (zone) => zone.primaryHazard
                .toLowerCase()
                .contains('flood'),
          )
          .toList();
    }

    if (activeLayer == 'LANDSLIDE') {
      return zones
          .where(
            (zone) => zone.primaryHazard
                .toLowerCase()
                .contains('landslide'),
          )
          .toList();
    }

    if (activeLayer == 'RELOCATION') {
      return const [];
    }

    return zones;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      body: Stack(
        children: [
          // ===================================================================
          // MAP
          // ===================================================================

          FlutterMap(
            mapController: mapController,
            options: const MapOptions(
              initialCenter: LatLng(26.30, 92.62),
              initialZoom: 9.3,
              minZoom: 6,
              maxZoom: 16,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.disha.safety',
              ),

              // ===============================================================
              // BACKEND RED ZONES
              // ===============================================================

              FutureBuilder<List<RedZone>>(
                future: _redZonesFuture,
                builder: (
                  context,
                  snapshot,
                ) {
                  if (!snapshot.hasData) {
                    return const SizedBox.shrink();
                  }

                  final zones = _visibleZones(
                    snapshot.data!,
                  );

                  return PolygonLayer(
                    polygons: zones.map<Polygon<Object>>(
                      (zone) {
                        return Polygon<Object>(
                          points: zone.points,
                          color: zone.color.withOpacity(.18),
                          borderColor:
                              zone.color.withOpacity(.75),
                          borderStrokeWidth: 2.0,
                          label:
                              '${zone.primaryHazard} ${zone.riskScore.round()}',
                          labelStyle: TextStyle(
                            color: zone.color,
                            fontSize: 9,
                            fontWeight: FontWeight.w800,
                          ),
                        );
                      },
                    ).toList(),
                  );
                },
              ),

              // ===============================================================
              // HABITATION MARKERS
              // ===============================================================

              if (activeLayer != 'RELOCATION')
                MarkerLayer(
                  markers: habitations.map(
                    (habitation) {
                      final level = riskLevelFromScore(
                        habitation.riskScore,
                      );

                      return Marker(
                        point: LatLng(
                          habitation.lat,
                          habitation.lon,
                        ),
                        width: 40,
                        height: 40,
                        child: GestureDetector(
                          onTap: () {
                            setState(() {
                              selected = habitation;
                            });
                          },
                          child: _LargeMapMarker(
                            color: riskColor(level),
                            score:
                                habitation.riskScore.round(),
                          ),
                        ),
                      );
                    },
                  ).toList(),
                ),

              // ===============================================================
              // RELOCATION SITE MARKERS
              // ===============================================================

              if (activeLayer == 'RELOCATION')
                MarkerLayer(
                  markers: relocationSites.map(
                    (site) {
                      final coordinate =
                          siteCoordinate(site.name);

                      return Marker(
                        point: coordinate,
                        width: 34,
                        height: 34,
                        child: GestureDetector(
                          onTap: () {
                            _showRelocationSite(site);
                          },
                          child: Container(
                            decoration: BoxDecoration(
                              color: cyan.withOpacity(.18),
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: cyan,
                                width: 2,
                              ),
                            ),
                            child: const Icon(
                              Icons.home_work_outlined,
                              color: cyan,
                              size: 17,
                            ),
                          ),
                        ),
                      );
                    },
                  ).toList(),
                ),
            ],
          ),

          // ===================================================================
          // TOP BAR
          // ===================================================================

          Positioned(
            top: 12,
            left: 14,
            right: 14,
            child: Row(
              children: [
                _MapTopButton(
                  icon: Icons.arrow_back,
                  onTap: () =>
                      Navigator.maybePop(context),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 11,
                    ),
                    decoration: BoxDecoration(
                      color:
                          Colors.black.withOpacity(.78),
                      borderRadius:
                          BorderRadius.circular(14),
                      border: Border.all(
                        color:
                            Colors.white.withOpacity(.1),
                      ),
                    ),
                    child: const Row(
                      children: [
                        Icon(
                          Icons.radar,
                          color: cyan,
                          size: 17,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'MULTI-HAZARD RISK MAP',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                            letterSpacing: .5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                _MapTopButton(
                  icon: Icons.my_location,
                  onTap: () {
                    mapController.move(
                      const LatLng(26.30, 92.62),
                      9.3,
                    );
                  },
                ),
                const SizedBox(width: 7),
                _MapTopButton(
                  icon: Icons.refresh,
                  onTap: _refresh,
                ),
              ],
            ),
          ),

          // ===================================================================
          // DISPATCH BANNER
          // ===================================================================
          Positioned(
            top: 78,
            left: 14,
            right: 14,
            child: GestureDetector(
              onTap: () {
                // Not ideal hardcoded navigation, but for demo works to nudge user to the Report tab
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFA726).withOpacity(0.9),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFFA726)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: Colors.black, size: 20),
                    SizedBox(width: 8),
                    Text(
                      'FIELD OPERATIONS: Check Report Tab for Tasking',
                      style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 11),
                    )
                  ],
                ),
              ),
            ),
          ),

          // ===================================================================
          // LAYER CHIPS
          // ===================================================================

          Positioned(
            top: 130, // Shifted down to make room for dispatch banner
            left: 14,
            right: 14,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _LayerChip(
                    label: 'RISK',
                    icon: Icons.radar,
                    active: activeLayer == 'RISK',
                    onTap: () {
                      setState(() {
                        activeLayer = 'RISK';
                        selected = null;
                      });
                    },
                  ),
                  const SizedBox(width: 7),
                  _LayerChip(
                    label: 'FLOOD',
                    icon: Icons.water,
                    active: activeLayer == 'FLOOD',
                    onTap: () {
                      setState(() {
                        activeLayer = 'FLOOD';
                        selected = null;
                      });
                    },
                  ),
                  const SizedBox(width: 7),
                  _LayerChip(
                    label: 'LANDSLIDE',
                    icon: Icons.terrain,
                    active:
                        activeLayer == 'LANDSLIDE',
                    onTap: () {
                      setState(() {
                        activeLayer = 'LANDSLIDE';
                        selected = null;
                      });
                    },
                  ),
                  const SizedBox(width: 7),
                  _LayerChip(
                    label: 'RELOCATION',
                    icon: Icons.home_work,
                    active:
                        activeLayer == 'RELOCATION',
                    onTap: () {
                      setState(() {
                        activeLayer = 'RELOCATION';
                        selected = null;
                      });
                    },
                  ),
                ],
              ),
            ),
          ),

          // ===================================================================
          // BACKEND STATUS
          // ===================================================================

          Positioned(
            left: 14,
            top: 126,
            child: FutureBuilder<List<RedZone>>(
              future: _redZonesFuture,
              builder: (
                context,
                snapshot,
              ) {
                final loading =
                    snapshot.connectionState ==
                        ConnectionState.waiting;

                final connected =
                    snapshot.hasData &&
                        !snapshot.hasError;

                final statusColor = loading
                    ? yellow
                    : connected
                        ? green
                        : red;

                final statusText = loading
                    ? 'SYNCING BACKEND'
                    : connected
                        ? 'BACKEND • ${snapshot.data!.length} RED ZONES'
                        : 'BACKEND OFFLINE • DEMO MARKERS';

                return Container(
                  padding:
                      const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 7,
                  ),
                  decoration: BoxDecoration(
                    color:
                        Colors.black.withOpacity(.82),
                    borderRadius:
                        BorderRadius.circular(10),
                    border: Border.all(
                      color:
                          statusColor.withOpacity(.25),
                    ),
                  ),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 4,
                        backgroundColor:
                            statusColor,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        statusText,
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 8,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),

          // ===================================================================
          // BOTTOM API STATUS
          // ===================================================================

          Positioned(
            bottom:
                selected == null ? 18 : 290,
            left: 14,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(
                horizontal: 11,
                vertical: 8,
              ),
              decoration: BoxDecoration(
                color:
                    Colors.black.withOpacity(.8),
                borderRadius:
                    BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 4,
                    backgroundColor:
                        backendOnline
                            ? green
                            : orange,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    backendOnline
                        ? 'API CONNECTED • $activeLayer'
                        : 'DEMO FALLBACK • $activeLayer',
                    style: const TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ),

          // ===================================================================
          // BACKEND ERROR
          // ===================================================================

          Positioned(
            top: 165,
            left: 14,
            right: 14,
            child: FutureBuilder<List<RedZone>>(
              future: _redZonesFuture,
              builder: (
                context,
                snapshot,
              ) {
                if (!snapshot.hasError) {
                  return const SizedBox.shrink();
                }

                return Container(
                  padding:
                      const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: red.withOpacity(.10),
                    borderRadius:
                        BorderRadius.circular(10),
                    border: Border.all(
                      color: red.withOpacity(.25),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.cloud_off,
                        color: red,
                        size: 16,
                      ),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'Could not reach DISHA backend. Showing the existing demo habitation data.',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 9,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: _refresh,
                        child: const Text(
                          'RETRY',
                          style: TextStyle(
                            color: cyan,
                            fontSize: 9,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),

          // ===================================================================
          // SELECTED HABITATION
          // ===================================================================

          if (selected != null)
            Positioned(
              left: 10,
              right: 10,
              bottom: 10,
              child: _SelectedMapPanel(
                habitation: selected!,
                onClose: () {
                  setState(() {
                    selected = null;
                  });
                },
              ),
            ),
        ],
      ),
    );
  }

  // ===========================================================================
  // RELOCATION SITE DETAILS
  // ===========================================================================

  void _showRelocationSite(
    RelocationSite site,
  ) {
    showModalBottomSheet(
      context: context,
      backgroundColor: panel,
      isScrollControlled: true,
      builder: (context) {
        final coordinate =
            siteCoordinate(site.name);

        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: cyan.withOpacity(.12),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: cyan.withOpacity(.4),
                        ),
                      ),
                      child: const Icon(
                        Icons.home_work_outlined,
                        color: cyan,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          Text(
                            site.name,
                            style:
                                const TextStyle(
                              fontSize: 20,
                              fontWeight:
                                  FontWeight.w900,
                            ),
                          ),
                          Text(
                            site.type,
                            style:
                                const TextStyle(
                              color: muted,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      onPressed: () =>
                          Navigator.pop(context),
                      icon: const Icon(
                        Icons.close,
                        color: muted,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 20),

                Row(
                  children: [
                    Expanded(
                      child: _SiteMetric(
                        title: 'SUITABILITY',
                        value:
                            '${site.suitability.round()}%',
                        color: cyan,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _SiteMetric(
                        title: 'CAPACITY',
                        value:
                            '${site.capacity}',
                        color: blue,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                Row(
                  children: [
                    Expanded(
                      child: _SiteMetric(
                        title: 'CURRENT',
                        value:
                            '${site.currentPopulation}',
                        color: orange,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _SiteMetric(
                        title: 'REMAINING',
                        value:
                            '${site.remainingCapacity}',
                        color: green,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                Row(
                  children: [
                    Expanded(
                      child: _SiteMetric(
                        title: 'DISTANCE',
                        value:
                            '${site.distance.toStringAsFixed(1)} km',
                        color: yellow,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _SiteMetric(
                        title: 'ELEVATION',
                        value:
                            '${site.elevation.toStringAsFixed(0)} m',
                        color: cyan,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 18),

                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.all(15),
                  decoration: BoxDecoration(
                    color: panel2,
                    borderRadius:
                        BorderRadius.circular(15),
                    border: Border.all(
                      color: border,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SITE ASSESSMENT',
                        style: TextStyle(
                          color: muted,
                          fontSize: 9,
                          fontWeight:
                              FontWeight.w900,
                          letterSpacing: .6,
                        ),
                      ),
                      const SizedBox(height: 12),
                      _SiteRow(
                        icon: Icons.route,
                        label: 'ACCESS',
                        value: site.access,
                      ),
                      const SizedBox(height: 10),
                      _SiteRow(
                        icon: Icons.shield_outlined,
                        label: 'SAFETY',
                        value: site.safety,
                      ),
                      const SizedBox(height: 10),
                      _SiteRow(
                        icon: Icons.location_on_outlined,
                        label: 'MAP POSITION',
                        value:
                            '${coordinate.latitude.toStringAsFixed(3)}, ${coordinate.longitude.toStringAsFixed(3)}',
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ============================================================================
// TOP BUTTON
// ============================================================================

class _MapTopButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _MapTopButton({
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 43,
        height: 43,
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(.78),
          borderRadius:
              BorderRadius.circular(13),
          border: Border.all(
            color:
                Colors.white.withOpacity(.12),
          ),
        ),
        child: Icon(
          icon,
          size: 19,
        ),
      ),
    );
  }
}

// ============================================================================
// LAYER CHIP
// ============================================================================

class _LayerChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool active;
  final VoidCallback onTap;

  const _LayerChip({
    required this.label,
    required this.icon,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding:
            const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 8,
        ),
        decoration: BoxDecoration(
          color: active
              ? cyan.withOpacity(.18)
              : Colors.black.withOpacity(.72),
          borderRadius:
              BorderRadius.circular(10),
          border: Border.all(
            color: active
                ? cyan.withOpacity(.55)
                : Colors.white12,
          ),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 13,
              color:
                  active ? cyan : Colors.white70,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w800,
                color: active
                    ? cyan
                    : Colors.white70,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================================
// MAP MARKER
// ============================================================================

class _LargeMapMarker extends StatelessWidget {
  final Color color;
  final int score;

  const _LargeMapMarker({
    required this.color,
    required this.score,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 29,
          height: 29,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(
              color: Colors.white,
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: color.withOpacity(.55),
                blurRadius: 12,
                spreadRadius: 3,
              ),
            ],
          ),
          child: Center(
            child: Text(
              '$score',
              style: const TextStyle(
                color: Colors.black,
                fontSize: 8,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// ============================================================================
// SELECTED HABITATION PANEL
// ============================================================================

class _SelectedMapPanel extends StatelessWidget {
  final Habitation habitation;
  final VoidCallback onClose;

  const _SelectedMapPanel({
    required this.habitation,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final level = riskLevelFromScore(
      habitation.riskScore,
    );

    final color = riskColor(level);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color:
            const Color(0xFF0B1721)
                .withOpacity(.97),
        borderRadius:
            BorderRadius.circular(20),
        border: Border.all(
          color: color.withOpacity(.4),
        ),
        boxShadow: const [
          BoxShadow(
            color: Colors.black54,
            blurRadius: 20,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 9,
                height: 48,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius:
                      BorderRadius.circular(5),
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment:
                      CrossAxisAlignment.start,
                  children: [
                    Text(
                      habitation.name,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight:
                            FontWeight.w900,
                      ),
                    ),
                    Text(
                      habitation.type,
                      style: const TextStyle(
                        color: muted,
                        fontSize: 10,
                      ),
                    ),
                  ],
                ),
              ),
              riskBadge(level),
              IconButton(
                onPressed: onClose,
                icon: const Icon(
                  Icons.close,
                  color: muted,
                  size: 18,
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),

          Row(
            children: [
              _SmallMetric(
                value:
                    '${habitation.population}',
                label: 'POPULATION',
              ),
              _SmallMetric(
                value:
                    '${habitation.vulnerability}%',
                label: 'VULNERABILITY',
              ),
              _SmallMetric(
                value:
                    '${habitation.riskScore.round()}',
                label: 'RISK SCORE',
              ),
            ],
          ),

          const SizedBox(height: 13),

          Row(
            children: [
              Expanded(
                child: _ActionButton(
                  label: 'INTELLIGENCE',
                  icon:
                      Icons.analytics_outlined,
                  onTap: () {
                    showModalBottomSheet(
                      context: context,
                      backgroundColor: panel,
                      isScrollControlled: true,
                      builder: (_) =>
                          HabitationDetails(
                        habitation: habitation,
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _ActionButton(
                  label: 'RELOCATION',
                  icon: Icons.directions_run,
                  primary: true,
                  onTap: () {
                    Navigator.pop(context);
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// SMALL METRIC
// ============================================================================

class _SmallMetric extends StatelessWidget {
  final String value;
  final String label;

  const _SmallMetric({
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: const TextStyle(
              color: muted,
              fontSize: 8,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// ACTION BUTTON
// ============================================================================

class _ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool primary;
  final VoidCallback onTap;

  const _ActionButton({
    required this.label,
    required this.icon,
    this.primary = false,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding:
            const EdgeInsets.symmetric(
          vertical: 11,
        ),
        decoration: BoxDecoration(
          color: primary
              ? cyan.withOpacity(.15)
              : panel2,
          borderRadius:
              BorderRadius.circular(11),
          border: Border.all(
            color: primary
                ? cyan.withOpacity(.4)
                : border,
          ),
        ),
        child: Row(
          mainAxisAlignment:
              MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 14,
              color: primary
                  ? cyan
                  : Colors.white70,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: primary
                    ? cyan
                    : Colors.white70,
                fontSize: 9,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================================
// HABITATION DETAILS
// ============================================================================

class HabitationDetails extends StatelessWidget {
  final Habitation habitation;

  const HabitationDetails({
    super.key,
    required this.habitation,
  });

  @override
  Widget build(BuildContext context) {
    final level = riskLevelFromScore(
      habitation.riskScore,
    );

    final color = riskColor(level);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment:
              CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text(
                        habitation.name,
                        style:
                            const TextStyle(
                          fontSize: 22,
                          fontWeight:
                              FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${habitation.district} • ${habitation.type}',
                        style:
                            const TextStyle(
                          color: muted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                riskBadge(level),
              ],
            ),

            const SizedBox(height: 20),

            Row(
              children: [
                Expanded(
                  child: _DetailMetric(
                    title: 'RISK',
                    value:
                        '${habitation.riskScore.round()}%',
                    color: color,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _DetailMetric(
                    title: 'VULNERABILITY',
                    value:
                        '${habitation.vulnerability.round()}%',
                    color: orange,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 10),

            Row(
              children: [
                Expanded(
                  child: _DetailMetric(
                    title: 'FLOOD',
                    value:
                        '${habitation.floodRisk.round()}%',
                    color: blue,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _DetailMetric(
                    title: 'LANDSLIDE',
                    value:
                        '${habitation.landslideRisk.round()}%',
                    color: yellow,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 10),

            Row(
              children: [
                Expanded(
                  child: _DetailMetric(
                    title: 'INFRASTRUCTURE',
                    value:
                        '${habitation.infrastructureRisk.round()}%',
                    color: orange,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _DetailMetric(
                    title: 'POPULATION',
                    value:
                        '${habitation.population}',
                    color: cyan,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),

            Container(
              width: double.infinity,
              padding:
                  const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: panel2,
                borderRadius:
                    BorderRadius.circular(16),
                border: Border.all(
                  color: border,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    habitation.relocationRequired
                        ? Icons.directions_run
                        : Icons.check_circle_outline,
                    color:
                        habitation.relocationRequired
                            ? red
                            : green,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      habitation.relocationRequired
                          ? 'Immediate relocation assessment recommended.'
                          : 'No immediate relocation requirement.',
                      style:
                          const TextStyle(
                        fontSize: 12,
                        fontWeight:
                            FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================================
// DETAIL METRIC
// ============================================================================

class _DetailMetric extends StatelessWidget {
  final String title;
  final String value;
  final Color color;

  const _DetailMetric({
    required this.title,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: panel,
        borderRadius:
            BorderRadius.circular(15),
        border: Border.all(
          color: border,
        ),
      ),
      child: Column(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: muted,
              fontSize: 9,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 21,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// RELOCATION SITE METRIC
// ============================================================================

class _SiteMetric extends StatelessWidget {
  final String title;
  final String value;
  final Color color;

  const _SiteMetric({
    required this.title,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: panel2,
        borderRadius:
            BorderRadius.circular(14),
        border: Border.all(
          color: border,
        ),
      ),
      child: Column(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: muted,
              fontSize: 8,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// RELOCATION SITE ROW
// ============================================================================

class _SiteRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _SiteRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          icon,
          color: cyan,
          size: 17,
        ),
        const SizedBox(width: 9),
        Text(
          label,
          style: const TextStyle(
            color: muted,
            fontSize: 9,
            fontWeight: FontWeight.w800,
          ),
        ),
        const Spacer(),
        Text(
          value,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}