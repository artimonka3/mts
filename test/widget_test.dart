import 'package:dogovor/main.dart';
import 'package:dogovor/widgets/common.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Макет показывает договорённости и экраны', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const DogovorApp());
    await tester.pumpAndSettle();

    expect(find.byType(Wordmark), findsOneWidget);
    expect(find.textContaining('просрочено'), findsWidgets);
    expect(find.textContaining('Алексей Морозов'), findsWidgets);

    await tester.tap(find.byKey(const Key('tab-calls')));
    await tester.pumpAndSettle();
    expect(find.text('Звонки'), findsWidgets);

    await tester.tap(find.byKey(const Key('tab-clients')));
    await tester.pumpAndSettle();
    expect(find.text('Клиенты'), findsWidgets);

    await tester.tap(find.byKey(const Key('tab-today')));
    await tester.pumpAndSettle();

    final task = find.textContaining('alexey@belstroy.by');
    await tester.ensureVisible(task);
    await tester.tap(task);
    await tester.pumpAndSettle();
    expect(find.text('Суть разговора'), findsOneWidget);

    final scrollable = find.byType(Scrollable).last;
    await tester.scrollUntilVisible(
      find.text('Расшифровка'),
      300,
      scrollable: scrollable,
    );
    expect(find.text('Расшифровка'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byIcon(Icons.arrow_back_rounded),
      -400,
      scrollable: scrollable,
    );
    await tester.tap(find.byIcon(Icons.arrow_back_rounded));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('record')));
    await tester.pumpAndSettle();
    expect(find.text('Запишите разговор'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.close_rounded));
    await tester.pumpAndSettle();
    expect(find.text('Запишите разговор'), findsNothing);
    expect(find.byKey(const Key('record')), findsOneWidget);
  });
}
