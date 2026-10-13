import 'package:dogovor/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Журнал звонков открывает разбор и чат', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const DogovorApp());
    await tester.pumpAndSettle();

    expect(find.text('Вызовы'), findsWidgets);
    final name = find.descendant(
      of: find.byKey(const Key('recents')),
      matching: find.text('Алексей Морозов'),
    );
    expect(name, findsOneWidget);

    await tester.tap(name);
    await tester.pumpAndSettle();
    expect(find.text('О чём говорили'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);

    await tester.tap(find.byIcon(Icons.arrow_back_ios_new_rounded));
    await tester.pumpAndSettle();
    expect(find.text('Вызовы'), findsWidgets);
  });
}
