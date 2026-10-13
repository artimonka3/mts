import 'package:flutter/material.dart';
import 'package:flutter_contacts/flutter_contacts.dart';

import '../data/store.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class ClientsScreen extends StatefulWidget {
  const ClientsScreen({super.key});

  @override
  State<ClientsScreen> createState() => _ClientsScreenState();
}

String _peopleWord(int n) {
  final mod10 = n % 10;
  final mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'контактов';
  if (mod10 == 1) return 'контакт';
  if (mod10 >= 2 && mod10 <= 4) return 'контакта';
  return 'контактов';
}

class _ClientsScreenState extends State<ClientsScreen> {
  final _query = TextEditingController();
  String q = '';
  bool _importing = false;

  Future<void> _importFromPhone() async {
    if (_importing) return;
    setState(() => _importing = true);
    try {
      final status = await FlutterContacts.permissions.request(
        PermissionType.read,
      );
      if (!mounted) return;
      if (status != PermissionStatus.granted &&
          status != PermissionStatus.limited) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Разрешите доступ к контактам в настройках'),
          ),
        );
        return;
      }
      final book = await FlutterContacts.getAll(
        properties: {
          ContactProperty.name,
          ContactProperty.phone,
          ContactProperty.organization,
        },
      );
      if (!mounted) return;
      final people = <({String name, String? company, String phone})>[];
      for (final contact in book) {
        if (contact.phones.isEmpty) continue;
        final name = (contact.displayName ?? '').trim();
        final company = contact.organizations.isEmpty
            ? null
            : contact.organizations.first.name;
        for (final phone in contact.phones) {
          if (phone.number.trim().isEmpty) continue;
          people.add((
            name: name.isEmpty ? phone.number : name,
            company: company,
            phone: phone.number,
          ));
          break;
        }
      }
      final added = Store.of(context).importPeople(people);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            added == 0
                ? 'Новых контактов нет'
                : 'Перенесли $added ${_peopleWord(added)}',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _importing = false);
    }
  }

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
                'Свои и с телефона',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: C.mute,
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: OutlinedButton.icon(
                  onPressed: _importing ? null : _importFromPhone,
                  icon: const Icon(Icons.contact_phone_outlined),
                  label: Text(
                    _importing ? 'Читаю контакты…' : 'Перенести с телефона',
                  ),
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
                                const SizedBox(height: 2),
                                Text(
                                  'разговоров: ${store.callsOf(client.id).length}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: C.mute,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
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
