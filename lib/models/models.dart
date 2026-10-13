enum CallDirection { incoming, outgoing, missed }

enum CommitmentOwner { us, client }

class ChatMessage {
  ChatMessage({required this.fromUser, required this.text});

  final bool fromUser;
  final String text;
}

enum CommitmentStatus { open, done }

class Turn {
  const Turn({required this.ours, required this.text});

  final bool ours;
  final String text;
}

class CommitmentDraft {
  const CommitmentDraft({
    required this.owner,
    required this.text,
    this.dueDate,
    this.dueText,
    this.quote,
  });

  final CommitmentOwner owner;
  final String text;
  final DateTime? dueDate;
  final String? dueText;
  final String? quote;
}

class Commitment {
  Commitment({
    required this.id,
    required this.callId,
    required this.clientId,
    required this.owner,
    required this.text,
    this.dueDate,
    this.dueText,
    this.quote,
    this.status = CommitmentStatus.open,
  });

  final String id;
  final String callId;
  final String clientId;
  final CommitmentOwner owner;
  final String text;
  final DateTime? dueDate;
  final String? dueText;
  final String? quote;
  CommitmentStatus status;

  bool get isDone => status == CommitmentStatus.done;

  bool get isOverdue {
    if (isDone || dueDate == null) return false;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final due = DateTime(dueDate!.year, dueDate!.month, dueDate!.day);
    return due.isBefore(today);
  }
}

class Client {
  Client({
    required this.id,
    required this.name,
    required this.tone,
    this.company,
    this.phone,
    List<String> facts = const [],
  }) : facts = List<String>.of(facts);

  final String id;
  final String name;
  final int tone;
  String? company;
  String? phone;
  final List<String> facts;
}

class CallRecord {
  CallRecord({
    required this.id,
    required this.clientId,
    required this.createdAt,
    required this.summary,
    required this.turns,
    required this.durationSec,
    this.direction = CallDirection.incoming,
  });

  final String id;
  final String clientId;
  final DateTime createdAt;
  final String summary;
  final List<Turn> turns;
  final int durationSec;
  final CallDirection direction;
}
