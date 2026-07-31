import 'package:flutter/material.dart';
import 'package:hausa_mobile/navigation/app_routes.dart';
import 'package:hausa_mobile/theme/brand.dart';

class HausaApp extends StatelessWidget {
  const HausaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Calculatrice Hausa',
      debugShowCheckedModeBanner: false,
      theme: buildBrandTheme(),
      initialRoute: AppRoutes.home,
      routes: AppRoutes.routes,
      onGenerateRoute: AppRoutes.onGenerateRoute,
    );
  }
}
