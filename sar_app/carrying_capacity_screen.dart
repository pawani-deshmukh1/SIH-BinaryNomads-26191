import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class CarryingCapacityScreen extends StatefulWidget {
  const CarryingCapacityScreen({super.key});

  @override
  State<CarryingCapacityScreen> createState() =>
      _CarryingCapacityScreenState();
}

class _CarryingCapacityScreenState extends State<CarryingCapacityScreen> {
  String selectedSite = 'Relief Zone Alpha';

  bool _loading = true;
  String? _error;

  final List<_CapacitySite> sites = [
    _CapacitySite(
      name: 'Relief Zone Alpha',
      capacity: 1850,
      population: 1240,
      waterPerPerson: 15,
      foodPerPerson: 0.65,
      shelterUnits: 248,
      medicalPriority: 'HIGH',
      location: 'Borigaon Emergency Sector',
      elevation: '342 m',
      access: 'Good',
    ),
    _CapacitySite(
      name: 'Community Ground Beta',
      capacity: 1500,
      population: 980,
      waterPerPerson: 15,
      foodPerPerson: 0.65,
      shelterUnits: 196,
      medicalPriority: 'MEDIUM',
      location: 'North Community Sector',
      elevation: '318 m',
      access: 'Moderate',
    ),
    _CapacitySite(
      name: 'Highland Shelter Gamma',
      capacity: 2200,
      population: 1120,
      waterPerPerson: 20,
      foodPerPerson: 0.65,
      shelterUnits: 224,
      medicalPriority: 'LOW',
      location: 'Highland Safety Sector',
      elevation: '487 m',
      access: 'Good',
    ),
  ];
    static const String _relocationPlanUrl =
      'http://10.102.59.67:8000/relocation-plan/';

  _CapacitySite get currentSite =>
      sites.firstWhere((site) => site.name == selectedSite);

  double get utilization =>
      currentSite.capacity == 0
          ? 0
          : currentSite.population / currentSite.capacity;

  int get remainingCapacity =>
      currentSite.capacity - currentSite.population;

  double get waterDemand =>
      currentSite.population * currentSite.waterPerPerson / 1000;

    double get foodDemand =>
      currentSite.population * currentSite.foodPerPerson;

  @override
  void initState() {
    super.initState();
    _loadCapacityData();
  }

