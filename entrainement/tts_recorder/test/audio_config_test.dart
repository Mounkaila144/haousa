import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:record/record.dart';
import 'package:tts_recorder/audio_service.dart';

void main() {
  test('les profils TTS 24 kHz et ASR 16 kHz restent distincts', () {
    final tts = AudioRecordingProfile.tts.recordConfig;
    final asr = AudioRecordingProfile.asr.recordConfig;

    expect(tts.sampleRate, 24000);
    expect(asr.sampleRate, 16000);
    expect(tts.numChannels, 1);
    expect(tts.autoGain, isFalse);
    expect(tts.echoCancel, isFalse);
    expect(tts.noiseSuppress, isFalse);
  });

  test('le VU-mètre peut être écouté après plusieurs ouvertures', () async {
    final recorder = _FakeAudioRecorder();
    final service = AudioCaptureService(recorder: recorder);
    final firstValues = <double>[];
    final secondValues = <double>[];

    final first = service
        .onAmplitudeChanged(const Duration(milliseconds: 80))
        .listen((amplitude) => firstValues.add(amplitude.current));
    recorder.add(-12);
    await Future<void>.delayed(Duration.zero);
    await first.cancel();

    final second = service
        .onAmplitudeChanged(const Duration(milliseconds: 80))
        .listen((amplitude) => secondValues.add(amplitude.current));
    recorder.add(-9);
    await Future<void>.delayed(Duration.zero);
    await second.cancel();

    expect(firstValues, <double>[-12]);
    expect(secondValues, <double>[-9]);
    await service.dispose();
  });
}

class _FakeAudioRecorder extends AudioRecorder {
  final StreamController<Amplitude> _controller = StreamController<Amplitude>();

  void add(double value) {
    _controller.add(Amplitude(current: value, max: value));
  }

  @override
  Stream<Amplitude> onAmplitudeChanged(Duration interval) => _controller.stream;

  @override
  Future<void> dispose() => _controller.close();
}
