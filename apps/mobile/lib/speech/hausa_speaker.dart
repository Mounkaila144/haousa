/// Restitution vocale hausa locale par Piper/Sherpa-ONNX.
library;

import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
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
  HausaSpeaker({required this.synthesizer, required this.play});

  final HausaTtsSynthesizer synthesizer;
  final WavPlayer play;

  String? lastError;

  List<VoiceSegment> preferred(String canonicalText, String spokenText) =>
      preferredUtterance(canonicalText, spokenText);

  Future<SpeechOutcome> speak(List<VoiceSegment> utterance) async {
    if (utterance.isEmpty) return SpeechOutcome.incomplete;
    try {
      final String hausaText = utteranceToHausaText(utterance);
      final Uint8List wav = await synthesizer.synthesizeWav(hausaText);
      await play(wav);
      lastError = null;
      return SpeechOutcome.spoken;
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
