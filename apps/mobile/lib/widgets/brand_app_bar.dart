import 'package:flutter/material.dart';
import 'package:hausa_mobile/theme/brand.dart';

/// Bandeau de marque, identique et toujours visible sur tous les écrans.
class BrandAppBar extends StatelessWidget implements PreferredSizeWidget {
  const BrandAppBar({
    super.key,
    required this.title,
    this.automaticallyImplyLeading = true,
    this.actions,
  });

  final String title;
  final bool automaticallyImplyLeading;
  final List<Widget>? actions;

  @override
  Size get preferredSize => const Size.fromHeight(128);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      automaticallyImplyLeading: automaticallyImplyLeading,
      toolbarHeight: preferredSize.height,
      titleSpacing: 12,
      backgroundColor: BrandColors.navyDeep,
      surfaceTintColor: Colors.transparent,
      elevation: 8,
      shadowColor: BrandColors.navy.withValues(alpha: 0.35),
      flexibleSpace: const _BrandHeaderBackground(),
      title: Semantics(
        label: title == 'Calculatrice Hausa'
            ? 'Calculatrice Hausa'
            : 'Calculatrice Hausa, $title',
        image: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: Colors.white.withValues(alpha: 0.28)),
                boxShadow: <BoxShadow>[
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.24),
                    blurRadius: 14,
                    offset: const Offset(0, 5),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(13),
                child: Image.asset(
                  'assets/brand/logo.webp',
                  key: const Key('brand-logo'),
                  width: 224,
                  height: 82,
                  fit: BoxFit.contain,
                ),
              ),
            ),
            const SizedBox(height: 5),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Container(
                  width: 18,
                  height: 3,
                  decoration: BoxDecoration(
                    color: BrandColors.red,
                    borderRadius: BorderRadius.circular(99),
                  ),
                ),
                const SizedBox(width: 7),
                Flexible(
                  child: Text(
                    title == 'Calculatrice Hausa' ? 'Assistant vocal' : title,
                    key: const Key('brand-page-title'),
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.25,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      actions: actions,
    );
  }
}

class _BrandHeaderBackground extends StatelessWidget {
  const _BrandHeaderBackground();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: brandGradient),
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          Positioned(
            right: -54,
            top: -68,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: BrandColors.blueLight.withValues(alpha: 0.12),
              ),
              child: const SizedBox.square(dimension: 170),
            ),
          ),
          Positioned(
            right: 72,
            bottom: -72,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: BrandColors.red.withValues(alpha: 0.12),
              ),
              child: const SizedBox.square(dimension: 128),
            ),
          ),
          const Align(
            alignment: Alignment.bottomCenter,
            child: SizedBox(
              width: double.infinity,
              height: 2,
              child: ColoredBox(color: BrandColors.blueLight),
            ),
          ),
        ],
      ),
    );
  }
}
