import '../models/models.dart';

class TalkSummary {
  const TalkSummary({
    required this.summary,
    required this.turns,
    required this.drafts,
  });

  final String summary;
  final List<Turn> turns;
  final List<CommitmentDraft> drafts;
}

/// Короткое саммари по расшифровке, без внешнего ИИ.
TalkSummary summarizeTalk(String transcript) {
  final text = transcript.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (text.isEmpty) {
    return const TalkSummary(
      summary:
          'Речь не расслышали. Включите громкую связь и держите телефон ближе.',
      turns: [],
      drafts: [],
    );
  }

  final sentences = text
      .split(RegExp(r'(?<=[.!?])\s+'))
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();
  final summary = sentences.length <= 2
      ? text
      : '${sentences[0]} ${sentences[1]}';

  const keys = [
    'отправ',
    'пришл',
    'созвон',
    'перезвон',
    'договор',
    'завтра',
    'пятниц',
    'понедел',
    'сред',
    'обеща',
  ];
  final drafts = <CommitmentDraft>[];
  for (final sentence in sentences) {
    final low = sentence.toLowerCase();
    if (!keys.any(low.contains)) continue;
    final ours =
        low.contains('я ') ||
        low.startsWith('я ') ||
        low.contains('мы ') ||
        low.contains('отправлю') ||
        low.contains('перезвоню');
    drafts.add(
      CommitmentDraft(
        owner: ours ? CommitmentOwner.us : CommitmentOwner.client,
        text: sentence,
        dueText: _due(low),
      ),
    );
    if (drafts.length == 4) break;
  }

  return TalkSummary(
    summary: summary,
    turns: [Turn(ours: false, text: text)],
    drafts: drafts,
  );
}

String? _due(String low) {
  if (low.contains('завтра')) return 'завтра';
  if (low.contains('пятниц')) return 'до пятницы';
  if (low.contains('понедел')) return 'в понедельник';
  if (low.contains('сред')) return 'до среды';
  if (low.contains('сегодня')) return 'сегодня';
  return null;
}
