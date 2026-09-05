import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../services/risk_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static const Color background = Color(0xFF071016);
  static const Color panel = Color(0xFF0B151C);
  static const Color border = Color(0xFF18333D);
  static const Color cyan = Color(0xFF20D9FF);

  bool _loading = true;
  String? _error;

  List<_RiskZone> _zones = [];

  int get _criticalCount =>
      _zones.where((zone) => zone.risk >= 0.80).length;

  int get _highCount =>
      _zones.where((zone) => zone.risk >= 0.60 && zone.risk < 0.80).length;

  int get _atRiskCount =>
      _zones.where((zone) => zone.risk >= 0.40).length;

  @override
  void initState() {
    super.initState();
    _loadRiskZones();
  }

  Future<void> _loadRiskZones() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final response = await RiskService.getRedZones();

      final zones = _parseZones(response);

      if (!mounted) return;

      setState(() {
        _zones = zones;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = 'Unable to connect to risk intelligence backend.';
      });
    }
  }

  List<_RiskZone> _parseZones(dynamic response) {
    final result = <_RiskZone>[];

    if (response is! Map<String, dynamic>) {
      return result;
    }

    final features = response['features'];

    if (features is! List) {
      return result;
    }

    for (var i = 0; i < features.length; i++) {
      final feature = features[i];

      if (feature is! Map) continue;

      final geometry = feature['geometry'];

      if (geometry is! Map) continue;

      final coordinates = geometry['coordinates'];

      if (coordinates is! List) continue;

      final properties = feature['properties'];

      final props = properties is Map ? properties : {};

      final risk = _number(
        props['risk'] ??
            props['risk_score'] ??
            props['riskScore'] ??
            props['score'],
      );

      final hazard =
        props['primary_hazard']?.toString() ??
        props['hazard']?.toString() ??
        props['hazard_type']?.toString() ??
        props['type']?.toString() ??
        'Hazard';

      final name =
          props['name']?.toString() ??
          props['habitation']?.toString() ??
          'Risk Zone ${i + 1}';

      final polygons = _extractPolygonCoordinates(
        geometry['type']?.toString() ?? '',
        coordinates,
      );

      for (final polygon in polygons) {
        if (polygon.length < 3) continue;

        final points = <LatLng>[];

        for (final coordinate in polygon) {
          if (coordinate is! List || coordinate.length < 2) continue;

          final lon = _number(coordinate[0]);
          final lat = _number(coordinate[1]);

          if (lat.abs() > 90 || lon.abs() > 180) continue;

          points.add(LatLng(lat, lon));
        }

        if (points.length >= 3) {
          result.add(
            _RiskZone(
              name: name,
              hazard: hazard,
              risk: risk,
              points: points,
            ),
          );
        }
      }
    }

    return result;
  }

  List<List<dynamic>> _extractPolygonCoordinates(
    String geometryType,
    dynamic coordinates,
  ) {
    if (geometryType == 'Polygon') {
      if (coordinates is List && coordinates.isNotEmpty) {
        final outerRing = coordinates.first;

        if (outerRing is List) {
          return [outerRing];
        }
      }
    }

    if (geometryType == 'MultiPolygon') {
      final result = <List<dynamic>>[];

      if (coordinates is List) {
        for (final polygon in coordinates) {
          if (polygon is List && polygon.isNotEmpty) {
            final outerRing = polygon.first;

            if (outerRing is List) {
              result.add(outerRing);
            }
          }
        }
      }

      return result;
    }

    return [];
  }

  double _number(dynamic value) {
    if (value is num) {
      return value.toDouble();
    }

    return double.tryParse(value?.toString() ?? '') ?? 0;
  }

  Color _riskColor(double risk) {
    if (risk >= 0.80) {
      return Colors.redAccent;
    }

    if (risk >= 0.60) {
      return Colors.orangeAccent;
    }

    if (risk >= 0.40) {
      return Colors.amber;
    }

    return Colors.greenAccent;
  }

  String _riskLabel(double risk) {
    if (risk >= 0.80) return 'CRITICAL';
    if (risk >= 0.60) return 'HIGH';
    if (risk >= 0.40) return 'AT RISK';
    return 'MONITOR';
  }

  LatLng _mapCenter() {
    if (_zones.isEmpty) {
      return const LatLng(26.2006, 92.9376);
    }

    final points = _zones.expand((zone) => zone.points).toList();

    if (points.isEmpty) {
      return const LatLng(26.2006, 92.9376);
    }

    var lat = 0.0;
    var lon = 0.0;

    for (final point in points) {
      lat += point.latitude;
      lon += point.longitude;
    }

    return LatLng(
      lat / points.length,
      lon / points.length,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: background,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadRiskZones,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: _buildHeader(),
              ),
              SliverToBoxAdapter(
                child: _buildStatus(),
              ),
              SliverToBoxAdapter(
                child: _buildMap(),
              ),
              SliverToBoxAdapter(
                child: _buildStats(),
              ),
              SliverToBoxAdapter(
                child: _buildPrioritySection(),
              ),
              const SliverToBoxAdapter(
                child: SizedBox(height: 24),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 10),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: cyan.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: cyan.withValues(alpha: 0.35),
              ),
            ),
            child: const Icon(
              Icons.shield_outlined,
              color: cyan,
              size: 27,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'DISHA',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.5,
                  ),
                ),
                Text(
                  'HABITATION RISK INTELLIGENCE',
                  style: TextStyle(
                    color: Colors.white54,
                    fontSize: 9,
                    letterSpacing: 1.1,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: _loadRiskZones,
            icon: const Icon(
              Icons.refresh_rounded,
              color: Colors.white70,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatus() {
    final online = !_loading && _error == null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 9,
        ),
        decoration: BoxDecoration(
          color: panel,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: border),
        ),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: online ? Colors.greenAccent : Colors.redAccent,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              online ? 'RISK INTELLIGENCE ONLINE' : 'BACKEND OFFLINE',
              style: TextStyle(
                color: online ? Colors.greenAccent : Colors.redAccent,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.7,
              ),
            ),
            const Spacer(),
            Text(
              _loading ? 'SYNCING...' : 'SYNC READY',
              style: const TextStyle(
                color: Colors.white38,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMap() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 14),
      child: Container(
        height: 390,
        decoration: BoxDecoration(
          color: panel,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: border),
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(
          children: [
            FlutterMap(
              options: MapOptions(
                initialCenter: _mapCenter(),
                initialZoom: 7.0,
              ),
              children: [
                TileLayer(
                  urlTemplate:
                      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.disha.sar_app',
                ),
                PolygonLayer(
                  polygons: _zones.map((zone) {
                    final color = _riskColor(zone.risk);

                    return Polygon(
                      points: zone.points,
                      color: color.withValues(alpha: 0.28),
                      borderColor: color,
                      borderStrokeWidth: 2.5,
                    );
                  }).toList(),
                ),
                MarkerLayer(
                  markers: _zones.map((zone) {
                    final center = _centerOf(zone.points);
                    final color = _riskColor(zone.risk);

                    return Marker(
                      point: center,
                      width: 62,
                      height: 62,
                      child: GestureDetector(
                        onTap: () {
                          _showZone(zone);
                        },
                        child: Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: color.withValues(alpha: 0.18),
                            border: Border.all(
                              color: color,
                              width: 2,
                            ),
                          ),
                          child: Center(
                            child: Container(
                              width: 26,
                              height: 26,
                              decoration: BoxDecoration(
                                color: color,
                                shape: BoxShape.circle,
                              ),
                              child: Center(
                                child: Text(
                                  '${(zone.risk * 100).round()}',
                                  style: const TextStyle(
                                    color: Colors.black,
                                    fontSize: 9,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),

            Positioned(
              left: 14,
              top: 14,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: background.withValues(alpha: 0.90),
                  borderRadius: BorderRadius.circular(9),
                  border: Border.all(color: border),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.radar_rounded,
                      color: cyan,
                      size: 16,
                    ),
                    SizedBox(width: 6),
                    Text(
                      'LIVE RISK MAP',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.7,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            Positioned(
              right: 12,
              bottom: 12,
              child: Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: background.withValues(alpha: 0.90),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _legendItem(
                      Colors.redAccent,
                      'Critical',
                    ),
                    _legendItem(
                      Colors.orangeAccent,
                      'High',
                    ),
                    _legendItem(
                      Colors.amber,
                      'At risk',
                    ),
                  ],
                ),
              ),
            ),

            if (_loading)
              Container(
                color: background.withValues(alpha: 0.55),
                child: const Center(
                  child: CircularProgressIndicator(
                    color: cyan,
                  ),
                ),
              ),

            if (_error != null && !_loading)
              Center(
                child: Container(
                  margin: const EdgeInsets.all(25),
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: background.withValues(alpha: 0.95),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: Colors.redAccent.withValues(alpha: 0.4),
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.cloud_off_rounded,
                        color: Colors.redAccent,
                        size: 32,
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Risk backend unavailable',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 5),
                      const Text(
                        'Check that the FastAPI server is running.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 12),
                      FilledButton.icon(
                        onPressed: _loadRiskZones,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _legendItem(Color color, String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 9,
            ),
          ),
        ],
      ),
    );
  }

  LatLng _centerOf(List<LatLng> points) {
    var lat = 0.0;
    var lon = 0.0;

    for (final point in points) {
      lat += point.latitude;
      lon += point.longitude;
    }

    return LatLng(
      lat / points.length,
      lon / points.length,
    );
  }

  Widget _buildStats() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Row(
        children: [
          Expanded(
            child: _statCard(
              'CRITICAL',
              _criticalCount.toString(),
              Colors.redAccent,
              Icons.warning_rounded,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _statCard(
              'HIGH',
              _highCount.toString(),
              Colors.orangeAccent,
              Icons.priority_high_rounded,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _statCard(
              'AT RISK',
              _atRiskCount.toString(),
              Colors.amber,
              Icons.location_on_outlined,
            ),
          ),
        ],
      ),
    );
  }

  Widget _statCard(
    String title,
    String value,
    Color color,
    IconData icon,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
      ),
      child: Column(
        children: [
          Icon(
            icon,
            color: color,
            size: 20,
          ),
          const SizedBox(height: 7),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 21,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: const TextStyle(
              color: Colors.white54,
              fontSize: 8,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPrioritySection() {
    final sorted = [..._zones]
      ..sort((a, b) => b.risk.compareTo(a.risk));

    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 22, 18, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'PRIORITY HABITATIONS',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Highest-risk zones requiring attention',
            style: TextStyle(
              color: Colors.white38,
              fontSize: 10,
            ),
          ),
          const SizedBox(height: 12),
          if (sorted.isEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: panel,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: border),
              ),
              child: const Text(
                'No risk zones returned by the backend.',
                style: TextStyle(
                  color: Colors.white54,
                ),
              ),
            )
          else
            ...sorted.take(5).map(_priorityCard),
        ],
      ),
    );
  }

  Widget _priorityCard(_RiskZone zone) {
    final color = _riskColor(zone.risk);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(
              Icons.location_on_rounded,
              color: color,
              size: 22,
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  zone.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  zone.hazard,
                  style: const TextStyle(
                    color: Colors.white38,
                    fontSize: 10,
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${(zone.risk * 100).round()}%',
                style: TextStyle(
                  color: color,
                  fontWeight: FontWeight.w900,
                  fontSize: 17,
                ),
              ),
              Text(
                _riskLabel(zone.risk),
                style: TextStyle(
                  color: color,
                  fontSize: 8,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showZone(_RiskZone zone) {
    final color = _riskColor(zone.risk);

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: panel,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 5, 20, 25),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.warning_rounded,
                      color: color,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        zone.name,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 15),
                _detailRow(
                  'Hazard',
                  zone.hazard,
                ),
                _detailRow(
                  'Risk score',
                  '${(zone.risk * 100).round()}%',
                ),
                _detailRow(
                  'Priority',
                  _riskLabel(zone.risk),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Colors.white54,
              fontSize: 12,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskZone {
  final String name;
  final String hazard;
  final double risk;
  final List<LatLng> points;

  const _RiskZone({
    required this.name,
    required this.hazard,
    required this.risk,
    required this.points,
  });
}