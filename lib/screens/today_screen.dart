import 'package:flutter/material.dart';

import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

enum _Filter { all, overdue, today, ours, client }

class TodayScreen extends StatefulWidget {
  const TodayScreen({super.key, required this.onAllCalls});

  final VoidCallback onAllCalls;

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  _Filter filter = _Filter.all;
  bool showDone = false;

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final visible = store.openCommitments.where(_match).toList();
    final done = store.doneCommitments;
    final recent = store.callsSorted.take(3).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(kPage, 8, kPage, 28),
      children: [
        Row(
          children: [
            Container(
              width: 36,
              height: 36,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: C.red,
                shape: BoxShape.circle,
              ),
              child: const Text(
                'Д',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: 16,
                ),
              ),
            ),
            const SizedBox(width: 10),
            const Expanded(child: Wordmark(size: 20)),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          longDate(DateTime.now()),
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: C.mute,
          ),
        ),
        const SizedBox(height: 16),
        _Hero(
          store: store,
          onOverdue: () => setState(() => filter = _Filter.overdue),
        ),
        const SizedBox(height: 12),
        _StatsCard(store: store),
        const SizedBox(height: 16),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final item in _Filter.values) ...[
                SelectChip(
                  label: _label(item, store),
                  selected: filter == item,
                  onTap: () => setState(() => filter = item),
                ),
                const SizedBox(width: 8),
              ],
            ],
          ),
        ),
        const SizedBox(height: 20),
        const SectionLabel('Сделать'),
        if (visible.isEmpty)
          Surface(
            child: Text(
              'Нет таких договорённостей',
              style: TextStyle(color: C.mute, fontWeight: FontWeight.w500),
            ),
          )
        else
          for (final c in visible) ...[
            CommitmentTile(
              commitment: c,
              clientName: store.clientOf(c.clientId)?.name ?? '',
              onToggle: () => store.toggle(c),
              onOpen: () => openCall(context, c.callId),
            ),
            const SizedBox(height: 10),
          ],
        if (filter == _Filter.all && done.isNotEmpty) ...[
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () => setState(() => showDone = !showDone),
            behavior: HitTestBehavior.opaque,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  Text('Закрыто · ${done.length}', style: T.section),
                  const SizedBox(width: 4),
                  Icon(
                    showDone
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                    size: 20,
                    color: C.mute,
                  ),
                ],
              ),
            ),
          ),
          if (showDone)
            for (final c in done) ...[
              CommitmentTile(
                commitment: c,
                clientName: store.clientOf(c.clientId)?.name ?? '',
                onToggle: () => store.toggle(c),
                onOpen: () => openCall(context, c.callId),
              ),
              const SizedBox(height: 10),
            ],
        ],
        if (filter == _Filter.all && recent.isNotEmpty) ...[
          const SizedBox(height: 12),
          SectionLabel(
            'Недавние звонки',
            trailing: GestureDetector(
              onTap: widget.onAllCalls,
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Все',
                    style: TextStyle(
                      color: C.red,
                      fontWeight: FontWeight.w600,
                      fontSize: 15,
                    ),
                  ),
                  Icon(Icons.chevron_right_rounded, color: C.red, size: 20),
                ],
              ),
            ),
          ),
          for (final call in recent) ...[
            CallCard(call: call, onTap: () => openCall(context, call.id)),
            const SizedBox(height: 10),
          ],
        ],
      ],
    );
  }

  bool _match(Commitment c) {
    return switch (filter) {
      _Filter.all => true,
      _Filter.overdue => c.isOverdue,
      _Filter.today => c.dueDate != null && dayDiff(c.dueDate!) == 0,
      _Filter.ours => c.owner == CommitmentOwner.us,
      _Filter.client => c.owner == CommitmentOwner.client,
    };
  }

  String _label(_Filter item, Store store) {
    return switch (item) {
      _Filter.all => 'Все ${store.openCommitments.length}',
      _Filter.overdue => 'Просрочено ${store.overdueCount}',
      _Filter.today => 'Сегодня ${store.dueTodayCount}',
      _Filter.ours => 'На нас',
      _Filter.client => 'Клиент',
    };
  }
}

/// Карточка как «Баланс» в приложении МТС.
class _Hero extends StatelessWidget {
  const _Hero({required this.store, required this.onOverdue});

  final Store store;
  final VoidCallback onOverdue;

  @override
  Widget build(BuildContext context) {
    final open = store.openCommitments.length;
    return Surface(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Открытые договорённости',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: C.mute,
            ),
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('$open', style: T.display),
              const SizedBox(width: 8),
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  open == 1
                      ? 'задача'
                      : (open >= 2 && open <= 4)
                      ? 'задачи'
                      : 'задач',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: C.inkSoft,
                  ),
                ),
              ),
            ],
          ),
          if (store.overdueCount > 0) ...[
            const SizedBox(height: 14),
            PrimaryButton(
              label: 'Разбрать просроченные · ${store.overdueCount}',
              onPressed: onOverdue,
            ),
          ],
        ],
      ),
    );
  }
}

/// Карточка как «Мои остатки».
class _StatsCard extends StatelessWidget {
  const _StatsCard({required this.store});

  final Store store;

  @override
  Widget build(BuildContext context) {
    return Surface(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      child: Column(
        children: [
          const Row(
            children: [
              Expanded(
                child: Text(
                  'Сводка',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: C.ink,
                  ),
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: C.mute),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _stat(
                  'Просрочено',
                  '${store.overdueCount}',
                  store.overdueCount > 0 ? C.red : C.ink,
                ),
              ),
              Container(width: 1, height: 36, color: C.line),
              Expanded(
                child: _stat(
                  'На сегодня',
                  '${store.dueTodayCount}',
                  store.dueTodayCount > 0 ? C.clay : C.ink,
                ),
              ),
              Container(width: 1, height: 36, color: C.line),
              Expanded(
                child: _stat('На клиенте', '${store.onClientCount}', C.ink),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color valueColor) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: C.mute,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: valueColor,
            ),
          ),
        ],
      ),
    );
  }
}
