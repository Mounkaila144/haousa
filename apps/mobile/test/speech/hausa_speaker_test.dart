import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/hausa_tts_engine.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';

import '../support/fake_hausa_tts.dart';

void main() {
  group('construction des énoncés', () {
    test('conserve tous les mots canoniques dans l’ordre', () {
      expect(utteranceFromHausa('talatin da takwas'), const <VoiceSegment>[
        VoiceSegment.word('talatin'),
        VoiceSegment.word('da'),
        VoiceSegment.word('takwas'),
      ]);
    });

    test('ignore les espaces superflus', () {
      expect(utteranceFromHausa('  talatin   da '), hasLength(2));
    });

    test('la confirmation devient une phrase hausa complète', () {
      final List<VoiceSegment> utterance = confirmationUtterance(
        utteranceFromHausa('talatin da takwas'),
      );
      expect(
        utteranceToHausaText(utterance),
        'Shin wannan ne? talatin da takwas',
      );
    });

    test('une opération et son résultat forment une phrase hausa complète', () {
      final List<VoiceSegment> utterance = answerUtterance(
        utteranceFromHausa('ashirin da uku a ƙara goma sha biyar'),
        utteranceFromHausa('talatin da takwas'),
      );
      expect(
        utteranceToHausaText(utterance),
        'ashirin da uku a ƙara goma sha biyar '
        'Sakamakon shi ne talatin da takwas',
      );
    });

    test('le refus et la répétition sont centralisés en hausa', () {
      expect(
        utteranceToHausaText(refusalUtterance()),
        'Ba zan iya bayar da amsa ba.',
      );
      expect(
        utteranceToHausaText(repeatUtterance()),
        'Da fatan za a sake magana.',
      );
    });
  });

  group('synthèse locale', () {
    test('envoie la forme résultat en mots en un seul appel TTS', () async {
      final List<Uint8List> played = <Uint8List>[];
      final List<String> synthesized = <String>[];
      final HausaSpeaker speaker = fakeHausaSpeaker(
        played: played,
        synthesized: synthesized,
      );

      final SpeechOutcome outcome = await speaker.speak(
        utteranceFromHausa('talatin da takwas'),
      );

      expect(outcome, SpeechOutcome.spoken);
      expect(synthesized, <String>['talatin da takwas']);
      expect(played, hasLength(1));
    });

    test('un énoncé vide ne lance pas le moteur', () async {
      final List<Uint8List> played = <Uint8List>[];
      final HausaSpeaker speaker = fakeHausaSpeaker(played: played);
      expect(await speaker.speak(<VoiceSegment>[]), SpeechOutcome.incomplete);
      expect(played, isEmpty);
    });

    test('une panne de synthèse est claire et aucune audio n’est jouée', () async {
      final List<Uint8List> played = <Uint8List>[];
      final HausaSpeaker speaker = fakeHausaSpeaker(
        played: played,
        failure: const HausaTtsException(
          'MULTI_SPEAKER_MODEL',
          'Ce modèle porte plusieurs locuteurs.',
        ),
      );

      expect(
        await speaker.speak(utteranceFromHausa('talatin')),
        SpeechOutcome.incomplete,
      );
      expect(speaker.lastError, contains('locuteurs'));
      expect(played, isEmpty);
    });

    test('une panne de lecture ne fait pas tomber l’écran', () async {
      final FakeHausaTtsSynthesizer synthesizer = FakeHausaTtsSynthesizer();
      final HausaSpeaker speaker = HausaSpeaker(
        synthesizer: synthesizer,
        play: (_) async => throw Exception('haut-parleur occupé'),
      );
      expect(
        await speaker.speak(utteranceFromHausa('talatin')),
        SpeechOutcome.failed,
      );
    });
  });
}
