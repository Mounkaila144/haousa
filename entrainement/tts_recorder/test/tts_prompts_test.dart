import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tts_recorder/csv_codec.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('le vocabulaire embarqué porte le corpus complet à enregistrer', () async {
    // Contrairement au studio zarma dont celui-ci est forké, aucune prise n'a
    // encore été faite : l'asset porte donc le corpus ENTIER, généré depuis
    // `hausa_numbers` par `scripts/generate_tts_prompts.py`.
    final source = await rootBundle.loadString('assets/tts_prompts.csv');
    final prompts = parsePromptsCsv(source);

    expect(prompts.length, greaterThan(300));
    expect(prompts.map((prompt) => prompt.id).toSet(), hasLength(prompts.length));
    // Le `|` sépare les champs du métafichier Piper : interdit partout.
    expect(prompts.any((prompt) => prompt.hausaText.contains('|')), isFalse);
  });

  test('chaque identifiant reste un nom de fichier lisible', () async {
    // L'identifiant devient le nom du WAV. Les opérateurs sont donc nommés
    // (`op_mul_…`) et non écrits `*` ou `/`, qui obligeraient à échapper et
    // rendraient les prises pénibles à retrouver à la main sur le téléphone.
    final source = await rootBundle.loadString('assets/tts_prompts.csv');
    final prompts = parsePromptsCsv(source);

    for (final prompt in prompts) {
      expect(
        RegExp(r'^[A-Za-z0-9_]+$').hasMatch(prompt.id),
        isTrue,
        reason: 'identifiant à échapper : ${prompt.id}',
      );
      expect(fileNameForPrompt(prompt.id), '${prompt.id}.wav');
    }
  });

  test('les consignes système portent du hausa, pas leur traduction', () async {
    // Chez le studio zarma, `texte_*` des consignes système portait le FRANÇAIS
    // (aide-mémoire à l'écran) et il fallait les exclure de l'entraînement.
    // Ici l'application prononce réellement ces phrases : c'est le hausa qui
    // doit être enregistré, et `affichage` qui porte la traduction.
    final source = await rootBundle.loadString('assets/tts_prompts.csv');
    final prompts = parsePromptsCsv(source);
    final systeme =
        prompts.where((prompt) => prompt.id.startsWith('sys_')).toList();

    expect(systeme, hasLength(3));
    expect(
      systeme.map((prompt) => prompt.hausaText),
      containsAll(<String>['Shin wannan ne?']),
    );
  });

  test('les consignes système sont présentes et distinguables', () async {
    // Le préfixe n'est pas cosmétique : c'est lui qui permet de les exclure
    // d'un entraînement TTS en une ligne. Leur `texte_hausa` porte le FRANÇAIS
    // (aide-mémoire à l'écran, décision du 2026-08-07), donc les laisser dans
    // `piper_metadata` apprendrait au modèle une correspondance fausse.
    final source = await rootBundle.loadString('assets/tts_prompts.csv');
    final prompts = parsePromptsCsv(source);
    final systeme =
        prompts.where((prompt) => prompt.id.startsWith('sys_')).toList();

    expect(systeme, isNotEmpty);
    expect(systeme.map((prompt) => prompt.id).toSet(), hasLength(systeme.length));
    // Les trois consignes en sommeil ne sont pas à enregistrer : l'écran
    // qu'elles servaient a été supprimé par le mode images.
    expect(
      systeme.map((prompt) => prompt.id),
      isNot(contains('sys_heard_beneficiary_prefix')),
    );
  });

  test('échappe les divisions dans les noms et produit une ligne Piper', () {
    expect(fileNameForPrompt('tts_1/5'), 'tts_1%2F5.wav');
    expect(
      piperMetadataRow('tts_1%2F5.wav', 'afo kan ifaysor igou'),
      'tts_1%2F5.wav|afo kan ifaysor igou',
    );
    expect(
      () => piperMetadataRow('x.wav', 'texte|interdit'),
      throwsFormatException,
    );
  });
}
