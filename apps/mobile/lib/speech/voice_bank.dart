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

/// Enregistrement de la consigne, à **rejouer** plutôt qu'à synthétiser.
///
/// Ces trois phrases sont fixes, et elles ont été volontairement écartées du
/// corpus d'entraînement : le modèle ne les a jamais vues. Les lui donner
/// reviendrait à lui faire inventer des mots qu'il n'a pas appris. Il ne sert
/// qu'aux montants et aux opérations, qui sont combinatoires — c'est pour eux
/// seuls qu'une synthèse est nécessaire.
const Map<String, String> kPromptRecordings = <String, String>{
  kPromptConfirm: 'assets/voice/sys_confirm.wav',
  kPromptCannotAnswer: 'assets/voice/sys_cannot_answer.wav',
  kPromptRepeat: 'assets/voice/sys_repeat.wav',
  kPromptResult: 'assets/voice/sys_result.wav',
};

String recordingForPrompt(String key) {
  final String? chemin = kPromptRecordings[key];
  if (chemin == null) {
    throw ArgumentError.value(key, 'prompt', 'Consigne sans enregistrement');
  }
  return chemin;
}

/// Découpe l'énoncé en tronçons homogènes, dans l'ordre.
///
/// Une confirmation mêle les deux natures — « Shin wannan ne ? » suivi du
/// montant — et chacune doit emprunter sa propre voie : l'enregistrement pour
/// la consigne, la synthèse pour le montant.
List<VoiceChunk> splitUtterance(List<VoiceSegment> utterance) {
  final List<VoiceChunk> chunks = <VoiceChunk>[];
  final List<String> mots = <String>[];

  void viderMots() {
    if (mots.isEmpty) return;
    chunks.add(VoiceChunk.synthesized(mots.join(' ')));
    mots.clear();
  }

  for (final VoiceSegment segment in utterance) {
    if (segment.kind == VoiceSegmentKind.word) {
      mots.add(segment.key);
      continue;
    }
    viderMots();
    chunks.add(VoiceChunk.recorded(recordingForPrompt(segment.key)));
  }
  viderMots();
  return chunks;
}

/// Un tronçon d'énoncé : soit un enregistrement, soit du texte à synthétiser.
class VoiceChunk {
  const VoiceChunk.recorded(this.assetPath) : text = null;
  const VoiceChunk.synthesized(this.text) : assetPath = null;

  /// Chemin de l'enregistrement, `null` si le tronçon est à synthétiser.
  final String? assetPath;

  /// Texte hausa à synthétiser, `null` si le tronçon est un enregistrement.
  final String? text;

  bool get isRecording => assetPath != null;

  @override
  bool operator ==(Object other) =>
      other is VoiceChunk &&
      other.assetPath == assetPath &&
      other.text == text;

  @override
  int get hashCode => Object.hash(assetPath, text);

  @override
  String toString() => isRecording ? 'recorded:$assetPath' : 'synth:$text';
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
