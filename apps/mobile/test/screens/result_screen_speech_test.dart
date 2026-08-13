import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/feedback/feedback_models.dart';
import 'package:hausa_mobile/models/recognition_result.dart';
import 'package:hausa_mobile/screens/result_screen.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';

import '../support/fake_hausa_tts.dart';

/// Écran Résultat d'un « nombre seul » : il **dit** le nombre reconnu.
///
/// La forme hausa n'est jamais écrite à l'écran (cf. `HausaNumberDisplay`) :
/// sans restitution vocale, cet écran ne rend rien à quelqu'un qui ne lit pas.
///
/// Ces tests fixent surtout la forme **prononcée** : `jikka` (1 000) s'écrit
/// avec la gémination mais se dit `jikk ka`, la synthèse embarquée lisant des
/// caractères et perdant le `kk`. La valeur vient du serveur et n'est jamais
/// recomposée sur l'appareil.
void main() {
  late List<Uint8List> played;
  late List<String> synthesized;

  setUp(() {
    played = <Uint8List>[];
    synthesized = <String>[];
  });

  RecognitionResult result({
    required int number,
    required String hausaText,
    String spokenText = '',
  }) {
    return RecognitionResult(
      id: 'aaaaaaaa-0000-4000-8000-000000000001',
      recognizedNumber: number,
      hausaText: hausaText,
      spokenText: spokenText,
      normalizedText: hausaText,
      confidence: 0.95,
      decision: Decision.accept,
      modelVersion: 'mock-1.0.0',
      grammarVersion: '2.4.0-hausa',
    );
  }

  Future<void> pump(
    WidgetTester tester, {
    required RecognitionResult value,
    ConfirmedResult? confirmed,
  }) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          hausaSpeakerProvider.overrideWithValue(
            fakeHausaSpeaker(played: played, synthesized: synthesized),
          ),
        ],
        child: MaterialApp(
          home: ResultScreen(result: value, confirmed: confirmed),
        ),
      ),
    );
    await tester.pump();
    await tester.pump();
  }

  testWidgets('prononce la forme parlée du serveur, pas la forme écrite', (
    tester,
  ) async {
    await pump(
      tester,
      value: result(number: 1000, hausaText: 'jikka', spokenText: 'jikk ka'),
    );

    expect(synthesized, <String>['jikk ka']);
    expect(
      synthesized,
      isNot(contains('jikka')),
      reason: 'la forme écrite serait lue « jika » par la synthèse',
    );
    expect(played, hasLength(1));
  });

  testWidgets('retombe sur la forme écrite quand aucune forme parlée n’est '
      'fournie', (tester) async {
    await pump(
      tester,
      value: result(number: 100, hausaText: 'ɗari', spokenText: ''),
    );

    expect(synthesized, <String>['ɗari']);
  });

  testWidgets('dit le candidat confirmé, pas la proposition principale', (
    tester,
  ) async {
    final RecognitionResult recognition = result(
      number: 90,
      hausaText: 'tasa\'in',
      spokenText: '',
    );

    await pump(
      tester,
      value: recognition,
      confirmed: ConfirmedResult(
        recognition: recognition,
        number: 1000,
        hausaText: 'jikka',
        spokenText: 'jikk ka',
      ),
    );

    expect(synthesized, <String>['jikk ka']);
    expect(find.text('1000'), findsOneWidget);
  });

  testWidgets('ne parle qu’une fois malgré les reconstructions', (
    tester,
  ) async {
    await pump(
      tester,
      value: result(number: 1000, hausaText: 'jikka', spokenText: 'jikk ka'),
    );
    await tester.pump();
    await tester.pump();

    expect(played, hasLength(1));
  });
}
