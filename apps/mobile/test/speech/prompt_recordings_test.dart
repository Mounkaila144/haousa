import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/hausa_tts_engine.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';
import 'package:hausa_mobile/speech/wav.dart';

/// Le modèle ne prononce que des **nombres**. Les phrases sont rejouées.
///
/// Les trois consignes fixes ont été volontairement écartées du corpus
/// d'entraînement : elles se disent toujours à l'identique, et l'application
/// peut rejouer leur enregistrement. Le modèle ne les a donc jamais vues — lui
/// confier « Shin wannan ne ? » lui ferait inventer des mots inconnus, sans
/// qu'aucune erreur ne le signale.
class _RecordingSynthesizer implements HausaTtsSynthesizer {
  final List<String> demandes = <String>[];

  @override
  Future<Uint8List> synthesizeWav(String hausaText) async {
    demandes.add(hausaText);
    return wavFromPcm(Uint8List(320));
  }

  @override
  Future<void> dispose() async {}
}

/// Ne fournit aucun enregistrement : simule un WAV non encore embarqué.
class _BundleVide extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) async =>
      throw StateError('asset absent : $key');
}

class _FakeBundle extends CachingAssetBundle {
  final List<String> charges = <String>[];

  @override
  Future<ByteData> load(String key) async {
    charges.add(key);
    return ByteData.view(wavFromPcm(Uint8List(320)).buffer);
  }
}

void main() {
  late _RecordingSynthesizer synthesizer;
  late _FakeBundle bundle;
  late List<Uint8List> joues;
  late HausaSpeaker speaker;

  setUp(() {
    synthesizer = _RecordingSynthesizer();
    bundle = _FakeBundle();
    joues = <Uint8List>[];
    speaker = HausaSpeaker(
      synthesizer: synthesizer,
      bundle: bundle,
      play: (Uint8List wav) async => joues.add(wav),
    );
  });

  test('une consigne seule est rejouée, jamais synthétisée', () async {
    final SpeechOutcome outcome = await speaker.speak(refusalUtterance());

    expect(outcome, SpeechOutcome.spoken);
    expect(
      synthesizer.demandes,
      isEmpty,
      reason: 'le modèle n’a jamais appris cette phrase',
    );
    expect(bundle.charges, <String>['assets/voice/sys_cannot_answer.wav']);
    expect(joues, hasLength(1));
  });

  test('une confirmation joue la consigne puis synthétise le montant', () async {
    // C'est le cas mêlé : « Shin wannan ne ? » suivi d'un montant. Chacun doit
    // emprunter sa propre voie.
    final List<VoiceSegment> utterance = confirmationUtterance(
      utteranceFromHausa('jikka biyar'),
    );

    await speaker.speak(utterance);

    expect(bundle.charges, <String>['assets/voice/sys_confirm.wav']);
    expect(synthesizer.demandes, <String>['jikka biyar']);
    expect(joues, hasLength(2), reason: 'consigne puis montant, dans l’ordre');
  });

  test('un montant seul ne touche à aucun enregistrement', () async {
    await speaker.speak(utteranceFromHausa('ɗari da hamsin'));

    expect(bundle.charges, isEmpty);
    expect(synthesizer.demandes, <String>['ɗari da hamsin']);
  });

  test('aucun texte de phrase n’atteint jamais le synthétiseur', () async {
    for (final List<VoiceSegment> utterance in <List<VoiceSegment>>[
      refusalUtterance(),
      repeatUtterance(),
      confirmationUtterance(utteranceFromHausa('goma')),
    ]) {
      await speaker.speak(utterance);
    }

    // Les mots des trois consignes, tels que `HausaMessages` les porte.
    const List<String> interdits = <String>[
      'Shin',
      'wannan',
      'zan',
      'amsa',
      'fatan',
      'magana',
    ];
    for (final String demande in synthesizer.demandes) {
      for (final String mot in interdits) {
        expect(
          demande.toLowerCase(),
          isNot(contains(mot.toLowerCase())),
          reason: 'ce mot n’est pas dans le corpus d’entraînement : $mot',
        );
      }
    }
  });

  test('une consigne absente ne fait pas perdre le résultat', () async {
    // Régression : l'écran Session disait l'opération puis se taisait. Le
    // connecteur « Sakamakon shi ne » n'étant pas encore enregistré, le
    // chargement échouait et emportait la RÉPONSE avec lui.
    final HausaSpeaker fragile = HausaSpeaker(
      synthesizer: synthesizer,
      bundle: _BundleVide(),
      play: (Uint8List wav) async => joues.add(wav),
    );

    final SpeechOutcome outcome = await fragile.speak(<VoiceSegment>[
      ...utteranceFromHausa('ashirin da uku'),
      const VoiceSegment.prompt(kPromptResult),
      ...utteranceFromHausa('talatin da takwas'),
    ]);

    expect(
      synthesizer.demandes,
      <String>['ashirin da uku', 'talatin da takwas'],
      reason: 'l’opération ET le résultat doivent être dits',
    );
    expect(joues, hasLength(2));
    // Le manque est signalé, sans faire taire l'application.
    expect(outcome, SpeechOutcome.incomplete);
    expect(fragile.lastError, isNotNull);
  });

  test('chaque consigne connue a son enregistrement', () {
    for (final String cle in <String>[
      kPromptConfirm,
      kPromptCannotAnswer,
      kPromptRepeat,
      // « Sakamakon shi ne » — le résultat est. Elle vit dans
      // `answerUtterance`, et avait échappé au premier corpus.
      kPromptResult,
    ]) {
      expect(recordingForPrompt(cle), startsWith('assets/voice/'));
    }
    expect(() => recordingForPrompt('inconnu'), throwsArgumentError);
  });
}
