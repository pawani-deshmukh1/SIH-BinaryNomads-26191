
import 'package:flutter/material.dart';

import '../screen/dashboard/dashboard_screen.dart';
import '../screen/risk_map/risk_map_screen.dart';
import '../screen/assessment/assess_screen.dart';
import '../screen/relocation/relocation_screen.dart';
import '../screen/alerts/alerts_screen.dart';
import '../screen/simulation/simulation_screen.dart';
import 'field_report_screen.dart';

class AppNavigation extends StatefulWidget {
  const AppNavigation({super.key});

  @override
  State<AppNavigation> createState() => _AppNavigationState();
}

class _AppNavigationState extends State<AppNavigation> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    RiskMapScreen(),
    AssessScreen(),
    RelocationScreen(),
    AlertsScreen(),
    SimulationScreen(),
    FieldReportScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF071016),

      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),

      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF0B151C),
          border: Border(
            top: BorderSide(
              color: Color(0xFF18333D),
              width: 1,
            ),
          ),
        ),

        child: NavigationBar(
          selectedIndex: _currentIndex,

          onDestinationSelected: (index) {
            setState(() {
              _currentIndex = index;
            });
          },

          backgroundColor: Colors.transparent,
          elevation: 0,

          indicatorColor: Color(0xFF20D9FF),

          labelBehavior:
              NavigationDestinationLabelBehavior.alwaysShow,

          destinations: const [
            NavigationDestination(
              icon: Icon(
                Icons.dashboard_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.dashboard,
                color: Color(0xFF071016),
              ),
              label: 'Command',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.map_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.map,
                color: Color(0xFF071016),
              ),
              label: 'Live Map',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.analytics_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.analytics,
                color: Color(0xFF071016),
              ),
              label: 'Assess',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.alt_route_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.alt_route,
                color: Color(0xFF071016),
              ),
              label: 'Relocate',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.notifications_none,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.notifications,
                color: Color(0xFF071016),
              ),
              label: 'Alerts',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.science_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.science,
                color: Color(0xFF071016),
              ),
              label: 'Simulate',
            ),

            NavigationDestination(
              icon: Icon(
                Icons.send_outlined,
                color: Colors.white70,
              ),
              selectedIcon: Icon(
                Icons.send,
                color: Color(0xFF071016),
              ),
              label: 'Report',
            ),
          ],
        ),
      ),
    );
  }
}
