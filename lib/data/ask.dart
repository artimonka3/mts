import '../models/models.dart';

/// Ответ по уже разобранному звонку. Сеть не вызывается.
String answerAbout({
  required CallRecord call,
  required Client? client,
  required List<Commitment> items,
  required String question,
}) {
  final q = question.toLowerCase();
  final name = client?.name ?? 'клиент';
  final company = client?.company;

  bool has(String s) => q.contains(s);

  if (has('кто') || has('компан') || has('номер') || has('телефон')) {
    final who = company == null ? name : '$name, $company';
    final phone = client?.phone == null ? '' : ' Телефон: ${client!.phone}.';
    return '$who.$phone';
  }

  if (has('срок') ||
      has('когда') ||
      has('договор') ||
      has('обещал') ||
      has('обяза')) {
    if (items.isEmpty) return 'В этом звонке отдельных обязательств не было.';
    final lines = items
        .map((c) {
          final who = c.owner == CommitmentOwner.us ? 'Мы' : 'Клиент';
          final when = c.dueText ?? 'без срока';
          return '• $who: ${c.text} ($when)';
        })
        .join('\n');
    return 'Вот что зафиксировано:\n$lines';
  }

  if (has('цитат') ||
      has('дослов') ||
      has('что сказал') ||
      has('что говорил')) {
    final bits = call.turns.take(3).map((t) {
      final who = t.ours ? 'Мы' : name;
      return '$who: ${t.text}';
    });
    return bits.join('\n\n');
  }

  if (has('факт') && client != null && client.facts.isNotEmpty) {
    return client.facts.map((f) => '• $f').join('\n');
  }

  return 'По звонку с $name: ${call.summary}\n\nМогу уточнить сроки, кто что обещал, или пересказать, что говорили.';
}
