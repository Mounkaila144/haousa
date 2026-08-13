import 'dart:async';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

class AudioRecordingProfile {
  const AudioRecordingProfile({required this.name, required this.sampleRate});

  final String name;
  final int sampleRate;

  static const asr = AudioRecordingProfile(name: 'ASR', sampleRate: 16000);
  static const tts = AudioRecordingProfile(name: 'TTS', sampleRate: 24000);

  RecordConfig get recordConfig => RecordConfig(
    encoder: AudioEncoder.wav,
    sampleRate: sampleRate,
    numChannels: 1,
    autoGain: false,
    echoCancel: false,
    noiseSuppress: false,
  );
}

class AudioCaptureService {
  AudioCaptureService({
    this.profile = AudioRecordingProfile.tts,
    AudioRecorder? recorder,
  }) : _recorder = recorder ?? AudioRecorder();

  final AudioRecordingProfile profile;
  final AudioRecorder _recorder;
  final StreamController<Amplitude> _amplitudeController =
      StreamController<Amplitude>.broadcast();
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  String? _temporaryPath;
  bool _recording = false;

  RecordConfig get recordingConfig => profile.recordConfig;

  Stream<Amplitude> onAmplitudeChanged(Duration interval) {
    // record 5.x expose un flux à abonnement unique. RecordingScreen peut être
    // ouvert et fermé plusieurs fois : on garde donc un seul abonnement natif
    // pendant toute la vie du service et on redistribue ses valeurs.
    _amplitudeSubscription ??= _recorder
        .onAmplitudeChanged(interval)
        .listen(
          _amplitudeController.add,
          onError: _amplitudeController.addError,
        );
    return _amplitudeController.stream;
  }

  Future<String> start() async {
    final status = await Permission.microphone.request();
    if (!status.isGranted || !await _recorder.hasPermission()) {
      throw const MicrophonePermissionException();
    }
    if (_recording) {
      await cancel();
    }
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}/prise_${DateTime.now().microsecondsSinceEpoch}.wav';
    _temporaryPath = path;
    await _recorder.start(profile.recordConfig, path: path);
    _recording = true;
    return path;
  }

  Future<String?> stop() async {
    if (!_recording) {
      return _temporaryPath;
    }
    final pluginPath = await _recorder.stop();
    _recording = false;
    _temporaryPath = pluginPath ?? _temporaryPath;
    return _temporaryPath;
  }

  Future<void> cancel() async {
    final path = _temporaryPath;
    if (_recording) {
      await _recorder.cancel();
    }
    _recording = false;
    _temporaryPath = null;
    if (path != null) {
      final file = File(path);
      if (await file.exists()) {
        await file.delete();
      }
    }
  }

  Future<void> dispose() async {
    await cancel();
    await _amplitudeSubscription?.cancel();
    await _amplitudeController.close();
    await _recorder.dispose();
  }
}

class MicrophonePermissionException implements Exception {
  const MicrophonePermissionException();
}
