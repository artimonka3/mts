import 'package:dogovor/data/ask.dart';
import 'package:dogovor/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Ответ по звонку достаёт сроки из договорённостей', () {
    final call = CallRecord(
      id: 'c',
      clientId: 'a',
      createdAt: DateTime(2026, 10, 13),
      summary: 'Обсудили тарифы.',
      turns: const [Turn(ours: true, text: 'Отправлю КП до пятницы')],
      durationSec: 60,
    );
    final items = [
      Commitment(
        id: 'k',
        callId: 'c',
        clientId: 'a',
        owner: CommitmentOwner.us,
        text: 'Отправить КП',
        dueText: 'до пятницы',
      ),
    ];

    final answer = answerAbout(
      call: call,
      client: Client(id: 'a', name: 'Алексей', tone: 0),
      items: items,
      question: 'какие сроки',
    );

    expect(answer, contains('Отправить КП'));
    expect(answer, contains('до пятницы'));
  });
}
