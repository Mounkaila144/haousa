import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

const String _thousandNamingFileName = 'thousand-naming';

/// Appellation du millier retenue par l'utilisateur.
///
/// Certains locuteurs disent `jika`, d'autres `dubu` — c'est régional, et les
/// deux valent exactement 1 000 F CFA. Ce réglage ne change **que** ce que
/// l'application dit et écrit : les deux formes restent comprises à l'écoute
/// quelle que soit sa valeur, sans quoi un mauvais réglage rendrait
/// l'application sourde à son propre utilisateur.
enum ThousandNaming {
  jika('jika', 'Jika', 'Niger'),
  dubu('dubu', 'Dubu', 'Nigeria');

  const ThousandNaming(this.wireValue, this.label, this.countryLabel);

  /// Valeur envoyée à l'API — le serveur produit la forme correspondante.
  final String wireValue;

  /// Libellé affiché dans les paramètres.
  final String label;

  /// Pays où cette appellation est employée. Le choix se présente à
  /// l'utilisateur sous forme de drapeau : c'est le seul repère utilisable
  /// par quelqu'un qui ne lit pas. Il désigne **la même** préférence — pas un
  /// second réglage, sans quoi les deux pourraient diverger.
  final String countryLabel;

  static ThousandNaming fromWire(String? value) {
    return ThousandNaming.values.firstWhere(
      (ThousandNaming naming) => naming.wireValue == value,
      orElse: () => defaultThousandNaming,
    );
  }
}

/// `jika` par défaut : c'est la forme du hausa du Niger, cible de l'application.
const ThousandNaming defaultThousandNaming = ThousandNaming.jika;

Future<File> _settingFile() async {
  final Directory supportDirectory = await getApplicationSupportDirectory();
  return File(
    '${supportDirectory.path}${Platform.pathSeparator}$_thousandNamingFileName',
  );
}

Future<ThousandNaming> loadThousandNaming() async {
  try {
    final File file = await _settingFile();
    if (!await file.exists()) {
      return defaultThousandNaming;
    }
    return ThousandNaming.fromWire((await file.readAsString()).trim());
  } on FileSystemException {
    // Un réglage illisible ne doit pas empêcher de calculer : on retombe sur
    // la valeur par défaut plutôt que d'échouer au démarrage.
    return defaultThousandNaming;
  }
}

Future<void> saveThousandNaming(ThousandNaming naming) async {
  final File file = await _settingFile();
  await file.writeAsString(naming.wireValue, flush: true);
}

/// Réglage courant. Surchargeable en test via `overrideWith`.
class ThousandNamingController extends Notifier<ThousandNaming> {
  @override
  ThousandNaming build() {
    unawaitedLoad();
    return defaultThousandNaming;
  }

  void unawaitedLoad() {
    loadThousandNaming().then((ThousandNaming stored) {
      if (stored != state) {
        state = stored;
      }
    });
  }

  Future<void> select(ThousandNaming naming) async {
    if (naming == state) {
      return;
    }
    state = naming;
    await saveThousandNaming(naming);
  }
}

final NotifierProvider<ThousandNamingController, ThousandNaming>
thousandNamingProvider =
    NotifierProvider<ThousandNamingController, ThousandNaming>(
      ThousandNamingController.new,
    );
