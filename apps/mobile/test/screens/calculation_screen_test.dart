import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/models/recognition_result.dart';
import 'package:hausa_mobile/navigation/app_routes.dart';
import 'package:hausa_mobile/screens/calculation_screen.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/hausa_tts_engine.dart';

import '../support/fake_hausa_tts.dart';

/// Écran de calcul : il montre ce que le serveur a répondu — et le **dit**.
///
/// L'utilisateur cible ne lit pas : un écran muet ne lui apprend rien. Ces
/// tests vérifient donc autant l'affichage que la prononciation, y compris son
/// refus de prononcer un énoncé incomplet.
void main() {
  late List<Uint8List> played;

  setUp(() => played = <Uint8List>[]);

  RecognitionResult result({RecognizedExpression? expression}) {
    return RecognitionResult(
      id: 'aaaaaaaa-0000-4000-8000-000000000001',
      recognizedNumber: null,
      hausaText: expression?.hausaText ?? '',
      normalizedText: '',
      confidence: 0.9,
      decision: Decision.accept,
      modelVersion: 'mock-1.0.0',
      grammarVersion: '1.4.0',
      expression: expression,
    );
  }

  Future<void> pump(
    WidgetTester tester,
    RecognitionResult value, {
    bool failTts = false,
  }) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          hausaSpeakerProvider.overrideWithValue(
            fakeHausaSpeaker(
              played: played,
              failure: failTts
                  ? const HausaTtsException(
                      'SYNTHESIS_FAILED',
                      'Le modèle local est indisponible.',
                    )
                  : null,
            ),
          ),
        ],
        child: MaterialApp(home: CalculationScreen(result: value)),
      ),
    );
    // Évite pumpAndSettle : il avance l'horloge factice par pas de 100 ms et
    // consomme donc une partie du délai de répétition que ces tests mesurent.
    await tester.pump();
    await tester.pump();
  }

  testWidgets('affiche l’opération et le résultat, jamais la forme hausa', (
    tester,
  ) async {
    await pump(
      tester,
      result(
        expression: const RecognizedExpression(
          left: 23,
          operator: '+',
          right: 15,
          hausaText: 'ashirin da uku a ƙara goma sha biyar',
          result: 38,
          resultHausaText: 'talatin da takwas',
        ),
      ),
    );

    expect(find.text('23 + 15'), findsOneWidget);
    expect(find.text('38'), findsOneWidget);
    expect(find.text('talatin da takwas'), findsNothing);
    expect(find.text('ashirin da uku a ƙara goma sha biyar'), findsNothing);
    expect(find.byKey(const Key('calculation-refusal')), findsNothing);
  });

  testWidgets('affiche le reste d’une division sans l’arrondir', (
    tester,
  ) async {
    await pump(
      tester,
      result(
        expression: const RecognizedExpression(
          left: 103,
          operator: '/',
          right: 5,
          hausaText: '—',
          result: 20,
          remainder: 3,
          resultHausaText: 'ashirin saura uku',
        ),
      ),
    );

    expect(find.text('20 reste 3'), findsOneWidget);
    expect(find.text('ashirin saura uku'), findsNothing);
  });

  testWidgets('un refus n’affiche aucun nombre', (tester) async {
    await pump(
      tester,
      result(
        expression: const RecognizedExpression(
          left: 3,
          operator: '-',
          right: 5,
          hausaText: 'uku a hidda biyar',
          refusalCode: 'NEGATIVE_RESULT',
        ),
      ),
    );

    expect(find.byKey(const Key('calculation-result')), findsNothing);
    expect(find.byKey(const Key('calculation-refusal')), findsOneWidget);
    expect(find.textContaining('négatif'), findsOneWidget);
  });

  // --------------------------------------------------------------------- //
  // AC5 — le résultat doit être DIT, pas seulement affiché
  // --------------------------------------------------------------------- //

  const RecognizedExpression sum = RecognizedExpression(
    left: 23,
    operator: '+',
    right: 15,
    hausaText: 'ashirin da uku a ƙara goma sha biyar',
    result: 38,
    resultHausaText: 'talatin da takwas',
  );

  testWidgets('prononce le résultat dès l’affichage', (tester) async {
    await pump(tester, result(expression: sum));

    expect(
      played,
      hasLength(1),
      reason: 'le résultat doit être dit sans action',
    );
  });

  testWidgets('ne répète pas avant deux secondes', (tester) async {
    await pump(tester, result(expression: sum));
    await tester.pump();

    expect(played, hasLength(1));
  });

  testWidgets('répète le résultat toutes les deux secondes', (tester) async {
    await pump(tester, result(expression: sum));
    expect(played, hasLength(1));

    await tester.pump(const Duration(milliseconds: 1999));
    expect(played, hasLength(1));

    await tester.pump(const Duration(milliseconds: 1));
    await tester.pump();
    expect(played, hasLength(2));

    await tester.pump(calculationRepeatDelay);
    await tester.pump();
    expect(played, hasLength(3));
  });

  testWidgets('la boucle s’arrête en quittant l’écran', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          hausaSpeakerProvider.overrideWithValue(
            fakeHausaSpeaker(played: played),
          ),
        ],
        child: MaterialApp(
          home: Builder(
            builder: (BuildContext context) => Center(
              child: FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        CalculationScreen(result: result(expression: sum)),
                  ),
                ),
                child: const Text('ouvrir'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('ouvrir'));
    await tester.pumpAndSettle();
    expect(played, hasLength(1));

    await tester.tap(find.byKey(const Key('record-new-calculation-button')));
    await tester.pumpAndSettle();

    await tester.pump(const Duration(seconds: 6));
    expect(
      played,
      hasLength(1),
      reason: 'la boucle doit s’arrêter quand l’écran est quitté',
    );
  });

  testWidgets('ne garde qu’un bouton pour lancer une nouvelle opération', (
    tester,
  ) async {
    await pump(tester, result(expression: sum));

    expect(find.byKey(const Key('calculation-replay-button')), findsNothing);
    expect(find.byKey(const Key('calculation-home-button')), findsNothing);
    expect(
      find.byKey(const Key('record-new-calculation-button')),
      findsOneWidget,
    );
    expect(played, hasLength(1));
  });

  testWidgets('prononce le refus au lieu de se taire', (tester) async {
    await pump(
      tester,
      result(
        expression: const RecognizedExpression(
          left: 3,
          operator: '-',
          right: 5,
          hausaText: 'uku a hidda biyar',
          refusalCode: 'NEGATIVE_RESULT',
        ),
      ),
    );

    expect(played, hasLength(1), reason: 'un silence passerait pour une panne');
  });

  testWidgets('une panne du TTS local fait taire l’énoncé et le signale', (
    tester,
  ) async {
    await pump(tester, result(expression: sum), failTts: true);

    expect(played, isEmpty);
    expect(
      find.byKey(const Key('calculation-speech-unavailable')),
      findsOneWidget,
    );
  });

  testWidgets('l’écran reste lisible quand le TTS local échoue', (
    tester,
  ) async {
    await pump(tester, result(expression: sum), failTts: true);

    expect(played, isEmpty);
    expect(find.text('38'), findsOneWidget);
  });

  testWidgets('la route refuse un argument sans opération', (tester) async {
    final Route<dynamic>? route = AppRoutes.onGenerateRoute(
      RouteSettings(name: AppRoutes.calculation, arguments: result()),
    );
    expect(route, isNotNull);

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (BuildContext context) => FilledButton(
            onPressed: () => Navigator.of(context).push(route!),
            child: const Text('ouvrir la route'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('ouvrir la route'));
    await tester.pumpAndSettle();
    // L'écran de calcul n'est jamais atteint sans expression : la route
    // bascule sur l'écran d'arguments invalides plutôt que d'afficher du vide.
    expect(find.byKey(const Key('calculation-screen')), findsNothing);
    expect(
      find.byKey(const Key('invalid-route-arguments-screen')),
      findsOneWidget,
    );
  });
}
