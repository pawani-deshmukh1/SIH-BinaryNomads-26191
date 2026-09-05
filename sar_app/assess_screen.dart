import 'dart:io';
import 'vulnerability_screen.dart';

import 'package:image_picker/image_picker.dart';

import '../../services/risk_service.dart';

import 'package:flutter/material.dart';

import '../capacity/carrying_capacity_screen.dart';
import '../relocation/relocation_screen.dart';

class AssessScreen extends StatelessWidget {
  const AssessScreen({super.key});

  static const Color bg = Color(0xFF071018);
  static const Color panel = Color(0xFF0C1721);
  static const Color panel2 = Color(0xFF111F2B);
  static const Color border = Color(0xFF20313D);

  static const Color cyan = Color(0xFF20D9FF);
  static const Color green = Color(0xFF35D0BA);
  static const Color orange = Color(0xFFFFA94D);
  static const Color red = Color(0xFFFF5263);
  static const Color muted = Color(0xFF8293A0);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: panel,
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'ASSESS',
          style: TextStyle(
            fontWeight: FontWeight.w900,
            letterSpacing: .8,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 30),
        children: [
          _header(),

          const SizedBox(height: 20),

          _statusCard(),

          const SizedBox(height: 20),

          const Text(
            'ASSESSMENT MODULES',
            style: TextStyle(
              color: muted,
              fontSize: 11,
              fontWeight: FontWeight.w900,
              letterSpacing: 1,
            ),
          ),

          const SizedBox(height: 10),

          _ModuleButton(
            icon: Icons.warning_amber_rounded,
            color: red,
            title: 'Hazard & Risk Assessment',
            subtitle: 'Evaluate flood, landslide and structural risk',
            badge: 'RISK',
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const RiskAssessmentScreen(),
                ),
              );
            },
          ),

          _ModuleButton(
            icon: Icons.people_outline,
            color: orange,
            title: 'Vulnerability Assessment',
            subtitle: 'Assess population and infrastructure vulnerability',
            badge: 'VULN',
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const VulnerabilityScreen(),
                ),
              );
            },
          ),

          _ModuleButton(
            icon: Icons.inventory_2_outlined,
            color: cyan,
            title: 'Carrying Capacity',
            subtitle: 'Evaluate capacity of safer relocation sites',
            badge: 'CAP',
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const CarryingCapacityScreen(),
                ),
              );
            },
          ),

          _ModuleButton(
            icon: Icons.location_on_outlined,
            color: green,
            title: 'Relocation Intelligence',
            subtitle: 'Compare safer alternative relocation sites',
            badge: 'MOVE',
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const RelocationScreen(),
                ),
              );
            },
          ),

          _ModuleButton(
            icon: Icons.monitor_heart_outlined,
            color: cyan,
            title: 'COP & Simulation',
            subtitle: 'Command operations and scenario simulation',
            badge: 'COP',
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text(
                    'COP & Simulation is available from the Simulation tab.',
                  ),
                ),
              );
            },
          ),

          const SizedBox(height: 22),

          _workflowCard(),
        ],
      ),
    );
  }

  Widget _header() {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Assessment Center',
          style: TextStyle(
            color: Colors.white,
            fontSize: 26,
            fontWeight: FontWeight.w900,
          ),
        ),
        SizedBox(height: 7),
        Text(
          'Evaluate hazards, vulnerability, capacity and relocation requirements.',
          style: TextStyle(
            color: muted,
            fontSize: 13,
            height: 1.4,
          ),
        ),
      ],
    );
  }

  Widget _statusCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [
            Color(0xFF102431),
            Color(0xFF0C1721),
          ],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: cyan.withOpacity(.28),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: cyan.withOpacity(.10),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.analytics_outlined,
              color: cyan,
            ),
          ),
          const SizedBox(width: 13),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ASSESSMENT ENGINE',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Ready for habitation analysis',
                  style: TextStyle(
                    color: muted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: 9,
              vertical: 5,
            ),
            decoration: BoxDecoration(
              color: green.withOpacity(.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Text(
              'ONLINE',
              style: TextStyle(
                color: green,
                fontSize: 9,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _workflowCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: border),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'DISHA WORKFLOW',
            style: TextStyle(
              color: cyan,
              fontSize: 10,
              fontWeight: FontWeight.w900,
              letterSpacing: 1,
            ),
          ),
          SizedBox(height: 12),
          _WorkflowRow(
            number: '01',
            title: 'IDENTIFY',
            subtitle: 'Detect hazardous red zones',
          ),
          _WorkflowRow(
            number: '02',
            title: 'ASSESS',
            subtitle: 'Evaluate vulnerability and risk',
          ),
          _WorkflowRow(
            number: '03',
            title: 'PRIORITIZE',
            subtitle: 'Rank relocation requirements',
          ),
          _WorkflowRow(
            number: '04',
            title: 'RELOCATE',
            subtitle: 'Select suitable safer sites',
          ),
          _WorkflowRow(
            number: '05',
            title: 'RESPOND',
            subtitle: 'Support emergency operations',
            last: true,
          ),
        ],
      ),
    );
  }
}

