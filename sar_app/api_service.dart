import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

class ApiService {
  static const String baseUrl = 'http://10.102.59.67:8000';

  static Future<bool> isOnline() async {
    final connectivityResult = await (Connectivity().checkConnectivity());
    return !connectivityResult.contains(ConnectivityResult.none);
  }

  static Future<dynamic> get(String endpoint) async {
    if (!await isOnline()) {
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString('cache_$endpoint');
      if (cached != null) {
        return jsonDecode(cached);
      }
      throw Exception('Device is offline and no cache available for $endpoint');
    }

    final response = await http.get(
      Uri.parse('$baseUrl$endpoint'),
      headers: {
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      final prefs = await SharedPreferences.getInstance();
      prefs.setString('cache_$endpoint', response.body);
      return jsonDecode(response.body);
    }

    throw Exception(
      'GET $endpoint failed: ${response.statusCode} ${response.body}',
    );
  }

  static Future<dynamic> post(
    String endpoint, {
    dynamic body,
  }) async {
    if (!await isOnline()) {
      final prefs = await SharedPreferences.getInstance();
      List<String> queue = prefs.getStringList('post_queue') ?? [];
      queue.add(jsonEncode({
        'endpoint': endpoint,
        'body': body,
      }));
      await prefs.setStringList('post_queue', queue);
      return {'status': 'queued', 'message': 'Device is offline. Report queued for sync.'};
    }

    final response = await http.post(
      Uri.parse('$baseUrl$endpoint'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: body == null ? null : jsonEncode(body),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }

    throw Exception(
      'POST $endpoint failed: ${response.statusCode} ${response.body}',
    );
  }

  static Future<void> syncOfflineQueue() async {
    if (!await isOnline()) return;

    final prefs = await SharedPreferences.getInstance();
    List<String> queue = prefs.getStringList('post_queue') ?? [];
    
    if (queue.isEmpty) return;

    List<String> remaining = [];
    for (String itemStr in queue) {
      try {
        final item = jsonDecode(itemStr);
        await post(item['endpoint'], body: item['body']);
      } catch (e) {
        remaining.add(itemStr);
      }
    }
    
    await prefs.setStringList('post_queue', remaining);
  }
}