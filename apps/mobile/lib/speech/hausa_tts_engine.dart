/// Moteur Piper/Sherpa-ONNX embarqué pour la voix hausa M3.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa_onnx;
import 'package:unorm_dart/unorm_dart.dart' as unorm;

import 'package:hausa_mobile/speech/wav.dart';

const String kHausaTtsVoice = 'M3';
const int kExpectedM3SpeakerId = 1;
const String kHausaTtsAssetRoot = 'assets/models/hausa_tts';

class HausaTtsException implements Exception {
  const HausaTtsException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => 'HausaTtsException($code): $message';
}

/// Contrat étroit utilisé par [HausaSpeaker] et facilement remplaçable en test.
abstract interface class HausaTtsSynthesizer {
  Future<Uint8List> synthesizeWav(String hausaText);

  Future<void> dispose();
}

/// Résout M3 depuis le JSON Piper. Il n'existe aucun locuteur de secours.
int resolveM3SpeakerId(String configJson) {
  final Object? decoded;
  try {
    decoded = jsonDecode(configJson);
  } on FormatException catch (error) {
    throw HausaTtsException('INVALID_CONFIG', 'JSON Piper invalide : $error');
  }
  if (decoded is! Map<String, dynamic>) {
    throw const HausaTtsException(
      'INVALID_CONFIG',
      'La configuration Piper doit être un objet JSON.',
    );
  }
  final Object? speakerMap = decoded['speaker_id_map'];
  if (speakerMap is! Map<String, dynamic>) {
    throw const HausaTtsException(
      'SPEAKER_MAP_MISSING',
      'Le champ speaker_id_map est absent de model.onnx.json.',
    );
  }
  if (!speakerMap.containsKey(kHausaTtsVoice)) {
    throw const HausaTtsException(
      'M3_NOT_FOUND',
      'La voix obligatoire M3 est absente de speaker_id_map. Aucune autre voix ne sera utilisée.',
    );
  }
  final Object? rawId = speakerMap[kHausaTtsVoice];
  if (rawId is! int) {
    throw HausaTtsException(
      'INVALID_M3_ID',
      'L’identifiant de M3 doit être un entier, reçu : $rawId.',
    );
  }
  final Object? rawCount = decoded['num_speakers'];
  if (rawCount is! int || rawId < 0 || rawId >= rawCount) {
    throw HausaTtsException(
      'INVALID_M3_ID',
      'L’identifiant M3=$rawId est hors de la plage des locuteurs.',
    );
  }
  if (rawId != kExpectedM3SpeakerId) {
    throw HausaTtsException(
      'M3_ID_MISMATCH',
      'L’identifiant M3 détecté est $rawId ; la révision validée attend $kExpectedM3SpeakerId.',
    );
  }
  return rawId;
}

/// Prétraitement prescrit par le modèle : minuscules, apostrophe ASCII et NFD.
String normalizeHausaTtsText(String text) {
  final String compact = text
      .trim()
      .toLowerCase()
      .replaceAll(RegExp('[‘’ʼ`´]'), "'")
      .replaceAll(RegExp(r'\s+'), ' ');
  return unorm.nfd(compact);
}

class HausaTtsEngine implements HausaTtsSynthesizer {
  HausaTtsEngine({AssetBundle? bundle}) : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;
  Future<_TtsWorker>? _initialization;
  Future<void> _queue = Future<void>.value();
  bool _disposed = false;

  @override
  Future<Uint8List> synthesizeWav(String hausaText) {
    final Completer<Uint8List> result = Completer<Uint8List>();
    _queue = _queue.then((_) async {
      try {
        if (_disposed) {
          throw const HausaTtsException(
            'DISPOSED',
            'Le moteur TTS hausa a déjà été libéré.',
          );
        }
        final String text = normalizeHausaTtsText(hausaText);
        if (text.isEmpty) {
          throw const HausaTtsException('EMPTY_TEXT', 'Le texte TTS est vide.');
        }
        if (RegExp('[0-9]').hasMatch(text)) {
          throw const HausaTtsException(
            'DIGITS_FORBIDDEN',
            'Les nombres doivent être convertis en mots hausa avant la synthèse.',
          );
        }
        final _TtsWorker worker = await (_initialization ??= _initialize());
        result.complete(await worker.generate(text));
      } catch (error, stackTrace) {
        result.completeError(error, stackTrace);
      }
    });
    return result.future;
  }

