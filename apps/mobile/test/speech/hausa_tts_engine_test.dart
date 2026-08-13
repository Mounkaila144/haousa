import 'dart:convert';
import 'dart:io';

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
  group('le modèle réellement livré', () {
    // Ces contrôles portent sur l'asset embarqué, pas sur un JSON fabriqué :
    // c'est ce couple-là qui part sur le téléphone. L'ancienne contrainte `M3`
    // n'aurait été détectée qu'ici, après des heures d'entraînement.
    Map<String, dynamic> config() =>
        jsonDecode(
              File('assets/models/hausa_tts/model.onnx.json').readAsStringSync(),
            )
            as Map<String, dynamic>;

    test('est mono-locuteur et se résout sans choix à faire', () {
      final String brut = File(
        'assets/models/hausa_tts/model.onnx.json',
      ).readAsStringSync();
      expect(config()['num_speakers'], 1);
      expect(resolveSpeakerId(brut), 0);
    });

    test('lit des caractères, jamais des phonèmes espeak', () {
      // espeak-ng ne connaît pas le hausa : s'il était appelé, il
      // phonétiserait le texte en français avant d'atteindre le réseau.
      expect(config()['phoneme_type'], 'text');
    });

    test('sa table couvre tout ce que l’application prononce', () {
      // Un caractère absent serait ignoré EN SILENCE par le frontend.
      final Map<String, dynamic> carte =
          config()['phoneme_id_map'] as Map<String, dynamic>;
      const List<String> enonces = <String>[
        'sifili',
        'ɗari da hamsin',
        'jikka biyar da ɗari',
        'dubu goma',
        "tasa'in da tara",
        'goma sha ɗaya',
        'ɗari a ƙara jikka',
        'ɗari sau ɗari',
        'jikka saura ɗari',
      ];
      for (final String enonce in enonces) {
        for (final int rune in normalizeHausaTtsText(enonce).runes) {
          final String caractere = String.fromCharCode(rune);
          expect(
            carte.containsKey(caractere),
            isTrue,
            reason: 'absent de la table du modèle : ${jsonEncode(caractere)} '
                '(énoncé « $enonce »)',
          );
        }
      }
    });

    test('le manifeste décrit les tailles réelles des fichiers', () {
      final Map<String, dynamic> manifeste =
          jsonDecode(
                File(
                  'assets/models/hausa_tts/asset_manifest.json',
                ).readAsStringSync(),
              )
              as Map<String, dynamic>;
      final Map<String, dynamic> fichiers =
          manifeste['files'] as Map<String, dynamic>;
      for (final String nom in <String>[
        'model.onnx',
        'model.onnx.json',
        'tokens.txt',
      ]) {
        final int attendu =
            (fichiers[nom] as Map<String, dynamic>)['bytes'] as int;
        expect(File('assets/models/hausa_tts/$nom').lengthSync(), attendu);
      }
    });
  });

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
