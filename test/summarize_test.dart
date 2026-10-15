import 'package:dogovor/data/summarize.dart';
import 'package:dogovor/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Саммари берёт первые фразы и обещание со сроком', () {
    final talk = summarizeTalk(
      'Обсудили тариф на сорок номеров. Я отправлю коммерческое предложение завтра. Клиент пришлёт список сотрудников.',
    );

    expect(talk.summary, contains('Обсудили тариф'));
    expect(talk.drafts, isNotEmpty);
    expect(
      talk.drafts.any(
        (d) => d.owner == CommitmentOwner.us && d.dueText == 'завтра',
      ),
      isTrue,
    );
  });
}
