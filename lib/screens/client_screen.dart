import 'package:flutter/material.dart';

import '../data/store.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class ClientScreen extends StatelessWidget {
  const ClientScreen({super.key, required this.clientId});

  final String clientId;

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final client = store.clientOf(clientId);
    if (client == null) {
      return const Scaffold(body: SizedBox.shrink());
    }
    final items = store.forClient(client.id);
    final calls = store.callsOf(client.id);
    final open = store.openFor(client.id);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(kPage, 8, kPage, 32),
          children: [
            Row(
              children: [
                RoundIconButton(
                  icon: Icons.arrow_back_rounded,
                  onTap: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(client.name, style: T.title),
            if (client.company != null) ...[
              const SizedBox(height: 6),
              Text(
                client.company!,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: C.mute,
                ),
              ),
            ],
            if (client.phone != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.phone_rounded, size: 16, color: C.mute),
                  const SizedBox(width: 6),
                  Text(
                    client.phone!,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: C.inkSoft,
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 18),
            Row(
              children: [
                _mini(open, 'Открыто', open > 0 && store.hasOverdue(client.id)),
                Container(
                  width: 1,
                  height: 32,
                  margin: const EdgeInsets.symmetric(horizontal: 18),
                  color: C.line,
                ),
                _mini(calls.length, 'Звонки', false),
              ],
            ),
            if (client.facts.isNotEmpty) ...[
              const SizedBox(height: 26),
              const SectionLabel('Что знаем'),
              Surface(child: FactList(facts: client.facts)),
            ],
            const SizedBox(height: 26),
            const SectionLabel('Обязательства'),
            if (items.isEmpty)
              const Text(
                'Пока нет',
                style: TextStyle(color: C.mute, fontWeight: FontWeight.w500),
              )
            else
              for (final c in items) ...[
                CommitmentTile(
                  commitment: c,
                  clientName: client.name,
                  showClient: false,
                  onToggle: () => store.toggle(c),
                  onOpen: () => openCall(context, c.callId),
                ),
                const SizedBox(height: 10),
              ],
            if (calls.isNotEmpty) ...[
              const SizedBox(height: 16),
              const SectionLabel('Звонки'),
              for (final call in calls) ...[
                CallCard(call: call, onTap: () => openCall(context, call.id)),
                const SizedBox(height: 10),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _mini(int value, String label, bool alert) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$value',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w800,
            height: 1,
            color: alert ? C.red : C.ink,
          ),
        ),
        const SizedBox(height: 4),
        Text(label, style: T.label),
      ],
    );
  }
}