  Future<_TtsWorker> _initialize() async {
    final String configJson = await _bundle.loadString(
      '$kHausaTtsAssetRoot/model.onnx.json',
    );
    final int speakerId = resolveM3SpeakerId(configJson);
    final Set<String> supportedCharacters = _readSupportedCharacters(
      configJson,
    );
    if (kDebugMode) {
      debugPrint('Voix sélectionnée : $kHausaTtsVoice');
      debugPrint('Speaker ID détecté : $speakerId');
    }

    final _InstalledTtsAssets assets = await _installAssets();
    return _TtsWorker.start(
      modelPath: assets.modelPath,
      tokensPath: assets.tokensPath,
      speakerId: speakerId,
      supportedCharacters: supportedCharacters,
      debug: kDebugMode,
    );
  }

  Set<String> _readSupportedCharacters(String configJson) {
    final Map<String, dynamic> config =
        jsonDecode(configJson) as Map<String, dynamic>;
    if (config['phoneme_type'] != 'text') {
      throw const HausaTtsException(
        'UNSUPPORTED_FRONTEND',
        'Le modèle n’utilise plus le frontend graphémique attendu.',
      );
    }
    final Object? rawMap = config['phoneme_id_map'];
    if (rawMap is! Map<String, dynamic>) {
      throw const HausaTtsException(
        'TOKENS_MISSING',
        'phoneme_id_map est absent de model.onnx.json.',
      );
    }
    return rawMap.keys.where((String key) => key.length == 1).toSet();
  }

  Future<_InstalledTtsAssets> _installAssets() async {
    final String manifestText = await _bundle.loadString(
      '$kHausaTtsAssetRoot/asset_manifest.json',
    );
    final Map<String, dynamic> manifest =
        jsonDecode(manifestText) as Map<String, dynamic>;
    final Map<String, dynamic> files =
        manifest['files'] as Map<String, dynamic>? ?? <String, dynamic>{};
    const List<String> required = <String>[
      'model.onnx',
      'model.onnx.json',
      'tokens.txt',
    ];
    if (!required.every(files.containsKey)) {
      throw const HausaTtsException(
        'ASSET_MANIFEST_INVALID',
        'Le manifeste TTS ne décrit pas toutes les ressources requises.',
      );
    }

    final Directory support = await getApplicationSupportDirectory();
    final Directory directory = Directory('${support.path}/hausa_tts_v1');
    await directory.create(recursive: true);
    final File installedManifest = File(
      '${directory.path}/asset_manifest.json',
    );

    bool current =
        await installedManifest.exists() &&
        await installedManifest.readAsString() == manifestText;
    if (current) {
      for (final String name in required) {
        final File target = File('${directory.path}/$name');
        final Object? expected = (files[name] as Map<String, dynamic>)['bytes'];
        if (expected is! int ||
            !await target.exists() ||
            await target.length() != expected) {
          current = false;
          break;
        }
      }
    }

    if (!current) {
      for (final String name in required) {
        final ByteData data = await _bundle.load('$kHausaTtsAssetRoot/$name');
        final Uint8List bytes = data.buffer.asUint8List(
          data.offsetInBytes,
          data.lengthInBytes,
        );
        final File target = File('${directory.path}/$name');
        final File temporary = File('${target.path}.installing');
        await temporary.writeAsBytes(bytes, flush: true);
        if (await target.exists()) {
          await target.delete();
        }
        await temporary.rename(target.path);
      }
      await installedManifest.writeAsString(manifestText, flush: true);
    }

    return _InstalledTtsAssets(
      modelPath: '${directory.path}/model.onnx',
      tokensPath: '${directory.path}/tokens.txt',
    );
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    final Future<_TtsWorker>? initialization = _initialization;
    if (initialization != null) {
      try {
        final _TtsWorker worker = await initialization;
        await worker.dispose();
      } catch (_) {
        // Une initialisation déjà en échec n'a aucune ressource à libérer.
      }
    }
  }
}

class _InstalledTtsAssets {
  const _InstalledTtsAssets({
    required this.modelPath,
    required this.tokensPath,
  });

  final String modelPath;
  final String tokensPath;
}

class _TtsWorker {
  _TtsWorker(this._isolate, this._commands, this._supportedCharacters);

  final Isolate _isolate;
  final SendPort _commands;
  final Set<String> _supportedCharacters;
  bool _disposed = false;

