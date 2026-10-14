import 'package:dogovor/data/call_agent.dart';
import 'package:dogovor/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Ответ агента раскладывается на реплики и саммари', () {
    const raw = '''
{"summary":"Договорились отправить КП завтра.","turns":[{"speaker":"us","text":"Я отправлю предложение завтра."},{"speaker":"client","text":"Хорошо, жду."}],"facts":["Нужно 40 номеров"],"commitments":[{"owner":"us","text":"Отправить КП","due_text":"завтра","quote":"отправлю предложение завтра"}]}
''';

    final talk = parseAgentReply(raw, fallbackTranscript: 'сырой текст');

    expect(talk.summary, contains('КП'));
    expect(talk.turns, hasLength(2));
    expect(talk.turns.first.ours, isTrue);
    expect(talk.turns.last.ours, isFalse);
    expect(talk.facts, ['Нужно 40 номеров']);
    expect(talk.drafts.single.owner, CommitmentOwner.us);
    expect(talk.drafts.single.dueText, 'завтра');
  });

  test('Соседние куски одного голоса склеиваются', () {
    final lines = parseDiarizedSegments({
      'segments': [
        {'speaker': 'A', 'text': 'Алло'},
        {'speaker': 'A', 'text': 'это Ирина'},
        {'speaker': 'B', 'text': 'Да, слушаю'},
      ],
    });

    expect(lines, hasLength(2));
    expect(lines.first.speaker, 'A');
    expect(lines.first.text, 'Алло это Ирина');
    expect(lines.last.speaker, 'B');
  });

  test('Образец голоса помечает нас, второй голос — клиент', () {
    final turns = turnsFromSpeakers(const [
      SpeakerLine('мы', 'Я отправлю предложение'),
      SpeakerLine('A', 'Жду до пятницы'),
    ]);

    expect(turns.first.ours, isTrue);
    expect(turns.first.label, isNull);
    expect(turns.last.ours, isFalse);
    expect(turns.last.label, isNull);
    expect(turns.last.text, 'Жду до пятницы');
  });
}
