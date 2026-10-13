import 'package:flutter/material.dart';

import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../routes.dart';
import '../theme.dart';
import 'live_call_screen.dart';

/// Журнал как «Вызовы»: сюда попадают разобранные сотовые звонки.
class RecentsScreen extends StatelessWidget {
  const RecentsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final calls = store.callsSorted;

    return ColoredBox(
      color: Colors.white,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 24),
        children: [
          const SizedBox(
            height: 44,
            child: Center(
              child: Text(
                'Вызовы',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: C.ink,
                ),
              ),
            ),
          ),
          for (final call in calls)
            _Row(call: call, onTap: () => openCall(context, call.id)),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.call, required this.onTap});

  final CallRecord call;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final client = store.clientOf(call.clientId);
    final name = client?.name ?? 'Неизвестный';
    final missed = call.direction == CallDirection.missed;
    final incoming = call.direction != CallDirection.outgoing;
    final same = store.calls.where((c) => c.clientId == call.clientId).length;
    final line = client?.phone == null
        ? 'телефон'
        : (name.startsWith('+') ? client!.phone! : 'телефон');
    final subtitle = same > 1 ? '$line ($same)' : line;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: Row(
          children: [
            _Avatar(name: name),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                      color: missed ? const Color(0xFFFF3B30) : C.ink,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Icon(
                        incoming
                            ? Icons.call_received_rounded
                            : Icons.call_made_rounded,
                        size: 14,
                        color: C.mute,
                      ),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13,
                            color: C.mute,
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(
              recentsWhen(call.createdAt),
              style: const TextStyle(
                fontSize: 15,
                color: C.mute,
                fontWeight: FontWeight.w400,
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: () {
                final person = store.clientOf(call.clientId);
                if (person == null) return;
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => LiveCallScreen(clientId: person.id),
                  ),
                );
              },
              child: Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF007AFF),
                    width: 1.4,
                  ),
                ),
                child: const Icon(
                  Icons.phone_rounded,
                  size: 16,
                  color: Color(0xFF007AFF),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.name});

  final String name;

  @override
  Widget build(BuildContext context) {
    final letter = name.startsWith('+') ? null : initials(name);
    return Container(
      width: 44,
      height: 44,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF8FB7FF), Color(0xFF4C8DFF)],
        ),
      ),
      child: letter == null
          ? const Icon(Icons.person_rounded, color: Colors.white, size: 26)
          : Text(
              String.fromCharCode(letter.runes.first),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w600,
              ),
            ),
    );
  }
}
