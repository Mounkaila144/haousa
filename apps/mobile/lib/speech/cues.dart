/// Signaux sonores courts de début et de fin d'enregistrement.
library;

import 'dart:math' as math;
import 'dart:typed_data';

import 'package:hausa_mobile/speech/wav.dart';

const Duration kCueDuration = Duration(milliseconds: 110);
const double kCueStartHz = 1046.5;
const double kCueStopHz = 784.0;

Uint8List toneWav(double hertz, {Duration duree = kCueDuration}) {
  final int total = (kSampleRate * duree.inMilliseconds / 1000).round();
  final int fondu = (kSampleRate * 0.015).round();
  final Uint8List pcm = Uint8List(total * 2);
  final ByteData data = ByteData.sublistView(pcm);

  for (int index = 0; index < total; index++) {
    final double phase = 2 * math.pi * hertz * index / kSampleRate;
    final double enveloppe = math.min(
      1.0,
      math.min(index / fondu, (total - 1 - index) / fondu),
    );
    final int echantillon = (math.sin(phase) * enveloppe * 0.35 * 32767)
        .round();
    data.setInt16(index * 2, echantillon, Endian.little);
  }
  return wavFromPcm(pcm);
}

final Uint8List startCueWav = toneWav(kCueStartHz);
final Uint8List stopCueWav = toneWav(kCueStopHz);