    Future<void> _loadCapacityData() async {
    try {
      final response = await http
          .get(
            Uri.parse(_relocationPlanUrl),
            headers: {
              'Accept': 'application/json',
            },
          )
          .timeout(const Duration(seconds: 45));

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(
          'Relocation plan request failed: ${response.statusCode}',
        );
      }

      final data = jsonDecode(response.body);

      if (data is! Map<String, dynamic>) {
        throw Exception('Invalid relocation plan response.');
      }

      final assignments = data['assignments'];

      if (assignments is! List) {
        throw Exception('Relocation plan contains no assignments.');
      }

      final Map<String, Map<String, dynamic>> groupedSites = {};

      for (final item in assignments) {
        if (item is! Map) continue;

        final siteId = item['site_id']?.toString() ?? '';
        final siteName = item['site_name']?.toString() ?? 'Unknown Site';

        if (siteId.isEmpty) continue;

        final population =
            int.tryParse(item['population']?.toString() ?? '0') ?? 0;

        final capacity =
            int.tryParse(item['site_capacity']?.toString() ?? '0') ?? 0;

        if (!groupedSites.containsKey(siteId)) {
          groupedSites[siteId] = {
            'name': siteName,
            'capacity': capacity,
            'population': population,
          };
        } else {
          groupedSites[siteId]!['population'] =
              (groupedSites[siteId]!['population'] as int) + population;
        }
      }

      final liveSites = groupedSites.values.map((site) {
        final capacity = site['capacity'] as int;
        final population = site['population'] as int;

        final utilization =
            capacity == 0 ? 0.0 : population / capacity;

        String medicalPriority;

        if (utilization >= 0.90) {
          medicalPriority = 'HIGH';
        } else if (utilization >= 0.75) {
          medicalPriority = 'MEDIUM';
        } else {
          medicalPriority = 'LOW';
        }

        return _CapacitySite(
          name: site['name'] as String,
          capacity: capacity,
          population: population,
          waterPerPerson: 15,
          foodPerPerson: 0.65,
          shelterUnits: (population / 5).ceil(),
          medicalPriority: medicalPriority,
          location: 'Live relocation plan',
          elevation: 'Not provided',
          access: 'Optimized',
        );
      }).toList();

      if (liveSites.isEmpty) {
        throw Exception('No relocation sites found in backend response.');
      }

      if (!mounted) return;

      setState(() {
        sites
          ..clear()
          ..addAll(liveSites);

        selectedSite = liveSites.first.name;
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    const background = Color(0xFF071016);
    const panel = Color(0xFF0D1921);
    const panel2 = Color(0xFF111F28);
    const border = Color(0xFF20323D);
    const cyan = Color(0xFF20D9FF);
    const green = Color(0xFF35E39A);
    const orange = Color(0xFFFFA63D);
    const red = Color(0xFFFF5D6C);
    const muted = Color(0xFF81909A);

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
              'CARRYING CAPACITY',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.2,
              ),
            ),
            SizedBox(height: 3),
            Text(
              'Relocation site resource assessment',
              style: TextStyle(
                color: muted,
                fontSize: 11,
              ),
            ),
          ],
        ),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(
              horizontal: 10,
              vertical: 6,
            ),
            decoration: BoxDecoration(
              color: green.withOpacity(.10),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: green.withOpacity(.35),
              ),
            ),
            child: const Row(
              children: [
                Icon(
                  Icons.circle,
                  color: green,
                  size: 8,
                ),
                SizedBox(width: 6),
                Text(
                  'ANALYSIS READY',
                  style: TextStyle(
                    color: green,
                    fontSize: 9,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      body: SafeArea(
  child: _loading
      ? const Center(
          child: CircularProgressIndicator(
            color: Color(0xFF20D9FF),
          ),
        )
      : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.cloud_off_rounded,
                      color: Color(0xFFFF5D6C),
                      size: 42,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'CAPACITY DATA UNAVAILABLE',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white54,
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: _loadCapacityData,
                      child: const Text('RETRY'),
                    ),
                  ],
                ),
              ),
            )
          : ListView(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
          children: [
            _sectionTitle(
              'RELOCATION SITE',
              cyan,
            ),
            const SizedBox(height: 10),

            _siteSelector(
              panel2,
              border,
              cyan,
            ),

            const SizedBox(height: 18),

            _siteHeaderCard(
              panel,
              border,
              cyan,
              green,
              muted,
            ),

            const SizedBox(height: 18),

            _sectionTitle(
              'CAPACITY UTILIZATION',
              cyan,
            ),
            const SizedBox(height: 10),

            _utilizationCard(
              panel,
              border,
              green,
              orange,
              red,
              muted,
            ),

            const SizedBox(height: 18),

            _sectionTitle(
              'RESOURCE REQUIREMENTS',
              cyan,
            ),
            const SizedBox(height: 10),

            Row(
              children: [
                Expanded(
                  child: _resourceCard(
                    title: 'WATER',
                    value: waterDemand.toStringAsFixed(1),
                    unit: 'KL / DAY',
                    icon: Icons.water_drop_outlined,
                    color: cyan,
                    panel: panel,
                    border: border,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _resourceCard(
                    title: 'FOOD',
                    value: foodDemand.toStringAsFixed(0),
                    unit: 'KG / DAY',
                    icon: Icons.restaurant_outlined,
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
                  child: _resourceCard(
                    title: 'SHELTER',
                    value: currentSite.shelterUnits.toString(),
                    unit: 'UNITS',
                    icon: Icons.home_work_outlined,
                    color: green,
                    panel: panel,
                    border: border,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _resourceCard(
                    title: 'POPULATION',
                    value: currentSite.population.toString(),
                    unit: 'PEOPLE',
                    icon: Icons.groups_outlined,
                    color: Colors.white,
                    panel: panel,
                    border: border,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 18),

            _sectionTitle(
              'SITE CONDITIONS',
              cyan,
            ),
            const SizedBox(height: 10),

            _conditionsCard(
              panel,
              border,
              muted,
              green,
              orange,
            ),

            const SizedBox(height: 18),

            _sectionTitle(
              'CAPACITY DECISION',
              cyan,
            ),
            const SizedBox(height: 10),

            _decisionCard(
              panel,
              border,
              green,
              orange,
              red,
              muted,
            ),

            const SizedBox(height: 20),

            SizedBox(
              height: 50,
              child: ElevatedButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      backgroundColor: panel2,
                      content: Text(
                        '$selectedSite capacity assessment saved.',
                        style: const TextStyle(
                          color: Colors.white,
                        ),
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.check_circle_outline),
                label: const Text(
                  'SAVE CAPACITY ASSESSMENT',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    letterSpacing: .8,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: cyan,
                  foregroundColor: Colors.black,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String title, Color color) {
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

  Widget _siteSelector(
    Color panel,
    Color border,
    Color cyan,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 14,
        vertical: 4,
      ),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: selectedSite,
          isExpanded: true,
          dropdownColor: panel,
          icon: Icon(
            Icons.keyboard_arrow_down,
            color: cyan,
          ),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
          items: sites.map((site) {
            return DropdownMenuItem<String>(
              value: site.name,
              child: Text(site.name),
            );
          }).toList(),
          onChanged: (value) {
            if (value == null) return;

            setState(() {
              selectedSite = value;
            });
          },
        ),
      ),
    );
  }

  Widget _siteHeaderCard(
    Color panel,
    Color border,
    Color cyan,
    Color green,
    Color muted,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: cyan.withOpacity(.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  Icons.location_on_outlined,
                  color: cyan,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      currentSite.name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      currentSite.location,
                      style: TextStyle(
                        color: muted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
              _statusBadge(
                'SUITABLE',
                green,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _miniInfo(
                  'ELEVATION',
                  currentSite.elevation,
                  muted,
                ),
              ),
              Expanded(
                child: _miniInfo(
                  'ACCESS',
                  currentSite.access,
                  muted,
                ),
              ),
              Expanded(
                child: _miniInfo(
                  'CAPACITY',
                  '${currentSite.capacity}',
                  muted,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _utilizationCard(
    Color panel,
    Color border,
    Color green,
    Color orange,
    Color red,
    Color muted,
  ) {
    final percent = utilization * 100;

    Color utilizationColor;

    if (percent >= 90) {
      utilizationColor = red;
    } else if (percent >= 75) {
      utilizationColor = orange;
    } else {
      utilizationColor = green;
    }

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${percent.toStringAsFixed(0)}%',
                style: TextStyle(
                  color: utilizationColor,
                  fontSize: 38,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(width: 10),
              const Padding(
                padding: EdgeInsets.only(bottom: 7),
                child: Text(
                  'UTILIZATION',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: .8,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: LinearProgressIndicator(
              value: utilization.clamp(0, 1).toDouble(),
              minHeight: 12,
              backgroundColor: Colors.white.withOpacity(.07),
              valueColor: AlwaysStoppedAnimation<Color>(
                utilizationColor,
              ),
            ),
          ),

          const SizedBox(height: 16),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _capacityNumber(
                'OCCUPIED',
                currentSite.population,
                Colors.white,
              ),
              _capacityNumber(
                'REMAINING',
                remainingCapacity,
                green,
              ),
              _capacityNumber(
                'TOTAL',
                currentSite.capacity,
                muted,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _resourceCard({
    required String title,
    required String value,
    required String unit,
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
        border: Border.all(color: border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                icon,
                color: color,
                size: 19,
              ),
              const SizedBox(width: 7),
              Text(
                title,
                style: TextStyle(
                  color: color,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: .8,
                ),
              ),
            ],
          ),
          const SizedBox(height: 13),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 25,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            unit,
            style: const TextStyle(
              color: Colors.white54,
              fontSize: 9,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _conditionsCard(
    Color panel,
    Color border,
    Color muted,
    Color green,
    Color orange,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Column(
        children: [
          _conditionRow(
            'Medical priority',
            currentSite.medicalPriority,
            currentSite.medicalPriority == 'HIGH'
                ? orange
                : green,
            muted,
          ),
          const Divider(
            color: Colors.white10,
            height: 22,
          ),
          _conditionRow(
            'Water requirement',
            '${waterDemand.toStringAsFixed(1)} KL/day',
            Colors.white,
            muted,
          ),
          const Divider(
            color: Colors.white10,
            height: 22,
          ),
          _conditionRow(
            'Food requirement',
            '${foodDemand.toStringAsFixed(0)} kg/day',
            Colors.white,
            muted,
          ),
          const Divider(
            color: Colors.white10,
            height: 22,
          ),
          _conditionRow(
            'Shelter requirement',
            '${currentSite.shelterUnits} units',
            Colors.white,
            muted,
          ),
        ],
      ),
    );
  }

  Widget _conditionRow(
    String label,
    String value,
    Color valueColor,
    Color muted,
  ) {
    return Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: muted,
              fontSize: 11,
            ),
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontSize: 11,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }

  Widget _decisionCard(
    Color panel,
    Color border,
    Color green,
    Color orange,
    Color red,
    Color muted,
  ) {
    final percent = utilization * 100;

    String decision;
    String explanation;
    Color decisionColor;
    IconData icon;

    if (percent >= 90) {
      decision = 'CAPACITY CRITICAL';
      explanation =
          'The site is approaching its maximum safe occupancy. Additional relocation should be restricted.';
      decisionColor = red;
      icon = Icons.warning_amber_rounded;
    } else if (percent >= 75) {
      decision = 'CAPACITY WARNING';
      explanation =
          'The site can accept additional population, but resource availability should be monitored.';
      decisionColor = orange;
      icon = Icons.error_outline;
    } else {
      decision = 'CAPACITY AVAILABLE';
      explanation =
          'The site has sufficient assessed capacity for the current relocation requirement.';
      decisionColor = green;
      icon = Icons.verified_outlined;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: decisionColor.withOpacity(.07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: decisionColor.withOpacity(.35),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            color: decisionColor,
            size: 27,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  decision,
                  style: TextStyle(
                    color: decisionColor,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .8,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  explanation,
                  style: TextStyle(
                    color: muted,
                    fontSize: 11,
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

  Widget _miniInfo(
    String title,
    String value,
    Color muted,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: muted,
            fontSize: 8,
            fontWeight: FontWeight.bold,
            letterSpacing: .6,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 11,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }

  Widget _statusBadge(
    String text,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 8,
        vertical: 5,
      ),
      decoration: BoxDecoration(
        color: color.withOpacity(.10),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: color.withOpacity(.35),
        ),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 8,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }

  Widget _capacityNumber(
    String title,
    int value,
    Color color,
  ) {
    return Column(
      children: [
        Text(
          value.toString(),
          style: TextStyle(
            color: color,
            fontSize: 18,
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
    );
  }
}

class _CapacitySite {
  final String name;
  final int capacity;
  final int population;
  final double waterPerPerson;
  final double foodPerPerson;
  final int shelterUnits;
  final String medicalPriority;
  final String location;
  final String elevation;
  final String access;

  const _CapacitySite({
    required this.name,
    required this.capacity,
    required this.population,
    required this.waterPerPerson,
    required this.foodPerPerson,
    required this.shelterUnits,
    required this.medicalPriority,
    required this.location,
    required this.elevation,
    required this.access,
  });
}