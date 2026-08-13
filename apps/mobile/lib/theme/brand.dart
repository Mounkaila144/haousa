/// Palette et thème de marque Calculatrice Hausa / PTR Niger.
///
/// Les teintes viennent du logo lui-même (`tool/build_brand_assets.py` les a
/// mesurées dessus) — l'application doit se reconnaître au premier coup d'œil
/// comme le produit du logo, pas comme un thème Material générique.
library;

import 'package:flutter/material.dart';

abstract final class BrandColors {
  /// Bleu nuit du logo — fonds d'AppBar, pied de page, texte sur fond clair.
  static const Color navy = Color(0xFF071A44);
  static const Color navyDeep = Color(0xFF040F2B);

  /// Bleu d'action — boutons et éléments interactifs (bon contraste au blanc).
  static const Color blue = Color(0xFF0A6CD6);
  static const Color blueLight = Color(0xFF00C8F8);

  /// Rouge du logo — alertes, refus, accents.
  static const Color red = Color(0xFFE00008);

  static const Color surface = Color(0xFFF4F7FC);
  static const Color surfaceBlue = Color(0xFFEAF2FF);
}

ThemeData buildBrandTheme() {
  const ColorScheme scheme = ColorScheme(
    brightness: Brightness.light,
    primary: BrandColors.blue,
    onPrimary: Colors.white,
    secondary: BrandColors.red,
    onSecondary: Colors.white,
    tertiary: BrandColors.blueLight,
    onTertiary: BrandColors.navy,
    error: BrandColors.red,
    onError: Colors.white,
    surface: Colors.white,
    onSurface: BrandColors.navy,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: BrandColors.surface,
    canvasColor: BrandColors.surface,
    dividerColor: BrandColors.navy.withValues(alpha: 0.10),
    textTheme: const TextTheme(
      displayLarge: TextStyle(
        color: BrandColors.navyDeep,
        fontWeight: FontWeight.w900,
        letterSpacing: -1.5,
      ),
      displayMedium: TextStyle(
        color: BrandColors.navyDeep,
        fontWeight: FontWeight.w800,
        letterSpacing: -1,
      ),
      headlineMedium: TextStyle(
        color: BrandColors.navy,
        fontWeight: FontWeight.w800,
      ),
      headlineSmall: TextStyle(
        color: BrandColors.navy,
        fontWeight: FontWeight.w800,
      ),
      titleLarge: TextStyle(
        color: BrandColors.navy,
        fontWeight: FontWeight.w800,
      ),
      titleMedium: TextStyle(
        color: BrandColors.navy,
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: TextStyle(color: BrandColors.navy, height: 1.45),
      bodyMedium: TextStyle(color: BrandColors.navy, height: 1.4),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: Colors.white,
        fontSize: 22,
        fontWeight: FontWeight.w700,
      ),
      iconTheme: IconThemeData(color: Colors.white),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: BrandColors.blue,
        foregroundColor: Colors.white,
        elevation: 5,
        shadowColor: BrandColors.blue.withValues(alpha: 0.32),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: BrandColors.navy,
        side: const BorderSide(color: BrandColors.blue, width: 2),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 17),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: BrandColors.blue,
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(color: BrandColors.blue.withValues(alpha: 0.12)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: BorderSide(color: BrandColors.blue.withValues(alpha: 0.16)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(18),
        borderSide: const BorderSide(color: BrandColors.blue, width: 2),
      ),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: BrandColors.blue,
      circularTrackColor: BrandColors.surfaceBlue,
      linearTrackColor: BrandColors.surfaceBlue,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      elevation: 16,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: BrandColors.navy,
      contentTextStyle: const TextStyle(color: Colors.white, fontSize: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    listTileTheme: ListTileThemeData(
      tileColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
    ),
  );
}

/// Dégradé signature de l'AppBar et du pied de page — même teintes partout.
const LinearGradient brandGradient = LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: <Color>[BrandColors.navyDeep, BrandColors.navy, BrandColors.blue],
);
