import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/models.dart';
import 'agent_settings.dart';
import 'summarize.dart';

class AgentException implements Exception {
  AgentException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Разделяет реплики и собирает саммари по расшифровке звонка.
class CallAgent {
  CallAgent(this.settings);

  final AgentSettings settings;

  Future<TalkSummary> analyze({
    required String transcript,
    required String clientName,
  }) async {
    final root = settings.baseUrl.replaceAll(RegExp(r'/+$'), '');
    final response = await http
        .post(
          Uri.parse('$root/chat/completions'),
          headers: {
            'Authorization': 'Bearer ${settings.apiKey.trim()}',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'model': settings.model.trim().isEmpty
                ? 'gpt-4o-mini'
                : settings.model.trim(),
            'temperature': 0.1,
            'response_format': {'type': 'json_object'},
            'messages': [
              {'role': 'system', 'content': _prompt},
              {
                'role': 'user',
                'content':
                    'Собеседник: $clientName.\n\nРасшифровка одним потоком, без подписей кто говорит:\n$transcript',
              },
            ],
          }),
        )
        .timeout(const Duration(seconds: 45));
    if (response.statusCode != 200) {
      throw AgentException(_errorText(response));
    }
    final body = jsonDecode(utf8.decode(response.bodyBytes));
    final content = body['choices'][0]['message']['content'] as String;
    return parseAgentReply(content, fallbackTranscript: transcript);
  }

  /// Сначала голоса по записи, потом роли «мы / клиент» и саммари.
  Future<TalkSummary> analyzeRecording({
    required String audioPath,
    required String clientName,
    required String liveTranscript,
    String? voiceReferencePath,
  }) async {
    final lines = await diarizeFile(
      audioPath,
      voiceReferencePath: voiceReferencePath,
    );
    if (lines.isEmpty) {
      if (liveTranscript.trim().isEmpty) return summarizeTalk(liveTranscript);
      return analyze(transcript: liveTranscript, clientName: clientName);
    }
    final turns = turnsFromSpeakers(lines);
    final script = lines
        .map((line) => '${line.speaker}: ${line.text}')
        .join('\n');
    try {
      final described = await _assignRoles(script, clientName);
      return TalkSummary(
        summary: described.summary,
        turns: turns,
        drafts: described.drafts,
        facts: described.facts,
      );
    } on Exception {
      return TalkSummary(
        summary: lines.take(2).map((line) => line.text).join(' '),
        turns: turns,
        drafts: const [],
      );
    }
  }

  Future<List<SpeakerLine>> diarizeFile(
    String audioPath, {
    String? voiceReferencePath,
  }) async {
    final root = settings.baseUrl.replaceAll(RegExp(r'/+$'), '');
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$root/audio/transcriptions'),
    );
    request.headers['Authorization'] = 'Bearer ${settings.apiKey.trim()}';
    request.fields['model'] = 'gpt-4o-transcribe-diarize';
    request.fields['response_format'] = 'diarized_json';
    request.fields['chunking_strategy'] = 'auto';
    if (voiceReferencePath != null && audioFileUsable(voiceReferencePath)) {
      final bytes = await File(voiceReferencePath).readAsBytes();
      request.fields['known_speaker_names[]'] = 'мы';
      request.fields['known_speaker_references[]'] =
          'data:audio/m4a;base64,${base64Encode(bytes)}';
    }
    request.files.add(await http.MultipartFile.fromPath('file', audioPath));
    final streamed = await request.send().timeout(const Duration(minutes: 2));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode != 200) {
      throw AgentException(_errorText(response));
    }
    final body = jsonDecode(utf8.decode(response.bodyBytes));
    return parseDiarizedSegments(body);
  }

  Future<TalkSummary> _assignRoles(String script, String clientName) async {
    final root = settings.baseUrl.replaceAll(RegExp(r'/+$'), '');
    final response = await http
        .post(
          Uri.parse('$root/chat/completions'),
          headers: {
            'Authorization': 'Bearer ${settings.apiKey.trim()}',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'model': settings.model.trim().isEmpty
                ? 'gpt-4o-mini'
                : settings.model.trim(),
            'temperature': 0.1,
            'response_format': {'type': 'json_object'},
            'messages': [
              {'role': 'system', 'content': _rolesPrompt},
              {'role': 'user', 'content': 'Клиент: $clientName.\n\n$script'},
            ],
          }),
        )
        .timeout(const Duration(seconds: 45));
    if (response.statusCode != 200) {
      throw AgentException(_errorText(response));
    }
    final body = jsonDecode(utf8.decode(response.bodyBytes));
    final content = body['choices'][0]['message']['content'] as String;
    return parseAgentReply(content, fallbackTranscript: script);
  }

  String _errorText(http.Response response) {
    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      return (json['error']?['message'] ?? 'Ошибка агента').toString();
    } catch (_) {
      return 'Агент ответил с ошибкой ${response.statusCode}';
    }
  }
}

class SpeakerLine {
  const SpeakerLine(this.speaker, this.text);

  final String speaker;
  final String text;
}

bool _isUs(String speaker) {
  final name = speaker.toLowerCase();
  return name == 'мы' || name == 'us' || name == 'agent';
}

