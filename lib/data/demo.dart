import '../format.dart';
import '../models/models.dart';

class DemoScript {
  const DemoScript({
    required this.clientName,
    required this.company,
    required this.phone,
    required this.summary,
    required this.facts,
    required this.turns,
    required this.drafts,
    required this.durationSec,
  });

  final String clientName;
  final String company;
  final String phone;
  final String summary;
  final List<String> facts;
  final List<Turn> turns;
  final List<CommitmentDraft> drafts;
  final int durationSec;
}

/// Готовый разбор, который показываем после «записи».
DemoScript demoScript() {
  final tomorrow = addDays(1);
  final friday = futureWeekday(DateTime.friday);
  final thursday = thursdayNextWeek();

  return DemoScript(
    clientName: 'Виктор Лебедев',
    company: 'НордЛинк',
    phone: '+375 29 555-19-40',
    durationSec: 4 * 60 + 12,
    summary: '«НордЛинк» сравнивает корпоративные тарифы на 25 человек. Завтра отправляем сравнение, бюджет согласуют до пятницы, встреча в офисе — на следующей неделе.',
    facts: const [
      '25 сотрудников',
      'Офис на ул. Притыцкого',
      'Сейчас у другого оператора, контракт до ноября',
      'Бюджет согласует финансовый директор',
    ],
    turns: const [
      Turn(
        ours: true,
        text: 'Виктор, добрый день, это Ирина, МТС Бизнес. Вы просили сравнить корпоративные тарифы для «НордЛинк».',
      ),
      Turn(
        ours: false,
        text: 'Да. У нас двадцать пять человек в офисе на Притыцкого. Сейчас сидим у другого оператора, контракт до ноября.',
      ),
      Turn(
        ours: true,
        text: 'Тогда завтра вышлю сравнение «Умного бизнеса» и «Безлимита» — с ценой перехода.',
      ),
      Turn(
        ours: false,
        text: 'До пятницы согласую бюджет с финансовым директором. Без неё не подпишу.',
      ),
      Turn(
        ours: true,
        text: 'И давайте на следующей неделе встретимся у вас в офисе, покажу условия очно.',
      ),
      Turn(ours: false, text: 'Давайте. Ориентируемся на четверг.'),
    ],
    drafts: [
      CommitmentDraft(
        owner: CommitmentOwner.us,
        text: 'Выслать сравнение тарифов «Умный бизнес» и «Безлимит»',
        dueDate: tomorrow,
        dueText: 'завтра',
        quote: 'завтра вышлю сравнение «Умного бизнеса» и «Безлимита»',
      ),
      CommitmentDraft(
        owner: CommitmentOwner.client,
        text: 'Согласовать бюджет с финансовым директором',
        dueDate: friday,
        dueText: 'до пятницы',
        quote: 'до пятницы согласую бюджет с финансовым директором',
      ),
      CommitmentDraft(
        owner: CommitmentOwner.us,
        text: 'Встретиться в офисе на ул. Притыцкого',
        dueDate: thursday,
        dueText: 'в четверг на следующей неделе',
        quote: 'на следующей неделе встретимся у вас в офисе',
      ),
    ],
  );
}
