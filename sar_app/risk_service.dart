import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'api_service.dart';

class RiskService {
  static const String baseUrl = 'http://10.102.59.67:8000';

  static Future<dynamic> getRedZones() async {
    return ApiService.get('/red-zones/');
  }

  static Future<dynamic> getLiveRisk() async {
    return ApiService.get('/live-risk/');
  }

  static Future<dynamic> getSusceptibility() async {
    return ApiService.get('/susceptibility/habitations');
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