class _WorkflowRow extends StatelessWidget {
  final String number;
  final String title;
  final String subtitle;
  final bool last;

  const _WorkflowRow({
    required this.number,
    required this.title,
    required this.subtitle,
    this.last = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: last ? 0 : 12,
      ),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0xFF111F2B),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              number,
              style: const TextStyle(
                color: Color(0xFF20D9FF),
                fontSize: 10,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: Color(0xFF8293A0),
                    fontSize: 10,
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

class _ModuleButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final String badge;
  final VoidCallback onTap;

  const _ModuleButton({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.badge,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1721),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF20313D),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 13,
            ),
            child: Row(
              children: [
                Container(
                  width: 46,
                  height: 46,
                  decoration: BoxDecoration(
                    color: color.withOpacity(.10),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: Icon(
                    icon,
                    color: color,
                  ),
                ),

                const SizedBox(width: 13),

                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          color: Color(0xFF8293A0),
                          fontSize: 11,
                          height: 1.3,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(width: 8),

                Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 7,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: color.withOpacity(.10),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        badge,
                        style: TextStyle(
                          color: color,
                          fontSize: 8,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(height: 7),
                    const Icon(
                      Icons.chevron_right_rounded,
                      color: Color(0xFF8293A0),
                      size: 19,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ============================================================
// HAZARD & RISK ASSESSMENT
// ============================================================

class RiskAssessmentScreen extends StatefulWidget {
  const RiskAssessmentScreen({super.key});

  @override
  State<RiskAssessmentScreen> createState() =>
      _RiskAssessmentScreenState();
}

class _RiskAssessmentScreenState
    extends State<RiskAssessmentScreen> {
  File? selectedImage;

  bool loading = false;

  dynamic floodResult;
  dynamic landslideResult;

  String? errorMessage;

  Future<void> pickImage() async {
    final picker = ImagePicker();

    final image = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
    );

    if (image == null) return;

    setState(() {
      selectedImage = File(image.path);
      floodResult = null;
      landslideResult = null;
      errorMessage = null;
    });
  }

  Future<void> analyzeImage() async {
    if (selectedImage == null) {
      setState(() {
        errorMessage = 'Please select an image first.';
      });
      return;
    }

    setState(() {
      loading = true;
      errorMessage = null;
      floodResult = null;
      landslideResult = null;
    });

    try {
      final results = await Future.wait([
        RiskService.assessFlood(selectedImage!),
        RiskService.assessLandslide(selectedImage!),
      ]);

      if (!mounted) return;

      setState(() {
        floodResult = results[0];
        landslideResult = results[1];
        loading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        loading = false;
        errorMessage = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF071018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0C1721),
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'Hazard & Risk Assessment',
          style: TextStyle(
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _introCard(),

          const SizedBox(height: 18),

          _imageSelector(),

          const SizedBox(height: 16),

          SizedBox(
            height: 52,
            child: ElevatedButton.icon(
              onPressed: loading ? null : analyzeImage,
              icon: loading
                  ? const SizedBox(
                      width: 19,
                      height: 19,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.analytics_outlined),
              label: Text(
                loading
                    ? 'ANALYZING...'
                    : 'ANALYZE WITH DISHA',
                style: const TextStyle(
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ),

          if (errorMessage != null) ...[
            const SizedBox(height: 16),
            _errorCard(),
          ],

          if (floodResult != null ||
              landslideResult != null) ...[
            const SizedBox(height: 22),
            _resultsHeader(),
          ],

          if (floodResult != null) ...[
            const SizedBox(height: 10),
            _resultCard(
              title: 'Flood Risk',
              icon: Icons.water_damage_outlined,
              color: Colors.blue,
              result: floodResult,
            ),
          ],

          if (landslideResult != null) ...[
            const SizedBox(height: 10),
            _resultCard(
              title: 'Landslide Risk',
              icon: Icons.terrain_outlined,
              color: Colors.orange,
              result: landslideResult,
            ),
          ],

          if (floodResult != null ||
              landslideResult != null) ...[
            const SizedBox(height: 18),
            _backendNotice(),
          ],
        ],
      ),
    );
  }

  Widget _introCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1721),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF20313D),
        ),
      ),
      child: const Row(
        children: [
          Icon(
            Icons.sensors_outlined,
            color: Color(0xFF20D9FF),
            size: 28,
          ),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'Upload a terrain or habitation image. DISHA will send it to the backend hazard analysis services.',
              style: TextStyle(
                color: Color(0xFF9AAAB5),
                fontSize: 11,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _imageSelector() {
    return GestureDetector(
      onTap: pickImage,
      child: Container(
        height: 220,
        decoration: BoxDecoration(
          color: const Color(0xFF0C1721),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selectedImage == null
                ? const Color(0xFF20313D)
                : const Color(0xFF20D9FF).withOpacity(.5),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: selectedImage == null
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.add_photo_alternate_outlined,
                    color: Color(0xFF20D9FF),
                    size: 48,
                  ),
                  SizedBox(height: 12),
                  Text(
                    'SELECT HABITATION IMAGE',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  SizedBox(height: 6),
                  Text(
                    'Tap to choose an image from your device',
                    style: TextStyle(
                      color: Color(0xFF8293A0),
                      fontSize: 10,
                    ),
                  ),
                ],
              )
            : Stack(
                fit: StackFit.expand,
                children: [
                  Image.file(
                    selectedImage!,
                    fit: BoxFit.cover,
                  ),
                  Positioned(
                    left: 12,
                    right: 12,
                    bottom: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 9,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(.72),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        children: [
                          Icon(
                            Icons.check_circle,
                            color: Color(0xFF35D0BA),
                            size: 17,
                          ),
                          SizedBox(width: 7),
                          Text(
                            'IMAGE SELECTED',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                            ),
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

  Widget _resultsHeader() {
    return const Text(
      'BACKEND ANALYSIS RESULTS',
      style: TextStyle(
        color: Color(0xFF8293A0),
        fontSize: 10,
        fontWeight: FontWeight.w900,
        letterSpacing: 1,
      ),
    );
  }

  Widget _resultCard({
    required String title,
    required IconData icon,
    required Color color,
    required dynamic result,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1721),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: color.withOpacity(.30),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withOpacity(.10),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              icon,
              color: color,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  _formatResult(result),
                  style: const TextStyle(
                    color: Color(0xFF9AAAB5),
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

  String _formatResult(dynamic result) {
    if (result is Map) {
      final entries = result.entries.take(4);

      return entries
          .map(
            (entry) =>
                '${entry.key}: ${entry.value}',
          )
          .join('\n');
    }

    return result.toString();
  }

  Widget _errorCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFF5263).withOpacity(.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: const Color(0xFFFF5263).withOpacity(.3),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.error_outline,
            color: Color(0xFFFF5263),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              errorMessage!,
              style: const TextStyle(
                color: Color(0xFFFF8A95),
                fontSize: 10,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _backendNotice() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF35D0BA).withOpacity(.06),
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Text(
        'Source: DISHA backend hazard analysis service',
        textAlign: TextAlign.center,
        style: TextStyle(
          color: Color(0xFF35D0BA),
          fontSize: 9,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}