/// Голос из образца — «мы». Если собеседник один, он и есть клиент.
List<Turn> turnsFromSpeakers(List<SpeakerLine> lines) {
  final others = lines
      .map((line) => line.speaker)
      .where((speaker) => !_isUs(speaker))
      .toSet();
  final singleOther = others.length == 1;
  return [
    for (final line in lines)
      Turn(
        ours: _isUs(line.speaker),
        text: line.text,
        label: _isUs(line.speaker) || singleOther
            ? null
            : 'Спикер ${line.speaker}',
      ),
  ];
}

/// Склеивает соседние куски одного голоса.
List<SpeakerLine> parseDiarizedSegments(Object? raw) {
  if (raw is! Map) return const [];
  final segments = raw['segments'];
  if (segments is! List) return const [];
  final lines = <SpeakerLine>[];
  for (final item in segments) {
    if (item is! Map) continue;
    final text = item['text']?.toString().trim() ?? '';
    if (text.isEmpty) continue;
    final speaker = (item['speaker']?.toString().trim().isNotEmpty ?? false)
        ? item['speaker'].toString().trim()
        : 'A';
    if (lines.isNotEmpty && lines.last.speaker == speaker) {
      final previous = lines.removeLast();
      lines.add(SpeakerLine(speaker, '${previous.text} $text'));
    } else {
      lines.add(SpeakerLine(speaker, text));
    }
  }
  return lines;
}

bool audioFileUsable(String? path) {
  if (path == null || path.isEmpty) return false;
  final file = File(path);
  return file.existsSync() && file.lengthSync() > 1000;
}

const _rolesPrompt = '''
Тебе дан разговор, уже размеченный по голосам: A, B, C — это разные спикеры, определённые по звуку.
Не смешивай их реплики и не придумывай новые.
Определи, какой голос — сотрудник компании («us»), а какой — клиент («client»).
Остальных, если есть, отнеси к тому, кому ближе по смыслу.
Пиши по-русски.

Верни только JSON:
{
  "summary": "1-3 предложения: о чём договорились",
  "turns": [{"speaker": "us" | "client", "text": "реплика этого голоса"}],
  "facts": ["устойчивый факт о клиенте"],
  "commitments": [
    {"owner": "us" | "client", "text": "что сделать", "due_text": "срок или null", "quote": "цитата или null"}
  ]
}
''';

const _prompt = '''
Ты разбираешь телефонный разговор сотрудника («us») и клиента («client»).
Тебе дают сплошную расшифровку без подписей. По смыслу раздели, кто какую реплику сказал.
Не выдумывай фразы, которых нет в тексте. Короткие реплики можно склеивать, если их сказал один человек подряд.
Пиши по-русски.

Верни только JSON:
{
  "summary": "1-3 предложения: о чём договорились",
  "turns": [{"speaker": "us" | "client", "text": "реплика"}],
  "facts": ["устойчивый факт о клиенте"],
  "commitments": [
    {"owner": "us" | "client", "text": "что сделать", "due_text": "срок как прозвучал или null", "quote": "короткая цитата или null"}
  ]
}
''';

TalkSummary parseAgentReply(String raw, {required String fallbackTranscript}) {
  var cleaned = raw.trim();
  if (cleaned.startsWith('```')) {
    cleaned = cleaned
        .replaceFirst(RegExp(r'^```(?:json)?'), '')
        .replaceFirst(RegExp(r'```$'), '')
        .trim();
  }
  final decoded = jsonDecode(cleaned);
  if (decoded is! Map) {
    throw AgentException('Агент вернул не объект');
  }
  final map = decoded.cast<String, dynamic>();

  final turns = <Turn>[];
  for (final item in (map['turns'] as List? ?? const [])) {
    if (item is! Map) continue;
    final text = item['text']?.toString().trim() ?? '';
    if (text.isEmpty) continue;
    turns.add(Turn(ours: item['speaker'] == 'us', text: text));
  }
  if (turns.isEmpty && fallbackTranscript.trim().isNotEmpty) {
    turns.add(Turn(ours: false, text: fallbackTranscript.trim()));
  }

  final drafts = <CommitmentDraft>[];
  for (final item in (map['commitments'] as List? ?? const [])) {
    if (item is! Map) continue;
    final text = item['text']?.toString().trim() ?? '';
    if (text.isEmpty) continue;
    drafts.add(
      CommitmentDraft(
        owner: item['owner'] == 'client'
            ? CommitmentOwner.client
            : CommitmentOwner.us,
        text: text,
        dueText: _nullable(item['due_text']),
        quote: _nullable(item['quote']),
      ),
    );
  }

  final facts = <String>[
    for (final fact in (map['facts'] as List? ?? const []))
      if (fact.toString().trim().isNotEmpty) fact.toString().trim(),
  ];

  final summary = map['summary']?.toString().trim() ?? '';
  return TalkSummary(
    summary: summary.isEmpty ? fallbackTranscript.trim() : summary,
    turns: turns,
    drafts: drafts,
    facts: facts,
  );
}

String? _nullable(Object? value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty || text == 'null') return null;
  return text;
}
