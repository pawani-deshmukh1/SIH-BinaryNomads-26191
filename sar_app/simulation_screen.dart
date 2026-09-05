import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'api_service.dart';

class SimulationScreen extends StatefulWidget {
  const SimulationScreen({super.key});

  @override
  State<SimulationScreen> createState() => _SimulationScreenState();
}

class _SimulationScreenState extends State<SimulationScreen> {
  double population = 1240.0;
  double availableCapacity = 1850.0;
  double evacuationTime = 35.0;
  double routeAvailability = 82.0;
  double emergencyResources = 75.0;

  double occupancy = 0.67;
  double estimatedEvacuationTime = 35.0;
  String operationalStatus = 'STABLE';

  bool simulationRunning = false;
  bool simulationComplete = false;

  @override
  void initState() {
    super.initState();
    _fetchDefaults();
  }

  Future<void> _fetchDefaults() async {
    try {
      final response = await ApiService.get('/simulation/2d/Borigaon');
      if (response != null) {
        setState(() {
          population = (response['population'] as num).toDouble();
          availableCapacity = (response['availableCapacity'] as num).toDouble();
          evacuationTime = (response['evacuationTime'] as num).toDouble();
          routeAvailability = (response['routeAvailability'] as num).toDouble();
          emergencyResources = (response['emergencyResources'] as num).toDouble();
        });
        _runSimulation(); // run initial math
      }
    } catch (e) {
      debugPrint('Error fetching simulation defaults: $e');
    }
  }

  Color get statusColor {
    switch (operationalStatus) {
      case 'CRITICAL':
        return const Color(0xFFFF5D6C);
      case 'WARNING':
        return const Color(0xFFFFA63D);
      default:
        return const Color(0xFF35E39A);
    }
  }

