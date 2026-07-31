import 'package:flutter/services.dart';
import 'package:hausa_mobile/speech/wav.dart';

/// Retourne un petit WAV PCM valide quel que soit le segment demandé.
class FakeVoiceBundle extends CachingAssetBundle {
  FakeVoiceBundle()
    : _wav = ByteData.sublistView(wavFromPcm(Uint8List.fromList(<int>[0, 0])));

  final ByteData _wav;

  @override
  Future<ByteData> load(String key) async => _wav;
}
