import 'package:flutter/material.dart';
import 'api_service.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  String filter = 'ALL';
  bool isLoading = true;
  List<_AlertItem> alerts = [];

  @override
  void initState() {
    super.initState();
    _fetchAlerts();
  }

  Future<void> _fetchAlerts() async {
    setState(() => isLoading = true);
    try {
      final response = await ApiService.get('/alerts/');
      if (response != null && response is List) {
        final parsedAlerts = response.map((data) {
          IconData iconData = Icons.warning_amber_rounded;
          if (data['icon'] == 'water_outlined') iconData = Icons.water_outlined;
          else if (data['icon'] == 'location_on_outlined') iconData = Icons.location_on_outlined;
          else if (data['icon'] == 'route_outlined') iconData = Icons.route_outlined;

          return _AlertItem(
            title: data['title'] ?? 'Alert',
            location: data['location'] ?? 'Unknown',
            description: data['description'] ?? '',
            time: data['time'] ?? 'Just now',
            severity: data['severity'] ?? 'LOW',
            icon: iconData,
          );
        }).toList();
        setState(() {
          alerts = parsedAlerts;
          isLoading = false;
        });
        return;
      }
    } catch (e) {
      debugPrint('Error fetching alerts: $e');
    }
    setState(() => isLoading = false);
  }

  List<_AlertItem> get visibleAlerts {
    if (filter == 'ALL') return alerts;

    return alerts
        .where((alert) => alert.severity == filter)
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    const background = Color(0xFF071016);
    const panel = Color(0xFF0D1921);
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
              'ALERT CENTER',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
              ),
            ),
            SizedBox(height: 3),
            Text(
              'Hazard and relocation intelligence',
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
            child: IconButton(
              onPressed: () {
                _fetchAlerts();
              },
              icon: const Icon(
                Icons.refresh,
                color: cyan,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
          children: [
            _summaryCard(
              panel,
              border,
              red,
              orange,
              green,
            ),

            const SizedBox(height: 20),

            _sectionTitle(
              'FILTER ALERTS',
              cyan,
            ),

            const SizedBox(height: 10),

            _filterBar(
              border,
              cyan,
              muted,
            ),

            const SizedBox(height: 18),

            _sectionTitle(
              'ACTIVE ALERTS',
              cyan,
            ),

            const SizedBox(height: 10),

            if (isLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 40),
                child: Center(child: CircularProgressIndicator(color: cyan)),
              )
            else if (visibleAlerts.isEmpty)
              _emptyState(
                panel,
                border,
                muted,
              )
            else
              ...visibleAlerts.map(
                (alert) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _alertCard(
                    alert,
                    panel,
                    border,
                    red,
                    orange,
                    green,
                    cyan,
                    muted,
                  ),
                ),
              ),

            const SizedBox(height: 12),

            _authorityNotice(
              panel,
              border,
              cyan,
              muted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _summaryCard(
    Color panel,
    Color border,
    Color red,
    Color orange,
    Color green,
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
          Expanded(
            child: _summaryMetric(
              'CRITICAL',
              '1',
              red,
            ),
          ),
          Expanded(
            child: _summaryMetric(
              'HIGH',
              '1',
              orange,
            ),
          ),
          Expanded(
            child: _summaryMetric(
              'MEDIUM',
              '1',
              orange,
            ),
          ),
          Expanded(
            child: _summaryMetric(
              'LOW',
              '1',
              green,
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryMetric(
    String title,
    String value,
    Color color,
  ) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 24,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          title,
          style: const TextStyle(
            color: Colors.white38,
            fontSize: 7,
            fontWeight: FontWeight.bold,
            letterSpacing: .5,
          ),
        ),
      ],
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

  Widget _filterBar(
    Color border,
    Color cyan,
    Color muted,
  ) {
    const filters = [
      'ALL',
      'CRITICAL',
      'HIGH',
      'MEDIUM',
      'LOW',
    ];

    return SizedBox(
      height: 38,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: filters.length,
        separatorBuilder: (_, __) =>
            const SizedBox(width: 7),
        itemBuilder: (context, index) {
          final item = filters[index];
          final selected = filter == item;

          return InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () {
              setState(() {
                filter = item;
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 12,
              ),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected
                    ? cyan.withOpacity(.12)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: selected
                      ? cyan.withOpacity(.6)
                      : border,
                ),
              ),
              child: Text(
                item,
                style: TextStyle(
                  color: selected ? cyan : muted,
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: .5,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _alertCard(
    _AlertItem alert,
    Color panel,
    Color border,
    Color red,
    Color orange,
    Color green,
    Color cyan,
    Color muted,
  ) {
    final color = _severityColor(
      alert.severity,
      red,
      orange,
      green,
      cyan,
    );

    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: alert.severity == 'CRITICAL'
              ? color.withOpacity(.55)
              : border,
        ),
      ),
      child: Column(
        children: [
          Row(
            crossAxisAlignment:
                CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withOpacity(.10),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(
                  alert.icon,
                  color: color,
                  size: 21,
                ),
              ),

              const SizedBox(width: 11),

              Expanded(
                child: Column(
                  crossAxisAlignment:
                      CrossAxisAlignment.start,
                  children: [
                    Text(
                      alert.title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          Icons.location_on_outlined,
                          color: muted,
                          size: 11,
                        ),
                        const SizedBox(width: 3),
                        Expanded(
                          child: Text(
                            alert.location,
                            style: TextStyle(
                              color: muted,
                              fontSize: 9,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              _severityBadge(
                alert.severity,
                color,
              ),
            ],
          ),

          const SizedBox(height: 13),

          Text(
            alert.description,
            style: TextStyle(
              color: muted,
              fontSize: 10,
              height: 1.45,
            ),
          ),

          const SizedBox(height: 13),

          Row(
            children: [
              Icon(
                Icons.schedule_outlined,
                color: muted,
                size: 13,
              ),
              const SizedBox(width: 5),
              Text(
                alert.time,
                style: TextStyle(
                  color: muted,
                  fontSize: 9,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () {
                  _showAlertDetails(
                    context,
                    alert,
                    color,
                  );
                },
                style: TextButton.styleFrom(
                  foregroundColor: cyan,
                  padding: EdgeInsets.zero,
                  minimumSize: Size.zero,
                  tapTargetSize:
                      MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text(
                  'VIEW DETAILS',
                  style: TextStyle(
                    fontSize: 8,
                    fontWeight: FontWeight.w800,
                    letterSpacing: .5,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _severityColor(
    String severity,
    Color red,
    Color orange,
    Color green,
    Color cyan,
  ) {
    switch (severity) {
      case 'CRITICAL':
        return red;
      case 'HIGH':
        return orange;
      case 'MEDIUM':
        return orange;
      default:
        return green;
    }
  }

  Widget _severityBadge(
    String text,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 7,
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
          fontSize: 7,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }

  Widget _emptyState(
    Color panel,
    Color border,
    Color muted,
  ) {
    return Container(
      padding: const EdgeInsets.all(30),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Column(
        children: [
          Icon(
            Icons.notifications_none,
            color: muted,
            size: 35,
          ),
          const SizedBox(height: 10),
          const Text(
            'NO ALERTS',
            style: TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            'No alerts match the selected filter.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: muted,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  Widget _authorityNotice(
    Color panel,
    Color border,
    Color cyan,
    Color muted,
  ) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: panel,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: border),
      ),
      child: Row(
        crossAxisAlignment:
            CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.admin_panel_settings_outlined,
            color: cyan,
            size: 19,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Alerts are intended to support authorized disaster-management personnel in prioritizing field assessment and relocation decisions.',
              style: TextStyle(
                color: muted,
                fontSize: 9,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showAlertDetails(
    BuildContext context,
    _AlertItem alert,
    Color color,
  ) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF0D1921),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(18),
        ),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              20,
              20,
              20,
              25,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      alert.icon,
                      color: color,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        alert.title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Text(
                  alert.description,
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 11,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 15),
                Text(
                  'LOCATION: ${alert.location}',
                  style: TextStyle(
                    color: color,
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                    letterSpacing: .5,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  'SEVERITY: ${alert.severity}',
                  style: TextStyle(
                    color: color,
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                    letterSpacing: .5,
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

class _AlertItem {
  final String title;
  final String location;
  final String description;
  final String time;
  final String severity;
  final IconData icon;

  const _AlertItem({
    required this.title,
    required this.location,
    required this.description,
    required this.time,
    required this.severity,
    required this.icon,
  });
}