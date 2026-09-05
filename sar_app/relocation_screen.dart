import 'package:flutter/material.dart';
import '../../services/relocation_service.dart';

class RelocationScreen extends StatefulWidget {
  const RelocationScreen({super.key});

  @override
  State<RelocationScreen> createState() => _RelocationScreenState();
}

class _RelocationScreenState extends State<RelocationScreen> {
  int selectedSite = 0;
  bool generating = false;
  bool planGenerated = false;

  Map<String, dynamic>? backendPlan;
  String? backendError;

  final List<_RelocationSite> sites = const [
    _RelocationSite(
      name: 'Relief Zone Alpha',
      distance: '2.4 km',
      capacity: 1850,
      suitability: 94,
      elevation: '342 m',
      access: 'GOOD',
      safety: 'HIGH',
      reason:
          'High suitability with strong road access and available capacity.',
    ),
    _RelocationSite(
      name: 'Community Ground Beta',
      distance: '4.1 km',
      capacity: 1500,
      suitability: 86,
      elevation: '318 m',
      access: 'MODERATE',
      safety: 'HIGH',
      reason: 'Suitable alternative with moderate accessibility.',
    ),
    _RelocationSite(
      name: 'Highland Shelter Gamma',
      distance: '6.8 km',
      capacity: 2200,
      suitability: 91,
      elevation: '487 m',
      access: 'GOOD',
      safety: 'VERY HIGH',
      reason:
          'Higher elevation provides strong protection from flood hazards.',
    ),
  ];

