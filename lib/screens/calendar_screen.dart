import 'package:flutter/material.dart';

import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../routes.dart';
import '../theme.dart';
import '../widgets/common.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  late DateTime _month;
  late DateTime _selected;
  String? _movingId;

  @override
  void initState() {
    super.initState();
    final today = dateOnly(DateTime.now());
    _month = DateTime(today.year, today.month);
    _selected = today;
  }

  void _shiftMonth(int delta) {
    setState(() {
      _month = DateTime(_month.year, _month.month + delta);
    });
  }

  Future<void> _create(Store store) async {
    final text = TextEditingController();
    var owner = CommitmentOwner.us;
    String? clientId;
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.viewInsetsOf(context).bottom,
          ),
          child: StatefulBuilder(
            builder: (context, setSheet) {
              return Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Задача на ${shortDate(_selected)}',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: text,
                      autofocus: true,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        hintText: 'Что сделать',
                        filled: true,
                        fillColor: C.paper,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        SelectChip(
                          label: 'Мы',
                          selected: owner == CommitmentOwner.us,
                          onTap: () =>
                              setSheet(() => owner = CommitmentOwner.us),
                        ),
                        const SizedBox(width: 8),
                        SelectChip(
                          label: 'Клиент',
                          selected: owner == CommitmentOwner.client,
                          onTap: () =>
                              setSheet(() => owner = CommitmentOwner.client),
                        ),
                      ],
                    ),
                    if (store.clients.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String?>(
                        initialValue: clientId,
                        decoration: InputDecoration(
                          labelText: 'Человек',
                          filled: true,
                          fillColor: C.paper,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: BorderSide.none,
                          ),
                        ),
                        items: [
                          const DropdownMenuItem(
                            value: null,
                            child: Text('Не привязывать'),
                          ),
                          for (final client in store.clientsSorted)
                            DropdownMenuItem(
                              value: client.id,
                              child: Text(client.name),
                            ),
                        ],
                        onChanged: (value) => setSheet(() => clientId = value),
                      ),
                    ],
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: FilledButton(
                        style: FilledButton.styleFrom(
                          backgroundColor: C.red,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                        onPressed: () =>
                            Navigator.pop(context, text.text.trim().isNotEmpty),
                        child: const Text('Создать'),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
    final value = text.text.trim();
    text.dispose();
    if (created == true && value.isNotEmpty) {
      store.addTask(
        text: value,
        day: _selected,
        clientId: clientId,
        owner: owner,
      );
    }
  }

  void _pick(DateTime day, Store store) {
    if (_movingId != null) {
      Commitment? task;
      for (final item in store.commitments) {
        if (item.id == _movingId) task = item;
      }
      if (task != null) store.plan(task, day);
      setState(() {
        _movingId = null;
        _selected = dateOnly(day);
      });
      return;
    }
    setState(() => _selected = dateOnly(day));
  }

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final tasks = store.onDay(_selected);
    final loose = store.unscheduled;
    Commitment? moving;
    if (_movingId != null) {
      for (final item in store.commitments) {
        if (item.id == _movingId) moving = item;
      }
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(kPage, 12, kPage, 28),
      children: [
        const Text('Задачи', style: T.title),
        const SizedBox(height: 4),
        const Text(
          'Нажмите день, чтобы спланировать',
          style: TextStyle(color: C.mute, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 16),
        _Month(
          month: _month,
          selected: _selected,
          store: store,
          onPrev: () => _shiftMonth(-1),
          onNext: () => _shiftMonth(1),
          onPick: (day) => _pick(day, store),
        ),
        if (moving != null) ...[
          const SizedBox(height: 12),
          Surface(
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Куда перенести: ${moving.text}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                TextButton(
                  onPressed: () => setState(() => _movingId = null),
                  child: const Text('Отмена'),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 18),
        SectionLabel(
          longDate(_selected),
          trailing: TextButton(
            onPressed: () => _create(store),
            child: const Text('Новая'),
          ),
        ),
        if (tasks.isEmpty)
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
              'На этот день ничего не стоит',
              style: TextStyle(color: C.mute, fontWeight: FontWeight.w500),
            ),
          )
        else
          for (final task in tasks) ...[
            CommitmentTile(
              commitment: task,
              clientName: store.clientOf(task.clientId)?.name ?? '',
              showClient: task.clientId.isNotEmpty,
              onToggle: () => store.toggle(task),
              onOpen: task.callId.isEmpty
                  ? null
                  : () => openCall(context, task.callId),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => setState(() => _movingId = task.id),
                child: const Text('Перенести'),
              ),
            ),
          ],
        if (loose.isNotEmpty) ...[
          const SizedBox(height: 8),
          const SectionLabel('Без срока'),
          for (final task in loose) ...[
            CommitmentTile(
              commitment: task,
              clientName: store.clientOf(task.clientId)?.name ?? '',
              showClient: task.clientId.isNotEmpty,
              onToggle: () => store.toggle(task),
              onOpen: task.callId.isEmpty
                  ? null
                  : () => openCall(context, task.callId),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => store.plan(task, _selected),
                child: const Text('На этот день'),
              ),
            ),
          ],
        ],
      ],
    );
  }
}

