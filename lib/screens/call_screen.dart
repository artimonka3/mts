import 'package:flutter/material.dart';

import '../data/store.dart';
import '../format.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class CallScreen extends StatelessWidget {
  const CallScreen({super.key, required this.callId});

  final String callId;

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final match = store.calls.where((c) => c.id == callId);
    if (match.isEmpty) {
      return const Scaffold(body: SizedBox.shrink());
    }
    final record = match.first;
    final client = store.clientOf(record.clientId);
    final items = store.commitmentsOfCall(record.id);

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
            const SizedBox(height: 16),
            if (client != null)
              Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: () => openClient(context, client.id),
                  borderRadius: BorderRadius.circular(16),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Monogram(
                          name: client.name,
                          tone: client.tone,
                          size: 52,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                client.name,
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.4,
                                ),
                              ),
                              if (client.company != null)
                                Text(
                                  client.company!,
                                  style: const TextStyle(
                                    color: C.mute,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right_rounded, color: C.mute),
                      ],
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 8),
            Text(
              '${callWhen(record.createdAt)} · ${durationLabel(record.durationSec)}',
              style: const TextStyle(
                color: C.mute,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 18),
            SummaryCard(text: record.summary),
            const SizedBox(height: 26),
            SectionLabel(
              items.isEmpty
                  ? 'Обязательства'
                  : 'Обязательства · ${items.length}',
            ),
            if (items.isEmpty)
              const Text(
                'В этом разговоре договорённостей нет',
                style: TextStyle(color: C.mute, fontWeight: FontWeight.w500),
              )
            else
              for (final c in items) ...[
                CommitmentTile(
                  commitment: c,
                  clientName: client?.name ?? '',
                  showClient: false,
                  showQuote: true,
                  onToggle: () => store.toggle(c),
                ),
                const SizedBox(height: 10),
              ],
            const SizedBox(height: 16),
            const SectionLabel('Расшифровка'),
            TranscriptView(
              turns: record.turns,
              theirName: firstName(client?.name ?? 'Клиент'),
            ),
          ],
        ),
      ),
    );
  }
}