  _RelocationSite get currentSite => sites[selectedSite];

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
              'RELOCATION INTELLIGENCE',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
              ),
            ),
            SizedBox(height: 3),
            Text(
              'Safer alternative site identification',
              style: TextStyle(
                color: muted,
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
          children: [
            _sectionTitle('SOURCE HABITATION', cyan),
            const SizedBox(height: 10),

            _habitationCard(
              panel,
              border,
              cyan,
              red,
              muted,
            ),

            const SizedBox(height: 20),

            _sectionTitle('ALTERNATIVE SITES', cyan),
            const SizedBox(height: 10),

            ...List.generate(
              sites.length,
              (index) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _siteCard(
                  index,
                  sites[index],
                  panel,
                  panel2,
                  border,
                  cyan,
                  green,
                  orange,
                  muted,
                ),
              ),
            ),

            const SizedBox(height: 10),

            _sectionTitle('SELECTED SITE ANALYSIS', cyan),
            const SizedBox(height: 10),

            _analysisCard(
              panel,
              border,
              cyan,
              green,
              orange,
              muted,
            ),

            const SizedBox(height: 20),

            _sectionTitle('RELOCATION DECISION', cyan),
            const SizedBox(height: 10),

            _decisionCard(
              panel,
              border,
              green,
              cyan,
              muted,
            ),

            const SizedBox(height: 18),

            if (backendError != null) ...[
              _errorCard(backendError!, red),
              const SizedBox(height: 14),
            ],

            SizedBox(
              height: 52,
              child: ElevatedButton.icon(
                onPressed: generating ? null : _generatePlan,
                icon: generating
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.black,
                        ),
                      )
                    : const Icon(Icons.route_outlined),
                label: Text(
                  generating
                      ? 'GENERATING PLAN...'
                      : planGenerated
                          ? 'REGENERATE RELOCATION PLAN'
                          : 'GENERATE RELOCATION PLAN',
                  style: const TextStyle(
                    fontWeight: FontWeight.w900,
                    letterSpacing: .7,
                  ),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: cyan,
                  foregroundColor: Colors.black,
                  disabledBackgroundColor: cyan.withOpacity(.5),
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),

            if (planGenerated) ...[
              const SizedBox(height: 16),
              _generatedPlanCard(
                panel,
                border,
                green,
                cyan,
                muted,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _generatePlan() async {
    setState(() {
      generating = true;
      backendError = null;
      planGenerated = false;
    });

    try {
      final response = await RelocationService.createRelocationPlan(
        [
          {
            'name': 'Borigaon',
            'population': 1240,
            'vulnerability': 82,
            'risk_score': 91,
            'flood_risk': 68,
            'landslide_risk': 54,
            'infrastructure_risk': 76,
            'risk': 91,
            'relocation_required': true,
          },
        ],
        region: 'assam',
      );

      if (!mounted) return;

      if (response is Map<String, dynamic>) {
        backendPlan = response;
      } else {
        backendPlan = {
          'response': response,
        };
      }

      setState(() {
        generating = false;
        planGenerated = true;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: Color(0xFF111F28),
          content: Text(
            'Relocation plan successfully generated by backend.',
            style: TextStyle(color: Colors.white),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        generating = false;
        planGenerated = false;
        backendError = 'Backend request failed: $e';
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: Color(0xFF111F28),
          content: Text(
            'Unable to generate relocation plan.',
            style: TextStyle(color: Colors.white),
          ),
        ),
      );
    }
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

  Widget _habitationCard(
    Color panel,
    Color border,
    Color cyan,
    Color red,
    Color muted,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Row(
        children: [
          Container(
            width: 45,
            height: 45,
            decoration: BoxDecoration(
              color: red.withOpacity(.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              Icons.warning_amber_rounded,
              color: red,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Borigaon',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Vulnerable habitation • Population 1,240',
                  style: TextStyle(
                    color: Color(0xFF81909A),
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
                '91',
                style: TextStyle(
                  color: red,
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                ),
              ),
              Text(
                'RISK',
                style: TextStyle(
                  color: muted,
                  fontSize: 8,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _siteCard(
    int index,
    _RelocationSite site,
    Color panel,
    Color panel2,
    Color border,
    Color cyan,
    Color green,
    Color orange,
    Color muted,
  ) {
    final selected = selectedSite == index;

    final suitabilityColor = site.suitability >= 90
        ? green
        : site.suitability >= 80
            ? orange
            : Colors.white54;

    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: () {
        setState(() {
          selectedSite = index;
          planGenerated = false;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: selected ? cyan.withOpacity(.06) : panel,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? cyan.withOpacity(.65) : border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: suitabilityColor.withOpacity(.10),
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: Icon(
                    Icons.location_on_outlined,
                    color: suitabilityColor,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        site.name,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '${site.distance} from habitation',
                        style: TextStyle(
                          color: muted,
                          fontSize: 9,
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '${site.suitability}%',
                      style: TextStyle(
                        color: suitabilityColor,
                        fontSize: 19,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      'SUITABILITY',
                      style: TextStyle(
                        color: muted,
                        fontSize: 7,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                _siteMetric('CAPACITY', '${site.capacity}', Colors.white),
                _siteMetric('ELEVATION', site.elevation, cyan),
                _siteMetric('ACCESS', site.access, green),
                _siteMetric('SAFETY', site.safety, green),
              ],
            ),
            if (selected) ...[
              const SizedBox(height: 13),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: panel2,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.info_outline,
                      color: cyan,
                      size: 15,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        site.reason,
                        style: TextStyle(
                          color: muted,
                          fontSize: 10,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _siteMetric(
    String label,
    String value,
    Color color,
  ) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Colors.white38,
              fontSize: 7,
              fontWeight: FontWeight.bold,
              letterSpacing: .4,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 9,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }

  Widget _analysisCard(
    Color panel,
    Color border,
    Color cyan,
    Color green,
    Color orange,
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
        children: [
          _analysisRow(
            'Site suitability',
            '${currentSite.suitability}%',
            currentSite.suitability >= 90 ? green : orange,
            muted,
          ),
          _divider(),
          _analysisRow(
            'Available capacity',
            '${currentSite.capacity - 1240} people',
            green,
            muted,
          ),
          _divider(),
          _analysisRow(
            'Distance',
            currentSite.distance,
            cyan,
            muted,
          ),
          _divider(),
          _analysisRow(
            'Elevation',
            currentSite.elevation,
            cyan,
            muted,
          ),
          _divider(),
          _analysisRow(
            'Road accessibility',
            currentSite.access,
            green,
            muted,
          ),
          _divider(),
          _analysisRow(
            'Safety classification',
            currentSite.safety,
            green,
            muted,
          ),
        ],
      ),
    );
  }

  Widget _analysisRow(
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
              fontSize: 10,
            ),
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontSize: 10,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }

  Widget _divider() {
    return const Divider(
      color: Colors.white10,
      height: 20,
    );
  }

  Widget _decisionCard(
    Color panel,
    Color border,
    Color green,
    Color cyan,
    Color muted,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: green.withOpacity(.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: green.withOpacity(.30),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.verified_outlined,
            color: green,
            size: 27,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'RECOMMENDED RELOCATION SITE',
                  style: TextStyle(
                    color: green,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .7,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  currentSite.name,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  'Highest-ranked available option based on suitability, capacity, accessibility and safety.',
                  style: TextStyle(
                    color: muted,
                    fontSize: 10,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _errorCard(String message, Color red) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: red.withOpacity(.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: red.withOpacity(.3),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.error_outline,
            color: red,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 10,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _generatedPlanCard(
    Color panel,
    Color border,
    Color green,
    Color cyan,
    Color muted,
  ) {
    final plan = backendPlan?['plan'];
    final summary = plan is Map ? plan['summary'] : null;

    final assigned = summary is Map
        ? summary['assigned']?.toString() ?? '0'
        : '0';

    final unassigned = summary is Map
        ? summary['unassigned_count']?.toString() ?? '0'
        : '0';

    final total = summary is Map
        ? summary['total_habitations']?.toString() ?? '1'
        : '1';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: green.withOpacity(.35),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.check_circle,
                color: green,
                size: 20,
              ),
              const SizedBox(width: 8),
              const Text(
                'BACKEND RELOCATION PLAN READY',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.w900,
                  letterSpacing: .7,
                ),
              ),
            ],
          ),

          const SizedBox(height: 15),

          _planStep(
            '01',
            'Identify vulnerable population',
            'Borigaon • 1,240 people',
            cyan,
          ),

          _planStep(
            '02',
            'Optimization result',
            '$assigned of $total habitation(s) assigned',
            cyan,
          ),

          _planStep(
            '03',
            'Unassigned habitations',
            unassigned,
            unassigned == '0' ? green : const Color(0xFFFFA63D),
          ),

          _planStep(
            '04',
            'Recommended destination',
            currentSite.name,
            green,
          ),

          if (backendPlan != null) ...[
            const SizedBox(height: 5),
            Text(
              'Optimization performed by backend.',
              style: TextStyle(
                color: muted,
                fontSize: 9,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _planStep(
    String number,
    String title,
    String subtitle,
    Color color,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 13),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 27,
            height: 27,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: color.withOpacity(.10),
              shape: BoxShape.circle,
            ),
            child: Text(
              number,
              style: TextStyle(
                color: color,
                fontSize: 8,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: Colors.white38,
                    fontSize: 9,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RelocationSite {
  final String name;
  final String distance;
  final int capacity;
  final int suitability;
  final String elevation;
  final String access;
  final String safety;
  final String reason;

  const _RelocationSite({
    required this.name,
    required this.distance,
    required this.capacity,
    required this.suitability,
    required this.elevation,
    required this.access,
    required this.safety,
    required this.reason,
  });
}

