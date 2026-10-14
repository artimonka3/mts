import 'package:flutter/widgets.dart';

import '../format.dart';
import '../models/models.dart';
import '../theme.dart';

/// Память приложения на время сессии. Данные демонстрационные.
class Store extends ChangeNotifier {
  Store() {
    _seed();
  }

  static Store of(BuildContext context) => StoreScope.of(context);

  final List<Client> clients = [];
  final List<CallRecord> calls = [];
  final List<Commitment> commitments = [];
  final Map<String, List<ChatMessage>> chats = {};
  int _seq = 100;

  List<ChatMessage> chatOf(String callId) => chats[callId] ?? const [];

  void addChat(String callId, ChatMessage message) {
    chats.putIfAbsent(callId, () => []).add(message);
    notifyListeners();
  }

  /// Перенос людей с телефона. Уже существующие номера пропускаются.
  int importPeople(
    List<({String name, String? company, String phone})> people,
  ) {
    var added = 0;
    for (final person in people) {
      final name = person.name.trim();
      final phone = person.phone.trim();
      if (name.isEmpty || phone.isEmpty) continue;
      if (_findByPhone(phone) != null) continue;
      clients.add(
        Client(
          id: _id(),
          name: name,
          company: person.company?.trim().isEmpty ?? true
              ? null
              : person.company!.trim(),
          phone: phone,
          tone: clients.length % C.tones.length,
        ),
      );
      added++;
    }
    if (added > 0) notifyListeners();
    return added;
  }

  Client? _findByPhone(String phone) {
    final tail = _tail(phone);
    if (tail.length < 6) return null;
    for (final client in clients) {
      if (_tail(client.phone ?? '') == tail) return client;
    }
    return null;
  }

  String _tail(String phone) {
    final digits = phone.replaceAll(RegExp(r'\D'), '');
    if (digits.length <= 9) return digits;
    return digits.substring(digits.length - 9);
  }

  String _id() => '${_seq++}';

  Client? clientOf(String id) {
    for (final c in clients) {
      if (c.id == id) return c;
    }
    return null;
  }

  List<CallRecord> get callsSorted {
    final list = [...calls];
    list.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return list;
  }

  List<CallRecord> callsOf(String clientId) =>
      callsSorted.where((c) => c.clientId == clientId).toList();

  List<Commitment> commitmentsOfCall(String callId) =>
      commitments.where((c) => c.callId == callId).toList();

  int openFor(String clientId) =>
      commitments.where((c) => c.clientId == clientId && !c.isDone).length;

  bool hasOverdue(String clientId) =>
      commitments.any((c) => c.clientId == clientId && c.isOverdue);

  List<Commitment> get openCommitments {
    final list = commitments.where((c) => !c.isDone).toList()..sort(_byDue);
    return list;
  }

  List<Commitment> get doneCommitments {
    final list = commitments.where((c) => c.isDone).toList()..sort(_byDue);
    return list;
  }

  List<Commitment> forClient(String clientId) {
    final list = commitments.where((c) => c.clientId == clientId).toList();
    list.sort((a, b) {
      if (a.isDone != b.isDone) return a.isDone ? 1 : -1;
      return _byDue(a, b);
    });
    return list;
  }

  int get overdueCount => commitments.where((c) => c.isOverdue).length;

  int get dueTodayCount => commitments
      .where((c) => !c.isDone && c.dueDate != null && dayDiff(c.dueDate!) == 0)
      .length;

  int get onClientCount => commitments
      .where((c) => !c.isDone && c.owner == CommitmentOwner.client)
      .length;

  List<Client> get clientsSorted {
    final list = [...clients];
    list.sort((a, b) {
      final byOpen = openFor(b.id) - openFor(a.id);
      if (byOpen != 0) return byOpen;
      return a.name.compareTo(b.name);
    });
    return list;
  }

  int _byDue(Commitment a, Commitment b) {
    if (a.isOverdue != b.isOverdue) return a.isOverdue ? -1 : 1;
    final ad = a.dueDate;
    final bd = b.dueDate;
    if (ad == null && bd == null) return 0;
    if (ad == null) return 1;
    if (bd == null) return -1;
    return ad.compareTo(bd);
  }

