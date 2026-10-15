import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';
import 'agent_settings.dart';
import 'store.dart';

class BackendException implements Exception {
  BackendException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Клиент API бэкенда: сессия, клиенты, задачи и загрузка записи.
class MtsApi {
  MtsApi(this.settings);

  final AgentSettings settings;

  String get _root => settings.serverUrl.replaceAll(RegExp(r'/+$'), '');

  Map<String, String> get _headers => {
    'Origin': _root,
    if (settings.hasSession) 'Cookie': 'mts_session=${settings.sessionCookie}',
    if (settings.csrfToken.isNotEmpty) 'X-CSRF-Token': settings.csrfToken,
  };

  /// Вход demo и загрузка клиентов с задачами. Ошибка сети не ломает локальные данные.
  Future<void> connect(Store store) async {
    await login(AgentSettings.demoLogin, AgentSettings.demoPassword);
    final people = await clients();
    final items = await tasks();
    store.mergeRemote(remoteClients: people, remoteTasks: items);
  }

  Future<void> login(String login, String password) async {
    final response = await http
        .post(
          Uri.parse('$_root/api/v1/auth/login'),
          headers: {..._headers, 'Content-Type': 'application/json'},
          body: jsonEncode({'login': login.trim(), 'password': password}),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw BackendException(_error(response));
    }
    final cookie = _cookie(response);
    final body =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (cookie == null || body['csrf_token'] == null) {
      throw BackendException('Сервер не выдал сессию');
    }
    settings.sessionCookie = cookie;
    settings.csrfToken = body['csrf_token'].toString();
    await settings.save();
  }

  Future<List<Client>> clients() async {
    final body = await _get('/api/v1/clients?limit=100');
    final items = (body['items'] as List?) ?? const [];
    return [
      for (final raw in items)
        if (raw is Map<String, dynamic>) _client(raw),
    ];
  }

  Future<List<Commitment>> tasks() async {
    final body = await _get('/api/v1/tasks?limit=100');
    final items = (body['items'] as List?) ?? const [];
    return [
      for (final raw in items)
        if (raw is Map<String, dynamic>) _task(raw),
    ];
  }

  Future<String> uploadCall({
    required String audioPath,
    required String title,
    String? clientId,
  }) async {
    final now = DateTime.now();
    final stamp =
        '${now.year.toString().padLeft(4, '0')}-'
        '${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}T'
        '${now.hour.toString().padLeft(2, '0')}:'
        '${now.minute.toString().padLeft(2, '0')}:'
        '${now.second.toString().padLeft(2, '0')}+03:00';
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$_root/api/v1/calls'),
    );
    request.headers.addAll({
      ..._headers,
      'Idempotency-Key': 'mobile-${now.microsecondsSinceEpoch}',
    });
    request.fields['metadata'] = jsonEncode({
      'title': title,
      'call_at': stamp,
      'timezone': 'Europe/Minsk',
      'language': 'ru',
      'source': 'upload',
      if (clientId != null && clientId.isNotEmpty) 'client_id': clientId,
      'participants': [
        {'display_name': title, 'role': 'client'},
      ],
      'processing_rights_confirmed': true,
      'notice_version': 'mobile-1',
    });
    request.files.add(await http.MultipartFile.fromPath('audio', audioPath));
    final streamed = await request.send().timeout(const Duration(minutes: 2));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode != 202 && response.statusCode != 200) {
      throw BackendException(_error(response));
    }
    final body =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    return body['call_id'].toString();
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final response = await http
        .get(Uri.parse('$_root$path'), headers: _headers)
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw BackendException(_error(response));
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Client _client(Map<String, dynamic> json) {
    final contacts = json['contacts'];
    String? phone;
    if (contacts is Map && contacts.isNotEmpty) {
      phone = contacts.values.first.toString();
    }
    return Client(
      id: json['id'].toString(),
      name: (json['display_name'] ?? 'Клиент').toString(),
      phone: phone,
      tone: 0,
      facts: [
        if (json['notes'] != null && json['notes'].toString().isNotEmpty)
          json['notes'].toString(),
      ],
    );
  }

  Commitment _task(Map<String, dynamic> json) {
    final due = json['due'];
    DateTime? date;
    String? spoken;
    if (due is Map) {
      spoken = due['original_text']?.toString();
      final kind = due['kind'];
      if (kind == 'date_only' && due['date'] != null) {
        date = DateTime.tryParse(due['date'].toString());
      } else if (kind == 'instant' && due['at'] != null) {
        date = DateTime.tryParse(due['at'].toString());
      } else if (kind == 'interval' && due['start'] != null) {
        date = DateTime.tryParse(due['start'].toString());
      }
    }
    return Commitment(
      id: json['id'].toString(),
      callId: (json['call_id'] ?? '').toString(),
      clientId: (json['client_id'] ?? '').toString(),
      owner: CommitmentOwner.us,
      text: (json['action'] ?? 'Задача').toString(),
      dueDate: date,
      dueText: spoken,
      status: json['execution'] == 'done'
          ? CommitmentStatus.done
          : CommitmentStatus.open,
    );
  }

  String? _cookie(http.Response response) {
    final raw = response.headers['set-cookie'];
    if (raw == null) return null;
    return RegExp('mts_session=([^;]+)').firstMatch(raw)?.group(1);
  }

  String _error(http.Response response) {
    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      return (json['message'] ?? json['detail'] ?? 'Ошибка сервера').toString();
    } catch (_) {
      return 'Сервер ответил ${response.statusCode}';
    }
  }
}
