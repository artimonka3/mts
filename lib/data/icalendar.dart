import 'dart:convert';

import '../models/models.dart';

/// Календарь задач в формате iCalendar (RFC 5545).
/// CRM и системный календарь импортируют такой файл как события.
String buildICalendar({
  required List<Commitment> tasks,
  required Client? Function(String id) clientOf,
}) {
  final events = tasks.where((task) => task.dueDate != null);
  final lines = <String>[
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Договорились//MTS Hackathon//RU',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'X-WR-CALNAME:Договорились',
    for (final task in events) ..._event(task, clientOf(task.clientId)),
    'END:VCALENDAR',
  ];
  return '${lines.map(_fold).join('\r\n')}\r\n';
}

List<String> _event(Commitment task, Client? client) {
  final start = _ymd(task.dueDate!);
  final end = _ymd(task.dueDate!.add(const Duration(days: 1)));
  final who = task.owner == CommitmentOwner.us ? 'Мы' : 'Клиент';
  final description = [
    if (client != null) 'Клиент: ${client.name}',
    if (client?.company != null) 'Компания: ${client!.company}',
    if (client?.phone != null) 'Телефон: ${client!.phone}',
    'Ответственный: $who',
    if (task.quote != null) 'Цитата: ${task.quote}',
    'Источник: договорённость из телефонного разговора',
  ].join('\n');

  return [
    'BEGIN:VEVENT',
    'UID:${task.id}@dogovor.mts',
    'DTSTAMP:${_stamp(DateTime.now())}',
    'DTSTART;VALUE=DATE:$start',
    'DTEND;VALUE=DATE:$end',
    'SUMMARY:${_text(task.text)}',
    'DESCRIPTION:${_text(description)}',
    'CATEGORIES:${_text(who)}',
    'STATUS:${task.isDone ? 'COMPLETED' : 'CONFIRMED'}',
    if (client != null) 'X-MTS-CLIENT:${_text(client.name)}',
    if (client?.company != null) 'X-MTS-COMPANY:${_text(client!.company!)}',
    if (client?.phone != null) 'X-MTS-PHONE:${_text(client!.phone!)}',
    'X-MTS-OWNER:${task.owner.name}',
    if (task.callId.isNotEmpty) 'X-MTS-CALL:${_text(task.callId)}',
    'END:VEVENT',
  ];
}

String _text(String value) => value
    .replaceAll('\\', '\\\\')
    .replaceAll('\r\n', '\n')
    .replaceAll('\n', '\\n')
    .replaceAll(',', '\\,')
    .replaceAll(';', '\\;');

String _ymd(DateTime date) {
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year}$month$day';
}

String _stamp(DateTime date) {
  final utc = date.toUtc();
  final month = utc.month.toString().padLeft(2, '0');
  final day = utc.day.toString().padLeft(2, '0');
  final hour = utc.hour.toString().padLeft(2, '0');
  final minute = utc.minute.toString().padLeft(2, '0');
  final second = utc.second.toString().padLeft(2, '0');
  return '${utc.year}$month${day}T$hour$minute${second}Z';
}

String _fold(String line) {
  final bytes = utf8.encode(line);
  if (bytes.length <= 75) return line;
  final buffer = StringBuffer();
  var index = 0;
  var limit = 75;
  while (index < line.length) {
    var end = index;
    var used = 0;
    while (end < line.length && used + _charBytes(line, end) <= limit) {
      used += _charBytes(line, end);
      end++;
    }
    if (end == index) end++;
    if (index > 0) buffer.write('\r\n ');
    buffer.write(line.substring(index, end));
    index = end;
    limit = 74;
  }
  return buffer.toString();
}

int _charBytes(String value, int index) => utf8.encode(value[index]).length;
