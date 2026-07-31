import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/app.dart';
import 'package:hausa_mobile/config/anon_id.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final String anonId = await loadOrCreateAnonId();
  runApp(
    ProviderScope(
      overrides: <Override>[anonIdProvider.overrideWithValue(anonId)],
      child: const HausaApp(),
    ),
  );
}
