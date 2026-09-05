import 'api_service.dart';
class RelocationService {
  static Future<dynamic> getRelocationPlan({
    String region = 'assam',
  }) {
    return ApiService.get(
      '/relocation-plan/?region=$region',
    );
  }

  static Future<dynamic> createRelocationPlan(
    List<Map<String, dynamic>> habitations, {
    String region = 'assam',
  }) {
    return ApiService.post(
      '/relocation-plan/habitations?region=$region',
      body: habitations,
    );
  }

  static Future<dynamic> getHabitationAdvisory(
    String habitationId,
  ) {
    return ApiService.get(
      '/advisory/$habitationId',
    );
  }
}