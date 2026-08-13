import 'package:flutter_riverpod/flutter_riverpod.dart';

class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    this.connectTimeout = const Duration(seconds: 10),
    this.sendTimeout = const Duration(seconds: 30),
    this.receiveTimeout = const Duration(seconds: 30),
  });

  factory AppConfig.fromEnvironment() {
    const String configuredApiBaseUrl = String.fromEnvironment('API_BASE_URL');
    // Le vhost `ia-ptrniger.duckdns.org` héberge encore l'ancien service Zarma sous
    // `/api/v1` ; l'API hausa est servie sous le préfixe `/hausa` (cf.
    // `infrastructure/nginx/hausa.conf`). Omettre le préfixe fait tomber
    // l'application sur une API qui répond `zarma_text` et une grammaire 1.5.0.
    const String defaultApiBaseUrl =
        'https://ia-ptrniger.duckdns.org/hausa/api/v1';

    return AppConfig(
      apiBaseUrl: configuredApiBaseUrl.isEmpty
          ? defaultApiBaseUrl
          : configuredApiBaseUrl,
    );
  }

  static const int buildNumber = 2;

  final String apiBaseUrl;
  final Duration connectTimeout;
  final Duration sendTimeout;
  final Duration receiveTimeout;
}

final appConfigProvider = Provider<AppConfig>((ref) {
  return AppConfig.fromEnvironment();
});
