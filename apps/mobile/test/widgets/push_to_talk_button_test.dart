import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/widgets/push_to_talk_button.dart';

void main() {
  late List<String> journal;
  late List<bool> signaux;
  late DateTime horloge;

  Future<void> pumpButton(WidgetTester tester, {bool enabled = true}) {
    return tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: PushToTalkButton(
              enabled: enabled,
              onStart: () => journal.add('début'),
              onEnd: (PushToTalkOutcome outcome) => journal.add(outcome.name),
              playCue: signaux.add,
              now: () => horloge,
            ),
          ),
        ),
      ),
    );
  }

  setUp(() {
    journal = <String>[];
    signaux = <bool>[];
    horloge = DateTime(2026);
  });

  Future<void> hold(WidgetTester tester, Duration duration) {
    horloge = horloge.add(duration);
    return tester.pump(duration);
  }

  testWidgets('un appui tenu puis relâché envoie l’enregistrement', (
    WidgetTester tester,
  ) async {
    await pumpButton(tester);
    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('push-to-talk'))),
    );
    await hold(tester, const Duration(milliseconds: 900));
    await gesture.up();
    await tester.pump();

    expect(journal, <String>['début', 'released']);
    expect(signaux, <bool>[true, false]);
  });

  testWidgets('un appui trop bref n’envoie rien', (WidgetTester tester) async {
    await pumpButton(tester);
    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('push-to-talk'))),
    );
    await hold(tester, const Duration(milliseconds: 120));
    await gesture.up();
    await tester.pump();

    expect(journal, <String>['début', 'cancelled']);
  });

  testWidgets('glisser vers le haut annule', (WidgetTester tester) async {
    await pumpButton(tester);
    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('push-to-talk'))),
    );
    await hold(tester, const Duration(milliseconds: 600));
    await gesture.moveBy(const Offset(0, -140));
    await tester.pump();
    await gesture.up();
    await tester.pump();

    expect(journal, <String>['début', 'cancelled']);
  });

  testWidgets('un petit mouvement reste un envoi volontaire', (
    WidgetTester tester,
  ) async {
    await pumpButton(tester);
    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('push-to-talk'))),
    );
    await hold(tester, const Duration(milliseconds: 600));
    await gesture.moveBy(const Offset(0, -40));
    await gesture.up();
    await tester.pump();

    expect(journal, <String>['début', 'released']);
  });

  testWidgets('désactivé, le bouton ne démarre rien', (
    WidgetTester tester,
  ) async {
    await pumpButton(tester, enabled: false);
    final TestGesture gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('push-to-talk'))),
    );
    await hold(tester, const Duration(milliseconds: 700));
    await gesture.up();
    await tester.pump();

    expect(journal, isEmpty);
    expect(signaux, isEmpty);
  });
}
