import 'package:flutter_test/flutter_test.dart';
import 'package:sar_app/main.dart';

void main() {
  testWidgets('DISHA app loads', (WidgetTester tester) async {
    await tester.pumpWidget(const DishaApp());

    expect(find.byType(DishaApp), findsOneWidget);
  });
}