  void addTask({
    required String text,
    required DateTime day,
    String? clientId,
    CommitmentOwner owner = CommitmentOwner.us,
  }) {
    final clean = text.trim();
    if (clean.isEmpty) return;
    commitments.add(
      Commitment(
        id: _id(),
        callId: '',
        clientId: clientId ?? '',
        owner: owner,
        text: clean,
        dueDate: dateOnly(day),
        dueText: shortDate(day),
      ),
    );
    notifyListeners();
  }

  void plan(Commitment c, DateTime day) {
    c.dueDate = dateOnly(day);
    c.dueText = shortDate(day);
    notifyListeners();
  }

  List<Commitment> onDay(DateTime day) {
    final target = dateOnly(day);
    final list = commitments.where((c) {
      if (c.dueDate == null) return false;
      return dateOnly(c.dueDate!) == target;
    }).toList();
    list.sort((a, b) {
      if (a.isDone != b.isDone) return a.isDone ? 1 : -1;
      return a.text.compareTo(b.text);
    });
    return list;
  }

  List<Commitment> get unscheduled =>
      commitments.where((c) => !c.isDone && c.dueDate == null).toList();

  void toggle(Commitment c) {
    c.status = c.isDone ? CommitmentStatus.open : CommitmentStatus.done;
    notifyListeners();
  }

  CallRecord save({
    required String clientName,
    required String company,
    required String phone,
    required String summary,
    required List<String> facts,
    required List<Turn> turns,
    required int durationSec,
    required List<CommitmentDraft> drafts,
    CallDirection direction = CallDirection.outgoing,
  }) {
    final client =
        _find(clientName, company) ??
        Client(
          id: _id(),
          name: clientName,
          company: company,
          phone: phone,
          tone: clients.length % C.tones.length,
          facts: facts,
        );
    if (!clients.contains(client)) {
      clients.add(client);
    } else {
      client.phone ??= phone;
      client.company ??= company;
      for (final fact in facts) {
        final known = client.facts.any(
          (e) => e.toLowerCase() == fact.toLowerCase(),
        );
        if (!known) client.facts.add(fact);
      }
    }

    final call = CallRecord(
      id: _id(),
      clientId: client.id,
      createdAt: DateTime.now(),
      summary: summary,
      turns: [...turns],
      durationSec: durationSec,
      direction: direction,
    );
    calls.add(call);
    for (final draft in drafts) {
      commitments.add(
        Commitment(
          id: _id(),
          callId: call.id,
          clientId: client.id,
          owner: draft.owner,
          text: draft.text,
          dueDate: draft.dueDate,
          dueText: draft.dueText,
          quote: draft.quote,
        ),
      );
    }
    notifyListeners();
    return call;
  }

  Client? _find(String name, String company) {
    final n = name.trim().toLowerCase();
    final c = company.trim().toLowerCase();
    for (final client in clients) {
      if (client.name.trim().toLowerCase() == n &&
          (client.company ?? '').trim().toLowerCase() == c) {
        return client;
      }
    }
    return null;
  }