  Future<void> _runSimulation() async {
    if (simulationRunning) {
      return;
    }

    setState(() {
      simulationRunning = true;
      simulationComplete = false;
    });

    try {
      final response = await http.post(
        Uri.parse('${ApiService.baseUrl}/simulation/2d/Borigaon'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'population': population,
          'capacity': availableCapacity,
          'evacuationTime': evacuationTime,
          'routeAvailability': routeAvailability,
          'emergencyResources': emergencyResources,
        }),
      );

      if (!mounted) return;

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(response.body);
        final results = data['results'];
        setState(() {
          occupancy = (results['occupancy_pct'] as num).toDouble();
          estimatedEvacuationTime = (results['estimated_evacuation_time'] as num).toDouble();
          operationalStatus = results['operational_status'] as String;
          
          simulationRunning = false;
          simulationComplete = true;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: Color(0xFF111F28),
            content: Text(
              'Simulation completed successfully.',
              style: TextStyle(color: Colors.white),
            ),
          ),
        );
      } else {
        throw Exception('Simulation failed');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        simulationRunning = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: const Color(0xFFFF5D6C),
          content: Text('Simulation error: $e'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    const Color background = Color(0xFF071016);
    const Color panel = Color(0xFF0D1921);
    const Color panel2 = Color(0xFF111F28);
    const Color border = Color(0xFF20323D);
    const Color cyan = Color(0xFF20D9FF);
    const Color green = Color(0xFF35E39A);
    const Color orange = Color(0xFFFFA63D);
    const Color muted = Color(0xFF81909A);

    return Scaffold(
      backgroundColor: background,
      appBar: AppBar(
        backgroundColor: background,
        elevation: 0,
        titleSpacing: 18,
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'COP & SIMULATION',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
              ),
            ),
            SizedBox(height: 3),
            Text(
              'Common operational picture',
              style: TextStyle(
                color: Color(0xFF81909A),
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            16,
            8,
            16,
            30,
          ),
          children: [
            _statusCard(
              panel: panel,
              statusColor: statusColor,
              muted: muted,
            ),
            const SizedBox(height: 20),
            _sectionTitle(
              'SIMULATION PARAMETERS',
              cyan,
            ),
            const SizedBox(height: 10),

            _sliderCard(
              title: 'Population to evacuate',
              displayValue: population.round().toString(),
              subtitle: 'people',
              min: 100.0,
              max: 2500.0,
              sliderValue: population,
              color: cyan,
              panel: panel,
              border: border,
              onChanged: (newValue) {
                setState(() {
                  population = newValue;
                });
              },
            ),

            _sliderCard(
              title: 'Available site capacity',
              displayValue: availableCapacity.round().toString(),
              subtitle: 'people',
              min: 500.0,
              max: 3000.0,
              sliderValue: availableCapacity,
              color: green,
              panel: panel,
              border: border,
              onChanged: (newValue) {
                setState(() {
                  availableCapacity = newValue;
                });
              },
            ),

            _sliderCard(
              title: 'Base evacuation time',
              displayValue: evacuationTime.round().toString(),
              subtitle: 'minutes',
              min: 10.0,
              max: 120.0,
              sliderValue: evacuationTime,
              color: orange,
              panel: panel,
              border: border,
              onChanged: (newValue) {
                setState(() {
                  evacuationTime = newValue;
                });
              },
            ),

            _sliderCard(
              title: 'Route availability',
              displayValue: '${routeAvailability.round()}%',
              subtitle: 'operational',
              min: 0.0,
              max: 100.0,
              sliderValue: routeAvailability,
              color: cyan,
              panel: panel,
              border: border,
              onChanged: (newValue) {
                setState(() {
                  routeAvailability = newValue;
                });
              },
            ),

            _sliderCard(
              title: 'Emergency resources',
              displayValue: '${emergencyResources.round()}%',
              subtitle: 'available',
              min: 0.0,
              max: 100.0,
              sliderValue: emergencyResources,
              color: green,
              panel: panel,
              border: border,
              onChanged: (newValue) {
                setState(() {
                  emergencyResources = newValue;
                });
              },
            ),

            const SizedBox(height: 12),

            _sectionTitle(
              'SIMULATION OUTPUT',
              cyan,
            ),

            const SizedBox(height: 10),

            _outputGrid(
              panel: panel,
              border: border,
              cyan: cyan,
              green: green,
              orange: orange,
            ),

            const SizedBox(height: 18),

            _operationalCard(
              panel: panel,
              color: statusColor,
              muted: muted,
            ),

            const SizedBox(height: 18),

            SizedBox(
              height: 52,
              child: ElevatedButton.icon(
                onPressed:
                    simulationRunning ? null : _runSimulation,
                icon: simulationRunning
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.black,
                        ),
                      )
                    : const Icon(
                        Icons.play_arrow_rounded,
                      ),
                label: Text(
                  simulationRunning
                      ? 'RUNNING SIMULATION...'
                      : 'RUN EVACUATION SIMULATION',
                  style: const TextStyle(
                    fontWeight: FontWeight.w900,
                    letterSpacing: .7,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: cyan,
                  foregroundColor: Colors.black,
                  disabledBackgroundColor:
                      cyan.withValues(alpha: 0.5),
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),

            if (simulationComplete) ...[
              const SizedBox(height: 14),
              _completeCard(
                panel: panel,
                green: green,
                muted: muted,
              ),
            ],

            const SizedBox(height: 18),

            _disclaimerCard(
              panel: panel2,
              border: border,
              muted: muted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(
    String title,
    Color color,
  ) {
    return Row(
      children: [
        Container(
          width: 4,
          height: 16,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          title,
          style: TextStyle(
            color: color,
            fontSize: 11,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.1,
          ),
        ),
      ],
    );
  }

  Widget _statusCard({
    required Color panel,
    required Color statusColor,
    required Color muted,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: statusColor.withValues(alpha: 0.35),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              Icons.monitor_heart_outlined,
              color: statusColor,
              size: 24,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Text(
                  'OPERATIONAL STATUS',
                  style: TextStyle(
                    color: muted,
                    fontSize: 8,
                    fontWeight: FontWeight.bold,
                    letterSpacing: .6,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  operationalStatus,
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .8,
                  ),
                ),
              ],
            ),
          ),
          Icon(
            Icons.circle,
            color: statusColor,
            size: 10,
          ),
        ],
      ),
    );
  }

  Widget _sliderCard({
    required String title,
    required String displayValue,
    required String subtitle,
    required double min,
    required double max,
    required double sliderValue,
    required Color color,
    required Color panel,
    required Color border,
    required ValueChanged<double> onChanged,
  }) {
    final double safeValue =
        sliderValue.clamp(min, max).toDouble();

    return Container(
      margin: const EdgeInsets.only(
        bottom: 10,
      ),
      padding: const EdgeInsets.fromLTRB(
        15,
        13,
        15,
        8,
      ),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: border,
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                displayValue,
                style: TextStyle(
                  color: color,
                  fontSize: 14,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                subtitle,
                style: const TextStyle(
                  color: Colors.white38,
                  fontSize: 8,
                ),
              ),
            ],
          ),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: color,
              inactiveTrackColor: Colors.white10,
              thumbColor: color,
              overlayColor: color.withValues(alpha: 0.10),
              trackHeight: 3,
            ),
            child: Slider(
              min: min,
              max: max,
              value: safeValue,
              onChanged: onChanged,
            ),
          ),
        ],
      ),
    );
  }

  Widget _outputGrid({
    required Color panel,
    required Color border,
    required Color cyan,
    required Color green,
    required Color orange,
  }) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _outputCard(
                title: 'OCCUPANCY',
                value:
                    '${(occupancy * 100).clamp(0.0, 999.0).toStringAsFixed(0)}%',
                icon: Icons.groups_outlined,
                color:
                    occupancy >= 0.90
                        ? const Color(0xFFFF5D6C)
                        : green,
                panel: panel,
                border: border,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _outputCard(
                title: 'EVACUATION',
                value:
                    '${estimatedEvacuationTime.toStringAsFixed(0)} min',
                icon: Icons.timer_outlined,
                color: orange,
                panel: panel,
                border: border,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _outputCard(
                title: 'ROUTE',
                value: '${routeAvailability.round()}%',
                icon: Icons.route_outlined,
                color: cyan,
                panel: panel,
                border: border,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _outputCard(
                title: 'RESOURCES',
                value: '${emergencyResources.round()}%',
                icon: Icons.inventory_2_outlined,
                color: green,
                panel: panel,
                border: border,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _outputCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    required Color panel,
    required Color border,
  }) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: border,
        ),
      ),
      child: Column(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            color: color,
            size: 20,
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 21,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            title,
            style: const TextStyle(
              color: Colors.white38,
              fontSize: 8,
              fontWeight: FontWeight.bold,
              letterSpacing: .5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _operationalCard({
    required Color panel,
    required Color color,
    required Color muted,
  }) {
    String message;

    switch (operationalStatus) {
      case 'CRITICAL':
        message =
            'Current parameters indicate a critical operational condition. Additional evacuation resources and route verification are recommended.';
        break;

      case 'WARNING':
        message =
            'Current parameters indicate a warning condition. Authorities should monitor capacity, route availability and emergency resources.';
        break;

      default:
        message =
            'Current parameters indicate a stable operational condition. The selected relocation scenario is within assessed limits.';
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: color.withValues(alpha: 0.30),
        ),
      ),
      child: Row(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.analytics_outlined,
            color: color,
            size: 22,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Text(
                  'SCENARIO ASSESSMENT',
                  style: TextStyle(
                    color: color,
                    fontSize: 9,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .7,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  message,
                  style: TextStyle(
                    color: muted,
                    fontSize: 10,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _completeCard({
    required Color panel,
    required Color green,
    required Color muted,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: green.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: green.withValues(alpha: 0.30),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.check_circle_outline,
            color: green,
            size: 20,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              'Simulation results generated from the selected scenario parameters.',
              style: TextStyle(
                color: muted,
                fontSize: 9,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _disclaimerCard({
    required Color panel,
    required Color border,
    required Color muted,
  }) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: border,
        ),
      ),
      child: Row(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.info_outline,
            color: muted,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Simulation outputs are decision-support estimates and should be validated against current field conditions before operational deployment.',
              style: TextStyle(
                color: muted,
                fontSize: 8,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}