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
  const String validConfig = '''
  {
    "num_speakers": 8,
    "speaker_id_map": {"F2": 0, "M3": 1, "M2": 2}
  }
  ''';

  group('sélection dynamique de M3', () {
    test('l’asset livré contient réellement M3=1', () {
      final String config = File(
        'assets/models/hausa_tts/model.onnx.json',
      ).readAsStringSync();
      expect(resolveM3SpeakerId(config), 1);
    });

    test('lit M3 depuis speaker_id_map', () {
      expect(resolveM3SpeakerId(validConfig), 1);
    });

    test('refuse clairement une configuration sans M3', () {
      expect(
        () => resolveM3SpeakerId(
          '{"num_speakers": 8, "speaker_id_map": {"M2": 2}}',
        ),
        throwsA(
          isA<HausaTtsException>()
              .having((e) => e.code, 'code', 'M3_NOT_FOUND')
              .having((e) => e.message, 'message', contains('M3')),
        ),
      );
    });

    test('refuse un changement silencieux de l’identifiant attendu', () {
      expect(
        () => resolveM3SpeakerId(
          '{"num_speakers": 8, "speaker_id_map": {"M3": 4}}',
        ),
        throwsA(
          isA<HausaTtsException>().having(
            (e) => e.code,
            'code',
            'M3_ID_MISMATCH',
          ),
        ),
      );
    });
  });

  test('le manifeste impose le frontend graphémique sans phonémiseur', () {
    final Map<String, dynamic> manifest =
        jsonDecode(
              File(
                'assets/models/hausa_tts/asset_manifest.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>;
    expect(manifest['runtime'], 'sherpa_onnx');
    expect(manifest['frontend'], 'characters');
    expect(manifest['phonemizer_resources'], isEmpty);
    expect(manifest['voice'], 'M3');
  });

  test('normalise en minuscules, apostrophe ASCII et Unicode NFD', () {
    expect(normalizeHausaTtsText('  TASA’IN   DA HUƊU  '), "tasa'in da huɗu");
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
