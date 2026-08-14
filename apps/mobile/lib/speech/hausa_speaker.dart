/// Restitution vocale hausa locale par Piper/Sherpa-ONNX.
library;

import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import 'package:hausa_mobile/speech/hausa_tts_engine.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';

enum SpeechOutcome { spoken, incomplete, failed }

typedef WavPlayer = Future<void> Function(Uint8List wav);

/// Les bips d'interface ne doivent pas prendre le focus audio Android pendant
/// que le micro capture encore la voix.
const AudioContextAndroid recordingCueAndroidAudioContext = AudioContextAndroid(
  contentType: AndroidContentType.sonification,
  usageType: AndroidUsageType.assistanceSonification,
  audioFocus: AndroidAudioFocus.none,
);

class HausaSpeaker {
  HausaSpeaker({required this.synthesizer, required this.play, this.bundle});

  final HausaTtsSynthesizer synthesizer;
  final WavPlayer play;

  /// Source des enregistrements de consignes. `null` : les assets de l'app.
  final AssetBundle? bundle;

  String? lastError;

  List<VoiceSegment> preferred(String canonicalText, String spokenText) =>
      preferredUtterance(canonicalText, spokenText);

  /// Charge un enregistrement, ou `null` s'il n'est pas embarqué.
  ///
  /// Renvoyer `null` plutôt que lever : l'appelant saute alors ce tronçon et
  /// prononce les autres. Une exception ferait perdre tout l'énoncé.
  Future<Uint8List?> _tryLoadRecording(String assetPath) async {
    try {
      final ByteData data = await (bundle ?? rootBundle).load(assetPath);
      return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    } catch (error) {
      if (kDebugMode) debugPrint('Consigne absente : $assetPath ($error)');
      return null;
    }
  }

  /// Dit l'énoncé, chaque tronçon par la voie qui lui revient.
  ///
  /// Les consignes fixes sont **rejouées** depuis leur enregistrement ; seuls
  /// les montants et les opérations passent par la synthèse. Le modèle a été
  /// entraîné sur les seuls nombres : lui confier « Shin wannan ne ? » lui
  /// ferait inventer des mots qu'il n'a jamais vus.
  Future<SpeechOutcome> speak(List<VoiceSegment> utterance) async {
    if (utterance.isEmpty) return SpeechOutcome.incomplete;
    try {
      bool complet = true;
      for (final VoiceChunk chunk in splitUtterance(utterance)) {
        final Uint8List? wav = chunk.isRecording
            ? await _tryLoadRecording(chunk.assetPath!)
            : await synthesizer.synthesizeWav(chunk.text!);
        if (wav == null) {
          // Consigne manquante : on la saute et on dit le reste. Un connecteur
          // absent ne doit pas emporter le RÉSULTAT, qui est l'essentiel — les
          // nombres suffisent à comprendre, le silence non.
          complet = false;
          continue;
        }
        await play(wav);
      }
      lastError = complet ? null : 'Une consigne enregistrée est absente.';
      return complet ? SpeechOutcome.spoken : SpeechOutcome.incomplete;
    } on HausaTtsException catch (error) {
      lastError = error.message;
      if (kDebugMode) debugPrint(error.toString());
      return SpeechOutcome.incomplete;
    } catch (error) {
      lastError = 'La synthèse ou la lecture audio locale a échoué.';
      if (kDebugMode) debugPrint('TTS hausa : $error');
      return SpeechOutcome.failed;
    }
  }
}

final hausaTtsEngineProvider = Provider<HausaTtsEngine>((ref) {
  final HausaTtsEngine engine = HausaTtsEngine();
  ref.onDispose(() => unawaited(engine.dispose()));
  return engine;
});

WavPlayer _createWavPlayer(Ref ref, {bool preserveRecordingFocus = false}) {
  final AudioPlayer player = AudioPlayer();
  int utteranceCount = 0;
  File? previous;

  Future<void> discard(File? file) async {
    if (file == null) return;
    try {
      await file.delete();
    } catch (_) {}
  }

  ref.onDispose(() {
    player.dispose();
    unawaited(discard(previous));
  });

  return (Uint8List wav) async {
    await player.stop();
    if (Platform.isAndroid && preserveRecordingFocus) {
      await player.setAudioContext(
        AudioContext(android: recordingCueAndroidAudioContext),
      );
    } else if (Platform.isIOS) {
      await player.setAudioContext(AudioContext(iOS: AudioContextIOS()));
    }
    final Directory directory = await getTemporaryDirectory();
    final File file = File(
      '${directory.path}/hausa_audio_${utteranceCount++}.wav',
    );
    await file.writeAsBytes(wav, flush: true);
    final Future<void> completed = player.onPlayerComplete.first;
    try {
      await player.play(DeviceFileSource(file.path));
      await completed;
    } finally {
      await discard(previous);
      previous = file;
    }
  };
}

final wavPlayerProvider = Provider<WavPlayer>((ref) {
  return _createWavPlayer(ref);
});

final recordingCuePlayerProvider = Provider<WavPlayer>((ref) {
  return _createWavPlayer(ref, preserveRecordingFocus: true);
});

/// Une instance Riverpod persistante : le modèle n'est jamais rechargé entre
/// deux calculs tant que le ProviderScope de l'application reste vivant.
final hausaSpeakerProvider = Provider<HausaSpeaker?>((ref) {
  return HausaSpeaker(
    synthesizer: ref.watch(hausaTtsEngineProvider),
    play: ref.watch(wavPlayerProvider),
  );
});
