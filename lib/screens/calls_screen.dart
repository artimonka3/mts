import 'package:flutter/material.dart';

import '../data/store.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class CallsScreen extends StatefulWidget {
  const CallsScreen({super.key});

  @override
  State<CallsScreen> createState() => _CallsScreenState();
}

class _CallsScreenState extends State<CallsScreen> {
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
    final calls = store.callsSorted.where((call) {
      if (needle.isEmpty) return true;
      final client = store.clientOf(call.clientId);
      final hay = '${client?.name} ${client?.company} ${call.summary}'
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
              const Text('Звонки', style: T.title),
              const SizedBox(height: 6),
              Text(
                '${store.calls.length} в истории',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: C.mute,
                ),
              ),
              const SizedBox(height: 16),
              SearchBox(
                controller: _query,
                hint: 'Имя, компания или суть',
                onChanged: (v) => setState(() => q = v),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: calls.isEmpty
              ? const Center(
                  child: Text(
                    'Таких звонков нет',
                    style: TextStyle(
                      color: C.mute,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(kPage, 8, kPage, 28),
                  itemCount: calls.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (context, i) => CallCard(
                    call: calls[i],
                    onTap: () => openCall(context, calls[i].id),
                  ),
                ),
        ),
      ],
    );
  }
}