class _Month extends StatelessWidget {
  const _Month({
    required this.month,
    required this.selected,
    required this.store,
    required this.onPrev,
    required this.onNext,
    required this.onPick,
  });

  final DateTime month;
  final DateTime selected;
  final Store store;
  final VoidCallback onPrev;
  final VoidCallback onNext;
  final ValueChanged<DateTime> onPick;

  @override
  Widget build(BuildContext context) {
    final first = DateTime(month.year, month.month, 1);
    final days = DateTime(month.year, month.month + 1, 0).day;
    final leading = first.weekday - 1;
    final today = dateOnly(DateTime.now());
    final cells = List<DateTime?>.filled(leading, null, growable: true);
    for (var day = 1; day <= days; day++) {
      cells.add(DateTime(month.year, month.month, day));
    }
    while (cells.length % 7 != 0) {
      cells.add(null);
    }

    return Surface(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 12),
      child: Column(
        children: [
          Row(
            children: [
              IconButton(
                onPressed: onPrev,
                icon: const Icon(Icons.chevron_left_rounded),
              ),
              Expanded(
                child: Text(
                  monthTitle(month),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              IconButton(
                onPressed: onNext,
                icon: const Icon(Icons.chevron_right_rounded),
              ),
            ],
          ),
          const Row(
            children: [
              _Dow('Пн'),
              _Dow('Вт'),
              _Dow('Ср'),
              _Dow('Чт'),
              _Dow('Пт'),
              _Dow('Сб'),
              _Dow('Вс'),
            ],
          ),
          for (var row = 0; row < cells.length ~/ 7; row++)
            Row(
              children: [
                for (var col = 0; col < 7; col++)
                  _Day(
                    day: cells[row * 7 + col],
                    selected:
                        cells[row * 7 + col] != null &&
                        dateOnly(cells[row * 7 + col]!) == selected,
                    today:
                        cells[row * 7 + col] != null &&
                        dateOnly(cells[row * 7 + col]!) == today,
                    count: cells[row * 7 + col] == null
                        ? 0
                        : store
                              .onDay(cells[row * 7 + col]!)
                              .where((c) => !c.isDone)
                              .length,
                    overdue:
                        cells[row * 7 + col] != null &&
                        store
                            .onDay(cells[row * 7 + col]!)
                            .any((c) => c.isOverdue),
                    onPick: onPick,
                  ),
              ],
            ),
        ],
      ),
    );
  }
}

class _Dow extends StatelessWidget {
  const _Dow(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: C.mute,
          ),
        ),
      ),
    );
  }
}

class _Day extends StatelessWidget {
  const _Day({
    required this.day,
    required this.selected,
    required this.today,
    required this.count,
    required this.overdue,
    required this.onPick,
  });

  final DateTime? day;
  final bool selected;
  final bool today;
  final int count;
  final bool overdue;
  final ValueChanged<DateTime> onPick;

  @override
  Widget build(BuildContext context) {
    if (day == null) return const Expanded(child: SizedBox(height: 46));
    final fg = selected ? Colors.white : C.ink;
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(2),
        child: Material(
          color: selected ? C.red : Colors.transparent,
          shape: const CircleBorder(),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: () => onPick(day!),
            child: SizedBox(
              height: 44,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${day!.day}',
                    style: TextStyle(
                      fontWeight: today ? FontWeight.w800 : FontWeight.w500,
                      color: fg,
                      decoration: today && !selected
                          ? TextDecoration.underline
                          : null,
                      decorationColor: C.red,
                    ),
                  ),
                  if (count > 0)
                    Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        color: selected
                            ? Colors.white
                            : overdue
                            ? C.red
                            : C.red,
                        shape: BoxShape.circle,
                      ),
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
