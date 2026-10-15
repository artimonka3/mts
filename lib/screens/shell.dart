import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../screens/clients_screen.dart';
import '../screens/recents_screen.dart';
import '../screens/calendar_screen.dart';
import '../theme.dart';

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: index,
          children: [
            const RecentsScreen(key: Key('recents')),
            const ClientsScreen(),
            const CalendarScreen(key: Key('today')),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: const Color(0xF2FFFFFF),
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x22000000),
                  blurRadius: 18,
                  offset: Offset(0, 6),
                ),
              ],
            ),
            child: SizedBox(
              height: 62,
              child: Row(
                children: [
                  _Tab(
                    itemKey: const Key('tab-calls'),
                    icon: Icons.access_time_filled_rounded,
                    label: 'Вызовы',
                    selected: index == 0,
                    onTap: () => setState(() => index = 0),
                  ),
                  _Tab(
                    itemKey: const Key('tab-clients'),
                    icon: Icons.person_rounded,
                    label: 'Контакты',
                    selected: index == 1,
                    onTap: () => setState(() => index = 1),
                  ),
                  _Tab(
                    itemKey: const Key('tab-today'),
                    icon: Icons.calendar_month_rounded,
                    label: 'Задачи',
                    selected: index == 2,
                    onTap: () => setState(() => index = 2),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Tab extends StatelessWidget {
  const _Tab({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
    this.itemKey,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Key? itemKey;

  @override
  Widget build(BuildContext context) {
    final color = selected ? C.red : C.mute;
    return Expanded(
      child: GestureDetector(
        key: itemKey,
        behavior: HitTestBehavior.opaque,
        onTap: () {
          if (!selected) HapticFeedback.selectionClick();
          onTap();
        },
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 24, color: color),
            const SizedBox(height: 2),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
            const SizedBox(height: 3),
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: selected ? 4 : 0,
              height: selected ? 4 : 0,
              decoration: const BoxDecoration(
                color: C.red,
                shape: BoxShape.circle,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
