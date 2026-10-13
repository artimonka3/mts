import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/store.dart';
import '../screens/calls_screen.dart';
import '../screens/capture_screen.dart';
import '../screens/clients_screen.dart';
import '../screens/today_screen.dart';
import '../theme.dart';

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int index = 0;

  Future<void> _openCapture() async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        fullscreenDialog: true,
        builder: (_) => const CaptureScreen(),
      ),
    );
    if (!mounted || saved != true) return;
    setState(() => index = 0);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Договорённости в карточке клиента'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final overdue = Store.of(context).overdueCount;
    return Scaffold(
      backgroundColor: C.paper,
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: index,
          children: [
            TodayScreen(
              key: const Key('today'),
              onAllCalls: () => setState(() => index = 1),
            ),
            const CallsScreen(),
            const ClientsScreen(),
          ],
        ),
      ),
      bottomNavigationBar: DecoratedBox(
        decoration: const BoxDecoration(
          color: C.card,
          boxShadow: [
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 12,
              offset: Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 64,
            child: Row(
              children: [
                _Tab(
                  itemKey: const Key('tab-today'),
                  icon: Icons.home_rounded,
                  label: 'Сегодня',
                  selected: index == 0,
                  alert: overdue > 0,
                  onTap: () => setState(() => index = 0),
                ),
                _Tab(
                  itemKey: const Key('tab-calls'),
                  icon: Icons.phone_in_talk_rounded,
                  label: 'Звонки',
                  selected: index == 1,
                  onTap: () => setState(() => index = 1),
                ),
                _Tab(
                  itemKey: const Key('tab-clients'),
                  icon: Icons.people_alt_rounded,
                  label: 'Клиенты',
                  selected: index == 2,
                  onTap: () => setState(() => index = 2),
                ),
                Padding(
                  padding: const EdgeInsets.only(right: 14, left: 4),
                  child: Semantics(
                    button: true,
                    label: 'Записать разговор',
                    child: GestureDetector(
                      key: const Key('record'),
                      onTap: _openCapture,
                      child: Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: C.red,
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x33E30613),
                              blurRadius: 10,
                              offset: Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.mic_rounded,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
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
    this.alert = false,
    this.itemKey,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  final bool alert;
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
            SizedBox(
              width: 28,
              height: 24,
              child: Stack(
                clipBehavior: Clip.none,
                alignment: Alignment.center,
                children: [
                  Icon(icon, size: 24, color: color),
                  if (alert)
                    Positioned(
                      right: -2,
                      top: -2,
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: C.red,
                          shape: BoxShape.circle,
                          border: Border.all(color: C.card, width: 1.5),
                        ),
                      ),
                    ),
                ],
              ),
            ),
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
