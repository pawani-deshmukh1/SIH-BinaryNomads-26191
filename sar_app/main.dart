import 'package:flutter/material.dart';
import 'widgets/app_navigation.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const DishaApp());
}

class DishaApp extends StatelessWidget {
  const DishaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'DISHA',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF071016),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF20D9FF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const AppNavigation(),
    );
  }
}