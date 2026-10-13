import 'models/models.dart';

DateTime dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

DateTime addDays(int offset) {
  final n = DateTime.now();
  return DateTime(n.year, n.month, n.day + offset);
}

DateTime atTime(DateTime day, int hour, int minute) =>
    DateTime(day.year, day.month, day.day, hour, minute);

/// Ближайший прошедший день недели, не включая сегодня.
DateTime pastWeekday(int weekday) {
  var d = dateOnly(DateTime.now());
  do {
    d = d.subtract(const Duration(days: 1));
  } while (d.weekday != weekday);
  return d;
}

/// Ближайший такой день недели. [includeToday] — можно ли вернуть сегодня.
DateTime futureWeekday(int weekday, {bool includeToday = true}) {
  var d = dateOnly(DateTime.now());
  if (includeToday && d.weekday == weekday) return d;
  do {
    d = d.add(const Duration(days: 1));
  } while (d.weekday != weekday);
  return d;
}

/// Четверг следующей календарной недели (неделя с понедельника).
DateTime thursdayNextWeek() {
  final today = dateOnly(DateTime.now());
  final mondayThis = today.subtract(Duration(days: today.weekday - 1));
  return mondayThis.add(const Duration(days: 10));
}

int dayDiff(DateTime d) =>
    dateOnly(d).difference(dateOnly(DateTime.now())).inDays;

const _monthsGen = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];

const _monthsShort = [
  'янв',
  'фев',
  'мар',
  'апр',
  'май',
  'июн',
  'июл',
  'авг',
  'сен',
  'окт',
  'ноя',
  'дек',
];

const _weekdays = [
  '',
  'понедельник',
  'вторник',
  'среда',
  'четверг',
  'пятница',
  'суббота',
  'воскресенье',
];

String longDate(DateTime d) =>
    '${_weekdays[d.weekday]}, ${d.day} ${_monthsGen[d.month - 1]}';

String shortDate(DateTime d) => '${d.day} ${_monthsShort[d.month - 1]}';

String hm(DateTime d) =>
    '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';

String clock(int seconds) {
  final m = (seconds ~/ 60).toString().padLeft(2, '0');
  final s = (seconds % 60).toString().padLeft(2, '0');
  return '$m:$s';
}

String callWhen(DateTime d) {
  final diff = dateOnly(DateTime.now()).difference(dateOnly(d)).inDays;
  final t = hm(d);
  if (diff == 0) return 'сегодня, $t';
  if (diff == 1) return 'вчера, $t';
  return '${shortDate(d)}, $t';
}

String durationLabel(int sec) {
  if (sec < 60) return '$sec с';
  final m = sec ~/ 60;
  final s = sec % 60;
  if (s == 0) return '$m мин';
  return '$m мин $s с';
}

String dueLabel(DateTime? due) {
  if (due == null) return 'без срока';
  final diff = dayDiff(due);
  if (diff < 0) return 'просрочено · ${shortDate(due)}';
  if (diff == 0) return 'сегодня';
  if (diff == 1) return 'завтра';
  return 'до ${shortDate(due)}';
}

String commitmentWhen(Commitment c) {
  if (c.isDone) return 'готово';
  if (c.isOverdue) return dueLabel(c.dueDate);
  final spoken = c.dueText?.trim();
  if (spoken != null && spoken.isNotEmpty) return spoken;
  return dueLabel(c.dueDate);
}

String countAgreements(int n) {
  final mod10 = n % 10;
  final mod100 = n % 100;
  final String word;
  if (mod100 >= 11 && mod100 <= 14) {
    word = 'договорённостей';
  } else if (mod10 == 1) {
    word = 'договорённость';
  } else if (mod10 >= 2 && mod10 <= 4) {
    word = 'договорённости';
  } else {
    word = 'договорённостей';
  }
  return '$n $word';
}

String firstName(String name) {
  final parts = name.trim().split(RegExp(r'\s+'));
  return parts.isEmpty || parts.first.isEmpty ? name : parts.first;
}

String initials(String name) {
  final parts = name
      .trim()
      .split(RegExp(r'\s+'))
      .where((p) => p.isNotEmpty)
      .toList();
  if (parts.isEmpty) return '?';
  String ch(String s) => String.fromCharCode(s.runes.first).toUpperCase();
  if (parts.length == 1) return ch(parts.first);
  return '${ch(parts[0])}${ch(parts[1])}';
}
