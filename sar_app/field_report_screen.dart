import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';
import 'api_service.dart';

class FieldReportScreen extends StatefulWidget {
  const FieldReportScreen({super.key});

  @override
  State<FieldReportScreen> createState() => _FieldReportScreenState();
}

class _FieldReportScreenState extends State<FieldReportScreen> {
  String? teamId;
  Map<String, dynamic>? activeDispatch;
  bool isLoading = true;
  Timer? _pollingTimer;
  bool isVerificationDialogShowing = false;
  
  // Simulated GPS Coordinates for Demo
  double _simLat = 26.342;
  double _simLng = 92.651;

  final TextEditingController _rescuedController = TextEditingController();
  final TextEditingController _notesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadTeamId();
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _rescuedController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadTeamId() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      teamId = prefs.getString('team_id');
      isLoading = false;
    });

    if (teamId != null) {
      _startPolling();
    }
  }

  Future<void> _saveTeamId(String newId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('team_id', newId);
    setState(() {
      teamId = newId;
    });
    _startPolling();
  }

  void _startPolling() {
    _fetchDispatchStatus();
    _pollingTimer = Timer.periodic(const Duration(seconds: 5), (timer) {
      _fetchDispatchStatus();
    });
  }

  Future<void> _fetchDispatchStatus() async {
    if (teamId == null) return;
    try {
      final res = await ApiService.get('/dispatch/');
      if (res != null && res['teams'] != null) {
        final teams = res['teams'] as List;
        final myTeam = teams.firstWhere((t) => t['id'] == teamId, orElse: () => null);
        if (myTeam != null) {
          // Check for HITL Verification Request
          if (myTeam['location_verification'] == 'PENDING' && !isVerificationDialogShowing) {
            _showVerificationDialog();
          }
          
          // Stream Simulated Telemetry to Backend
          _streamLocation();
          
          if (myTeam['current_assignment'] != null) {
            final dispatches = res['dispatches'] as List;
            final dsp = dispatches.firstWhere((d) => d['id'] == myTeam['current_assignment'], orElse: () => null);
            if (mounted) {
              setState(() {
                activeDispatch = dsp;
              });
            }
          } else {
            if (mounted) {
              setState(() {
                activeDispatch = null;
              });
            }
          }
        }
      }
    } catch (e) {
      debugPrint("Error fetching dispatch: $e");
    }
  }

  void _streamLocation() async {
    if (teamId == null) return;
    try {
      // Simulate movement towards South-East to simulate driving
      _simLat -= 0.0001;
      _simLng += 0.0001;
      
      await ApiService.post('/dispatch/$teamId/location', body: {
        'lat': _simLat,
        'lng': _simLng
      });
    } catch (e) {
      debugPrint("Telemetry stream error: $e");
    }
  }

  void _showVerificationDialog() {
    isVerificationDialogShowing = true;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.red.shade900,
        title: const Text(
          "🚨 COMMANDER OVERRIDE", 
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)
        ),
        content: const Text(
          "COMMANDER REQUESTS LOCATION VERIFICATION.\n\nARE YOU AT THE CORRECT SITE?",
          style: TextStyle(color: Colors.white, fontSize: 16),
        ),
        actions: [
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
            onPressed: () async {
              try {
                await ApiService.post('/dispatch/$teamId/confirm-location', body: {});
              } catch(e) {
                debugPrint(e.toString());
              }
              isVerificationDialogShowing = false;
              if (mounted) Navigator.pop(ctx);
            },
            child: const Text("YES, WE ARE HERE", style: TextStyle(color: Colors.white)),
          )
        ],
      )
    );
  }

  Future<void> _acceptDispatch() async {
    if (teamId == null) return;
    try {
      await ApiService.post('/dispatch/$teamId/accept', {});
      _fetchDispatchStatus();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _submitReport() async {
    if (teamId == null) return;
    final rescued = int.tryParse(_rescuedController.text) ?? 0;
    
    try {
      await ApiService.post('/field-reports/', {
        "team_id": teamId,
        "rescued_count": rescued,
        "notes": _notesController.text
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Report submitted successfully!'), backgroundColor: Colors.green));
      _rescuedController.clear();
      _notesController.clear();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _completeMission() async {
    if (teamId == null) return;
    try {
      await ApiService.post('/dispatch/$teamId/complete', {});
      _fetchDispatchStatus();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFF071016),
        body: Center(child: CircularProgressIndicator(color: Color(0xFF20D9FF))),
      );
    }

    if (teamId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Field Operations'), backgroundColor: const Color(0xFF071016)),
        backgroundColor: const Color(0xFF071016),
        body: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.sensor_door_outlined, size: 64, color: Colors.white54),
              const SizedBox(height: 20),
              const Text('Select your team to register for Field Operations.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 16)),
              const SizedBox(height: 30),
              ElevatedButton(onPressed: () => _saveTeamId('TEAM-A1'), style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF20D9FF), foregroundColor: Colors.black), child: const Text('Register as TEAM-A1')),
              const SizedBox(height: 10),
              ElevatedButton(onPressed: () => _saveTeamId('TEAM-B2'), style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF20D9FF), foregroundColor: Colors.black), child: const Text('Register as TEAM-B2')),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Op: $teamId'), 
        backgroundColor: const Color(0xFF071016),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: () => _saveTeamId('')),
        ],
      ),
      backgroundColor: const Color(0xFF071016),
      body: activeDispatch == null ? _buildWaiting() : _buildActiveDispatch(),
    );
  }

  Widget _buildWaiting() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.radar, size: 64, color: Color(0xFF35D07F)),
          SizedBox(height: 20),
          Text('STATUS: AVAILABLE', style: TextStyle(color: Color(0xFF35D07F), fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: 2)),
          SizedBox(height: 10),
          Text('Waiting for command center tasking...', style: TextStyle(color: Colors.white70)),
        ],
      ),
    );
  }

  Widget _buildActiveDispatch() {
    final status = activeDispatch!['status'];
    final hab = activeDispatch!['habitation_id'];
    final sz = activeDispatch!['safe_zone_id'];
    final isDispatched = status == 'DISPATCHED';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDispatched ? const Color(0xFFFFA726).withOpacity(0.1) : const Color(0xFFFF4D67).withOpacity(0.1),
              border: Border.all(color: isDispatched ? const Color(0xFFFFA726) : const Color(0xFFFF4D67)),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Text(isDispatched ? '🚨 NEW DISPATCH ORDER' : '🔴 ON SCENE', style: TextStyle(color: isDispatched ? const Color(0xFFFFA726) : const Color(0xFFFF4D67), fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                Text('Target: $hab', style: const TextStyle(color: Colors.white, fontSize: 16)),
                const SizedBox(height: 8),
                Text('Destination: $sz', style: const TextStyle(color: Colors.white, fontSize: 16)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (isDispatched)
            ElevatedButton(
              onPressed: _acceptDispatch,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFFA726),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: const Text('ACCEPT DISPATCH', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            )
          else
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('Submit Field Report', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                TextField(
                  controller: _rescuedController,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: 'Civilians Rescued (Wave Count)',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                    focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Color(0xFF20D9FF))),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _notesController,
                  style: const TextStyle(color: Colors.white),
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Notes (Optional)',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                    focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Color(0xFF20D9FF))),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _submitReport,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF20D9FF),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: const Text('SUBMIT REPORT', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 40),
                TextButton(
                  onPressed: _completeMission,
                  child: const Text('COMPLETE MISSION & RETURN TO BASE', style: TextStyle(color: Color(0xFF35D07F))),
                )
              ],
            ),
        ],
      ),
    );
  }
}
