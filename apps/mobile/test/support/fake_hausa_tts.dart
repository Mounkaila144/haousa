import 'dart:typed_data';

import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/hausa_tts_engine.dart';
import 'package:hausa_mobile/speech/wav.dart';

class FakeHausaTtsSynthesizer implements HausaTtsSynthesizer {
  FakeHausaTtsSynthesizer({this.failure});

  final Object? failure;
  final List<String> texts = <String>[];
  bool disposed = false;

  @override
  Future<Uint8List> synthesizeWav(String hausaText) async {
    texts.add(hausaText);
    if (failure != null) throw failure!;
    return wavFromPcm(Uint8List(320));
  }

  @override
  Future<void> dispose() async => disposed = true;
}

HausaSpeaker fakeHausaSpeaker({
  required List<Uint8List> played,
  List<String>? synthesized,
  Object? failure,
}) {
  final FakeHausaTtsSynthesizer synthesizer = FakeHausaTtsSynthesizer(
    failure: failure,
  );
  if (synthesized != null) {
    // Keep the caller's list in sync without exposing mutable implementation
    // details from production code.
    return HausaSpeaker(
      synthesizer: _RecordingSynthesizer(synthesizer, synthesized),
      play: (Uint8List wav) async => played.add(wav),
    );
  }
  return HausaSpeaker(
    synthesizer: synthesizer,
    play: (Uint8List wav) async => played.add(wav),
  );
}

class _RecordingSynthesizer implements HausaTtsSynthesizer {
  _RecordingSynthesizer(this.delegate, this.output);

  final FakeHausaTtsSynthesizer delegate;
  final List<String> output;

  @override
  Future<Uint8List> synthesizeWav(String hausaText) async {
    final Uint8List wav = await delegate.synthesizeWav(hausaText);
    output.add(hausaText);
    return wav;
  }

  @override
  Future<void> dispose() => delegate.dispose();
}
