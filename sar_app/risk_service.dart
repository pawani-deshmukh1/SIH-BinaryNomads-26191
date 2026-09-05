import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class RiskService {
  static const String baseUrl = 'http://10.102.59.67:8000';

  static Future<dynamic> getRedZones() async {
    final response = await http.get(
      Uri.parse('$baseUrl/red-zones/'),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    }

    throw Exception(
      'Red zones request failed: ${response.statusCode}',
    );
  }

  static Future<dynamic> getLiveRisk() async {
    final response = await http.get(
      Uri.parse('$baseUrl/live-risk/'),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    }

    throw Exception(
      'Live risk request failed: ${response.statusCode}',
    );
  }

  static Future<dynamic> getSusceptibility() async {
    final response = await http.get(
      Uri.parse('$baseUrl/susceptibility/habitations'),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body);
    }

    throw Exception(
      'Susceptibility request failed: ${response.statusCode}',
    );
  }

  static Future<dynamic> assessFlood(File image) async {
    return _uploadImage(
      endpoint: '/flood-risk/',
      image: image,
    );
  }

  static Future<dynamic> assessLandslide(File image) async {
    return _uploadImage(
      endpoint: '/landslide-risk/',
      image: image,
    );
  }

  static Future<dynamic> _uploadImage({
    required String endpoint,
    required File image,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl$endpoint'),
    );

    request.files.add(
      await http.MultipartFile.fromPath(
        'file',
        image.path,
      ),
    );

    final streamedResponse = await request.send();

    final response = await http.Response.fromStream(
      streamedResponse,
    );

    if (response.statusCode >= 200 &&
        response.statusCode < 300) {
      if (response.body.isEmpty) {
        return {};
      }

      return jsonDecode(response.body);
    }

    throw Exception(
      '$endpoint failed: '
      '${response.statusCode} ${response.body}',
    );
  }
}