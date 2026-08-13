import 'package:flutter/services.dart';

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

/// Fournit les enregistrements de consignes sans toucher aux assets réels.
///
/// Les tests vérifient l'**aiguillage** — quelle voie emprunte chaque tronçon —
/// pas le contenu audio. Passer par `rootBundle` les ferait dépendre de la
/// présence des WAV, et échouer pour une raison sans rapport avec ce qu'ils
/// contrôlent.
class FakePromptBundle extends CachingAssetBundle {
  final List<String> charges = <String>[];

  @override
  Future<ByteData> load(String key) async {
    charges.add(key);
    return ByteData.view(wavFromPcm(Uint8List(320)).buffer);
  }
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
      bundle: FakePromptBundle(),
      play: (Uint8List wav) async => played.add(wav),
    );
  }
  return HausaSpeaker(
    synthesizer: synthesizer,
    bundle: FakePromptBundle(),
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
