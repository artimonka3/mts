import 'package:flutter/material.dart';

import '../data/store.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class ClientsScreen extends StatefulWidget {
  const ClientsScreen({super.key});

  @override
  State<ClientsScreen> createState() => _ClientsScreenState();
}

class _ClientsScreenState extends State<ClientsScreen> {
  final _query = TextEditingController();
  String q = '';

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final needle = q.trim().toLowerCase();
    final clients = store.clientsSorted.where((client) {
      if (needle.isEmpty) return true;
      final hay =
          '${client.name} ${client.company} ${client.phone} ${client.facts.join(' ')}'
              .toLowerCase();
      return hay.contains(needle);
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(kPage, 12, kPage, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Клиенты', style: T.title),
              const SizedBox(height: 6),
              const Text(
                'Карточки собираются из звонков',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: C.mute,
                ),
              ),
              const SizedBox(height: 16),
              SearchBox(
                controller: _query,
                hint: 'Имя или компания',
                onChanged: (v) => setState(() => q = v),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: clients.isEmpty
              ? const Center(
                  child: Text(
                    'Никого не нашли',
                    style: TextStyle(
                      color: C.mute,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(kPage, 8, kPage, 28),
                  itemCount: clients.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, i) {
                    final client = clients[i];
                    final open = store.openFor(client.id);
                    final overdue = store.hasOverdue(client.id);
                    return Surface(
                      onTap: () => openClient(context, client.id),
                      child: Row(
                        children: [
                          Monogram(
                            name: client.name,
                            tone: client.tone,
                            size: 52,
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  client.name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 16,
                                  ),
                                ),
                                if (client.company != null)
                                  Text(
                                    client.company!,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      fontSize: 13,
                                      color: C.mute,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                if (client.phone != null) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    client.phone!,
                                    style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: C.inkSoft,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Column(
                            children: [
                              Text(
                                '$open',
                                style: TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.w800,
                                  height: 1,
                                  color: open == 0
                                      ? C.mute
                                      : overdue
                                      ? C.red
                                      : C.ink,
                                ),
                              ),
                              const SizedBox(height: 4),
                              const Text('открыто', style: T.label),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