  static Future<_TtsWorker> start({
    required String modelPath,
    required String tokensPath,
    required int speakerId,
    required Set<String> supportedCharacters,
    required bool debug,
  }) async {
    final ReceivePort ready = ReceivePort();
    final ReceivePort errors = ReceivePort();
    final Isolate isolate = await Isolate.spawn<List<Object>>(
      _ttsWorkerMain,
      <Object>[ready.sendPort, modelPath, tokensPath, speakerId, debug],
      onError: errors.sendPort,
      errorsAreFatal: true,
    );
    try {
      final Object? first = await Future.any<Object?>(<Future<Object?>>[
        ready.first,
        errors.first.then<Object?>((dynamic error) {
          throw HausaTtsException(
            'WORKER_INIT_FAILED',
            'Impossible de charger le modèle local M3 : $error',
          );
        }),
      ]).timeout(const Duration(minutes: 2));
      if (first is! SendPort) {
        throw HausaTtsException(
          'WORKER_INIT_FAILED',
          'Réponse inattendue du moteur TTS : $first',
        );
      }
      return _TtsWorker(isolate, first, supportedCharacters);
    } catch (_) {
      isolate.kill(priority: Isolate.immediate);
      rethrow;
    } finally {
      ready.close();
      errors.close();
    }
  }

  Future<Uint8List> generate(String text) async {
    if (_disposed) {
      throw const HausaTtsException('DISPOSED', 'Le worker TTS est arrêté.');
    }
    for (final int rune in text.runes) {
      final String character = String.fromCharCode(rune);
      if (!_supportedCharacters.contains(character)) {
        throw HausaTtsException(
          'UNSUPPORTED_CHARACTER',
          'Le caractère ${jsonEncode(character)} n’existe pas dans les tokens du modèle.',
        );
      }
    }
    final ReceivePort reply = ReceivePort();
    _commands.send(<String, Object>{
      'method': 'generate',
      'text': text,
      'reply': reply.sendPort,
    });
    final Object response = await reply.first.timeout(
      const Duration(minutes: 2),
      onTimeout: () => throw const HausaTtsException(
        'SYNTHESIS_TIMEOUT',
        'La synthèse locale M3 a dépassé deux minutes.',
      ),
    );
    reply.close();
    if (response is TransferableTypedData) {
      return response.materialize().asUint8List();
    }
    throw HausaTtsException(
      'SYNTHESIS_FAILED',
      response is String ? response : 'Réponse invalide du worker TTS.',
    );
  }

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    final ReceivePort reply = ReceivePort();
    _commands.send(<String, Object>{
      'method': 'dispose',
      'reply': reply.sendPort,
    });
    await reply.first.timeout(
      const Duration(seconds: 5),
      onTimeout: () => null,
    );
    reply.close();
    _isolate.kill(priority: Isolate.immediate);
  }
}

@pragma('vm:entry-point')
Future<void> _ttsWorkerMain(List<Object> arguments) async {
  final SendPort ready = arguments[0] as SendPort;
  final String modelPath = arguments[1] as String;
  final String tokensPath = arguments[2] as String;
  final int speakerId = arguments[3] as int;
  final bool debug = arguments[4] as bool;

  sherpa_onnx.initBindings();
  final sherpa_onnx.OfflineTts tts = sherpa_onnx.OfflineTts(
    sherpa_onnx.OfflineTtsConfig(
      model: sherpa_onnx.OfflineTtsModelConfig(
        vits: sherpa_onnx.OfflineTtsVitsModelConfig(
          model: modelPath,
          tokens: tokensPath,
          lexicon: '',
          dataDir: '',
          noiseScale: 0.667,
          noiseScaleW: 0.8,
          lengthScale: 1,
        ),
        numThreads: 2,
        debug: debug,
        provider: 'cpu',
      ),
      maxNumSenetences: 1,
    ),
  );
  final ReceivePort commands = ReceivePort();
  ready.send(commands.sendPort);

  await for (final Object? raw in commands) {
    if (raw is! Map) continue;
    final SendPort? reply = raw['reply'] as SendPort?;
    if (raw['method'] == 'dispose') {
      tts.free();
      reply?.send(true);
      commands.close();
      return;
    }
    if (raw['method'] == 'generate' && reply != null) {
      try {
        final sherpa_onnx.GeneratedAudio audio = tts.generate(
          text: raw['text'] as String,
          sid: speakerId,
          speed: 1,
        );
        if (audio.samples.isEmpty || audio.sampleRate <= 0) {
          throw const HausaTtsException(
            'EMPTY_AUDIO',
            'Sherpa-ONNX a produit un signal vide.',
          );
        }
        final Uint8List wav = wavFromFloatSamples(
          audio.samples,
          sampleRate: audio.sampleRate,
        );
        reply.send(TransferableTypedData.fromList(<Uint8List>[wav]));
      } catch (error) {
        reply.send(error.toString());
      }
    }
  }
}