  void _seed() {
    final fridayPast = pastWeekday(DateTime.friday);
    final wednesday = futureWeekday(DateTime.wednesday);
    final monday = futureWeekday(DateTime.monday, includeToday: false);
    final friday = futureWeekday(DateTime.friday);
    final tomorrow = addDays(1);

    clients.addAll([
      Client(
        id: 'alexey',
        name: 'Алексей Морозов',
        company: 'БелСтрой',
        phone: '+375 29 612-44-18',
        tone: 0,
        facts: const [
          '40 корпоративных номеров',
          'Бюджет до 800 руб. в месяц',
          'ЛПР — директор Сергей Петрович',
          'Важны условия роуминга',
          'Почта: alexey@belstroy.by',
        ],
      ),
      Client(
        id: 'marina',
        name: 'Марина Коваль',
        company: 'Аптека 36,6',
        phone: '+375 29 330-18-90',
        tone: 1,
        facts: const [
          '12 аптек',
          'Нужны связь для курьеров и интернет в точки',
          'Один счёт на всю сеть',
          'Две точки переезжают',
        ],
      ),
      Client(
        id: 'dmitry',
        name: 'Дмитрий Савич',
        company: 'Логистик Плюс',
        phone: '+375 33 701-55-02',
        tone: 2,
        facts: const [
          '80 машин в парке',
          'Интересует М2М',
          'Пилот на 10 машин, без замены всего парка',
        ],
      ),
      Client(
        id: 'olga',
        name: 'Ольга Берест',
        company: 'Кофейня «Двор»',
        phone: '+375 25 909-14-77',
        tone: 3,
        facts: const [
          'Одна точка',
          'Гостевой Wi-Fi и касса',
          'Небольшой бюджет',
        ],
      ),
      Client(
        id: 'missed',
        name: '+375 (29) 609-20-72',
        phone: '+375296092072',
        tone: 4,
        facts: const ['Просил перезвонить по договору на сим-карты'],
      ),
    ]);

    calls.addAll([
      CallRecord(
        id: 'call-alexey',
        clientId: 'alexey',
        createdAt: atTime(pastWeekday(DateTime.thursday), 15, 10),
        durationSec: 11 * 60,
        direction: CallDirection.outgoing,
        summary: 'Корпоративные номера для «БелСтрой»: 40 сим, бюджет до 800 руб. КП с роумингом, список сотрудников и созвон по договору.',
        turns: const [
          Turn(
            ours: true,
            text: 'Алексей, добрый день, это Ирина из МТС Бизнес. Возвращаюсь по корпоративным номерам для «БелСтрой».',
          ),
          Turn(
            ours: false,
            text: 'Да, Ирина. Нам нужно сорок номеров, бюджет — до восьмисот рублей в месяц.',
          ),
          Turn(
            ours: true,
            text: 'Тогда подготовлю коммерческое предложение с роумингом и отправлю на почту до пятницы.',
          ),
          Turn(
            ours: false,
            text: 'Хорошо. Я до среды согласую список сотрудников с Сергеем Петровичем и пришлю таблицу.',
          ),
          Turn(
            ours: true,
            text: 'И в понедельник созвонимся уже по договору. Директору важны условия роуминга — включу их отдельно.',
          ),
          Turn(
            ours: false,
            text: 'Да, он как раз про роуминг и спрашивал. Договорились.',
          ),
        ],
      ),
      CallRecord(
        id: 'call-marina',
        clientId: 'marina',
        createdAt: atTime(addDays(0), 9, 20),
        durationSec: 6 * 60,
        summary: 'Пакет для сети из 12 аптек: связь курьерам и интернет в точки. Расчёт сегодня, адреса — до пятницы.',
        turns: const [
          Turn(
            ours: true,
            text: 'Марина, добрый день. Собрала для сети «Аптека 36,6» пакет: связь для курьеров и интернет в точки.',
          ),
          Turn(
            ours: false,
            text: 'Нам важно закрыть все двенадцать адресов одним счётом.',
          ),
          Turn(
            ours: true,
            text: 'Сделаю. Расчёт на двенадцать точек пришлю сегодня до конца дня.',
          ),
          Turn(
            ours: false,
            text: 'А я до пятницы пришлю актуальные адреса — два из них переезжают.',
          ),
          Turn(
            ours: true,
            text: 'Приняла. Как получу адреса, зафиксирую их в договоре.',
          ),
        ],
      ),
      CallRecord(
        id: 'call-dmitry',
        clientId: 'dmitry',
        createdAt: atTime(addDays(0), 11, 5),
        durationSec: 8 * 60,
        direction: CallDirection.outgoing,
        summary: 'Пилот М2М на 10 машин вместо всего парка. Завтра — схема и список бортовых номеров.',
        turns: const [
          Turn(
            ours: true,
            text: 'Дмитрий, по М2М для «Логистик Плюс». Можем запустить пилот на десять машин, без замены всего парка.',
          ),
          Turn(
            ours: false,
            text: 'Восемьдесят машин сразу не потяну. Давайте десять.',
          ),
          Turn(
            ours: true,
            text: 'Завтра пришлю схему пилота и стоимость сим-карт.',
          ),
          Turn(
            ours: false,
            text: 'Завтра же подтвержу бортовые номера, которые берём в пилот.',
          ),
          Turn(
            ours: true,
            text: 'Отлично, тогда со следующего понедельника можем ставить.',
          ),
        ],
      ),
      CallRecord(
        id: 'call-olga',
        clientId: 'olga',
        createdAt: atTime(addDays(-9), 16, 40),
        durationSec: 4 * 60,
        direction: CallDirection.outgoing,
        summary: 'Гостевой Wi-Fi и касса для кофейни. Тариф отправлен, счёт клиент оплачивает.',
        turns: const [
          Turn(
            ours: true,
            text: 'Ольга, по кофейне «Двор» — гостевой Wi-Fi и одна касса. Отправляю тариф сегодня.',
          ),
          Turn(
            ours: false,
            text: 'Да, пришлите. Счёт оплачу на этой неделе, бюджет небольшой.',
          ),
          Turn(
            ours: true,
            text: 'Тариф уже на почте. Там отдельная сеть для гостей и сеть для кассы.',
          ),
          Turn(ours: false, text: 'Получила, спасибо. Оплачиваю.'),
        ],
      ),
      CallRecord(
        id: 'call-missed',
        clientId: 'missed',
        createdAt: atTime(addDays(-1), 18, 42),
        durationSec: 28,
        direction: CallDirection.missed,
        summary: 'Пропущенный. В голосовом сообщении просят перезвонить по договору на корпоративные сим-карты.',
        turns: const [
          Turn(
            ours: false,
            text: 'Добрый день, это по договору на сим-карты. Перезвоните, пожалуйста, сегодня.',
          ),
        ],
      ),
    ]);

    commitments.addAll([
      Commitment(
        id: 'k1',
        callId: 'call-alexey',
        clientId: 'alexey',
        owner: CommitmentOwner.us,
        text: 'Отправить КП с условиями роуминга на alexey@belstroy.by',
        dueDate: fridayPast,
        dueText: 'до пятницы',
        quote: 'подготовлю коммерческое предложение с роумингом и отправлю на почту до пятницы',
      ),
      Commitment(
        id: 'k2',
        callId: 'call-alexey',
        clientId: 'alexey',
        owner: CommitmentOwner.client,
        text: 'Прислать список сотрудников после согласования с директором',
        dueDate: wednesday,
        dueText: 'до среды',
        quote: 'до среды согласую список сотрудников с Сергеем Петровичем и пришлю таблицу',
      ),
      Commitment(
        id: 'k3',
        callId: 'call-alexey',
        clientId: 'alexey',
        owner: CommitmentOwner.us,
        text: 'Созвониться и обсудить договор',
        dueDate: monday,
        dueText: 'в понедельник',
        quote: 'в понедельник созвонимся уже по договору',
      ),
      Commitment(
        id: 'k4',
        callId: 'call-marina',
        clientId: 'marina',
        owner: CommitmentOwner.us,
        text: 'Прислать расчёт на 12 точек одним счётом',
        dueDate: addDays(0),
        dueText: 'сегодня до конца дня',
        quote: 'расчёт на двенадцать точек пришлю сегодня до конца дня',
      ),
      Commitment(
        id: 'k5',
        callId: 'call-marina',
        clientId: 'marina',
        owner: CommitmentOwner.client,
        text: 'Прислать актуальные адреса аптек',
        dueDate: friday,
        dueText: 'до пятницы',
        quote: 'до пятницы пришлю актуальные адреса',
      ),
      Commitment(
        id: 'k6',
        callId: 'call-dmitry',
        clientId: 'dmitry',
        owner: CommitmentOwner.us,
        text: 'Прислать схему пилота М2М на 10 машин и стоимость сим-карт',
        dueDate: tomorrow,
        dueText: 'завтра',
        quote: 'завтра пришлю схему пилота и стоимость сим-карт',
      ),
      Commitment(
        id: 'k7',
        callId: 'call-dmitry',
        clientId: 'dmitry',
        owner: CommitmentOwner.client,
        text: 'Подтвердить бортовые номера для пилота',
        dueDate: tomorrow,
        dueText: 'завтра',
        quote: 'завтра же подтвержу бортовые номера',
      ),
      Commitment(
        id: 'k8',
        callId: 'call-olga',
        clientId: 'olga',
        owner: CommitmentOwner.us,
        text: 'Отправить тариф на гостевой Wi-Fi и кассу',
        dueDate: addDays(-9),
        dueText: 'сегодня',
        quote: 'тариф уже на почте',
        status: CommitmentStatus.done,
      ),
      Commitment(
        id: 'k9',
        callId: 'call-olga',
        clientId: 'olga',
        owner: CommitmentOwner.client,
        text: 'Оплатить счёт за тариф',
        dueDate: addDays(-7),
        dueText: 'на этой неделе',
        quote: 'счёт оплачу на этой неделе',
        status: CommitmentStatus.done,
      ),
    ]);
  }
}

class StoreScope extends InheritedNotifier<Store> {
  const StoreScope({super.key, required Store store, required super.child})
    : super(notifier: store);

  static Store of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<StoreScope>();
    assert(scope != null, 'StoreScope не найден');
    return scope!.notifier!;
  }
}
