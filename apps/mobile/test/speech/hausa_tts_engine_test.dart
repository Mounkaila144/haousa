import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/speech/hausa_tts_engine.dart';

class _UnusedBundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) {
    throw StateError('Le chargement des assets ne devait pas être atteint.');
  }
}

void main() {
  group('résolution du locuteur', () {
    // La voix est mono-locuteur : elle est entraînée sur une seule personne.
    // L'ancienne contrainte — un locuteur `M3` à l'identifiant 1 — venait d'un
    // modèle multi-locuteurs et refuserait de charger la nouvelle voix.
    test('un modèle mono-locuteur donne l’identifiant 0', () {
      expect(resolveSpeakerId('{"num_speakers": 1}'), 0);
    });

    test('refuse un modèle multi-locuteurs plutôt que d’en choisir un', () {
      // Deviner reviendrait à changer de voix à chaque révision du modèle,
      // sans que rien ne le signale.
      expect(
        () => resolveSpeakerId(
          '{"num_speakers": 8, "speaker_id_map": {"F2": 0, "M3": 1}}',
        ),
        throwsA(
          isA<HausaTtsException>().having(
            (e) => e.code,
            'code',
            'MULTI_SPEAKER_MODEL',
          ),
        ),
      );
    });

    test('refuse un décompte de locuteurs absent ou absurde', () {
      for (final String config in <String>['{}', '{"num_speakers": 0}']) {
        expect(
          () => resolveSpeakerId(config),
          throwsA(
            isA<HausaTtsException>().having(
              (e) => e.code,
              'code',
              'INVALID_SPEAKER_COUNT',
            ),
          ),
        );
      }
    });

    test('refuse un JSON invalide', () {
      expect(
        () => resolveSpeakerId('pas du json'),
        throwsA(
          isA<HausaTtsException>().having(
            (e) => e.code,
            'code',
            'INVALID_CONFIG',
          ),
        ),
      );
    });
  });

  test('normalise en minuscules, apostrophe ASCII et Unicode NFD', () {
    expect(normalizeHausaTtsText('  TASA’IN   DA HUƊU  '), "tasa'in da huɗu");
  });

  test('translittère ƙ en q, comme le corpus d’entraînement', () {
    // `ƙ` n'existe pas dans la table du modèle : le corpus a été écrit avec
    // `q`. Sans la même substitution ici, `a ƙara` serait refusé au chargement.
    expect(normalizeHausaTtsText('a ƙara'), 'a qara');
    expect(normalizeHausaTtsText('ɗari a ƙara jikka'), contains('a qara'));
  });

  test('laisse intactes les implosives présentes dans la table', () {
    // `ɗ` et `ɓ` sont de l'IPA : le modèle les connaît, on n'y touche pas.
    expect(normalizeHausaTtsText('ɗari'), 'ɗari'.toLowerCase());
    expect(normalizeHausaTtsText('huɗu'), contains('u'));
  });

  test('refuse les chiffres avant tout chargement du modèle', () async {
    final HausaTtsEngine engine = HausaTtsEngine(bundle: _UnusedBundle());
    await expectLater(
      engine.synthesizeWav('38'),
      throwsA(
        isA<HausaTtsException>().having(
          (e) => e.code,
          'code',
          'DIGITS_FORBIDDEN',
        ),
      ),
    );
    await engine.dispose();
  });
}
