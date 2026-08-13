/// Construction textuelle des énoncés envoyés au TTS hausa local.
library;

import 'package:hausa_mobile/l10n/hausa_messages.dart';

enum VoiceSegmentKind { word, prompt }

const String kPromptConfirm = 'confirm';
const String kPromptCannotAnswer = 'cannot_answer';
const String kPromptResult = 'result';
const String kPromptRepeat = 'repeat';

class VoiceSegment {
  const VoiceSegment.word(this.key) : kind = VoiceSegmentKind.word;
  const VoiceSegment.prompt(this.key) : kind = VoiceSegmentKind.prompt;

  final VoiceSegmentKind kind;
  final String key;

  @override
  bool operator ==(Object other) =>
      other is VoiceSegment && other.kind == kind && other.key == key;

  @override
  int get hashCode => Object.hash(kind, key);

  @override
  String toString() => '${kind.name}:$key';
}

List<VoiceSegment> utteranceFromHausa(String hausaText) {
  return hausaText
      .split(RegExp(r'\s+'))
      .where((String word) => word.isNotEmpty)
      .map(VoiceSegment.word)
      .toList(growable: false);
}

/// Le TTS n'est pas limité à une banque : toute forme parlée hausa non vide
/// peut être synthétisée, sinon la forme canonique du serveur est conservée.
List<VoiceSegment> preferredUtterance(String canonicalText, String spokenText) {
  return utteranceFromHausa(
    spokenText.trim().isNotEmpty ? spokenText : canonicalText,
  );
}

List<VoiceSegment> confirmationUtterance(List<VoiceSegment> inner) {
  return <VoiceSegment>[const VoiceSegment.prompt(kPromptConfirm), ...inner];
}

List<VoiceSegment> answerUtterance(
  List<VoiceSegment> operation,
  List<VoiceSegment> result,
) {
  return <VoiceSegment>[
    ...operation,
    const VoiceSegment.prompt(kPromptResult),
    ...result,
  ];
}

List<VoiceSegment> refusalUtterance() {
  return const <VoiceSegment>[VoiceSegment.prompt(kPromptCannotAnswer)];
}

List<VoiceSegment> repeatUtterance() {
  return const <VoiceSegment>[VoiceSegment.prompt(kPromptRepeat)];
}

String utteranceToHausaText(List<VoiceSegment> utterance) {
  const Map<String, String> prompts = <String, String>{
    kPromptConfirm: HausaMessages.ttsConfirm,
    kPromptCannotAnswer: HausaMessages.ttsCannotAnswer,
    kPromptResult: HausaMessages.ttsResult,
    kPromptRepeat: HausaMessages.ttsRepeat,
  };
  final List<String> parts = <String>[];
  for (final VoiceSegment segment in utterance) {
    if (segment.kind == VoiceSegmentKind.word) {
      parts.add(segment.key);
      continue;
    }
    final String? prompt = prompts[segment.key];
    if (prompt == null) {
      throw ArgumentError.value(
        segment.key,
        'utterance',
        'Consigne TTS inconnue',
      );
    }
    parts.add(prompt);
  }
  return parts.join(' ').trim();
}
