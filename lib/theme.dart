import 'package:flutter/material.dart';

const double kPage = 16;
const double kRadius = 20;

abstract final class C {
  /// Фон как в «Мой МТС».
  static const paper = Color(0xFFF2F3F7);
  static const card = Color(0xFFFFFFFF);
  static const ink = Color(0xFF1A1A1A);
  static const inkSoft = Color(0xFF3C3C43);
  static const mute = Color(0xFF8E8E93);
  static const line = Color(0xFFE5E5EA);
  static const chip = Color(0xFFEEF0F4);
  static const secondaryBtn = Color(0xFFE8E8ED);

  /// Фирменный красный МТС.
  static const red = Color(0xFFE30613);
  static const redSoft = Color(0xFFFFEBEE);
  static const redSoftBorder = Color(0x33E30613);

  static const moss = Color(0xFF34C759);
  static const mossBg = Color(0xFFE8F8ED);
  static const sand = Color(0xFFFFF4E0);
  static const clay = Color(0xFFB86E00);
  static const blush = Color(0xFFFFEBEE);

  static const shadow = Color(0x14000000);

  static const tones = <Color>[
    Color(0xFFE30613),
    Color(0xFF1A1A1A),
    Color(0xFF5856D6),
    Color(0xFF007AFF),
    Color(0xFF34C759),
  ];

  static List<BoxShadow> get cardShadow => const [
    BoxShadow(color: Color(0x0F000000), blurRadius: 16, offset: Offset(0, 4)),
    BoxShadow(color: Color(0x08000000), blurRadius: 4, offset: Offset(0, 1)),
  ];
}

abstract final class T {
  static const display = TextStyle(
    fontSize: 40,
    fontWeight: FontWeight.w700,
    letterSpacing: -1.2,
    height: 1,
    color: C.ink,
  );

  static const title = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.6,
    height: 1.15,
    color: C.ink,
  );

  static const body = TextStyle(
    fontSize: 15,
    height: 1.35,
    fontWeight: FontWeight.w400,
    color: C.ink,
  );

  static const label = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    color: C.mute,
  );

  static const section = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w700,
    color: C.ink,
  );
}
