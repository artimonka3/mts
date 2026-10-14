import 'package:dogovor/data/icalendar.dart';
import 'package:dogovor/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Задача с датой становится событием iCalendar', () {
    final task = Commitment(
      id: 'k1',
      callId: 'call-1',
      clientId: 'alexey',
      owner: CommitmentOwner.us,
      text: 'Отправить КП, роуминг',
      dueDate: DateTime(2026, 10, 16),
      quote: 'до пятницы',
    );
    final client = Client(
      id: 'alexey',
      name: 'Алексей Морозов',
      company: 'БелСтрой',
      phone: '+375 29 111-22-33',
      tone: 0,
    );

    final ics = buildICalendar(
      tasks: [task],
      clientOf: (id) => id == client.id ? client : null,
    );

    expect(ics, contains('BEGIN:VCALENDAR'));
    expect(ics, contains('UID:k1@dogovor.mts'));
    expect(ics, contains('DTSTART;VALUE=DATE:20261016'));
    expect(ics, contains('DTEND;VALUE=DATE:20261017'));
    expect(ics, contains('Отправить КП\\, роуминг'));
    expect(ics, contains('X-MTS-CLIENT:Алексей Морозов'));
    expect(ics, contains('X-MTS-COMPANY:БелСтрой'));
    expect(ics, contains('STATUS:CONFIRMED'));
    expect(ics, endsWith('END:VCALENDAR\r\n'));
  });
}
