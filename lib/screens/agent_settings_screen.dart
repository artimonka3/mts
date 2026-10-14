import 'package:flutter/material.dart';

import '../data/agent_settings.dart';
import '../data/mts_api.dart';
import '../data/store.dart';
import '../theme.dart';

class AgentSettingsScreen extends StatefulWidget {
  const AgentSettingsScreen({super.key});

  @override
  State<AgentSettingsScreen> createState() => _AgentSettingsScreenState();
}

class _AgentSettingsScreenState extends State<AgentSettingsScreen> {
  final _key = TextEditingController();
  final _url = TextEditingController();
  final _model = TextEditingController();
  final _server = TextEditingController();
  final _login = TextEditingController();
  final _password = TextEditingController();
  bool _ready = false;
  bool _saving = false;
  bool _connecting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final settings = await AgentSettings.load();
    if (!mounted) return;
    _key.text = settings.apiKey;
    _url.text = settings.baseUrl;
    _model.text = settings.model;
    _server.text = settings.serverUrl;
    setState(() => _ready = true);
  }

  @override
  void dispose() {
    _key.dispose();
    _url.dispose();
    _model.dispose();
    _server.dispose();
    _login.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<AgentSettings> _current() async {
    final previous = await AgentSettings.load();
    return AgentSettings(
      apiKey: _key.text,
      baseUrl: _url.text.isEmpty ? 'https://api.openai.com/v1' : _url.text,
      model: _model.text.isEmpty ? 'gpt-4o-mini' : _model.text,
      serverUrl: _server.text,
      sessionCookie: previous.sessionCookie,
      csrfToken: previous.csrfToken,
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await (await _current()).save();
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  Future<void> _connect() async {
    setState(() => _connecting = true);
    try {
      final settings = await _current();
      await settings.save();
      final api = MtsApi(settings);
      await api.login(_login.text, _password.text);
      final clients = await api.clients();
      final tasks = await api.tasks();
      if (!mounted) return;
      Store.of(context).mergeRemote(remoteClients: clients, remoteTasks: tasks);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Подключено: ${clients.length} клиентов, ${tasks.length} задач',
          ),
        ),
      );
    } on Exception catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось подключиться: $error')),
      );
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F3F7),
      body: SafeArea(
        child: _ready
            ? ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                children: [
                  Row(
                    children: [
                      IconButton(
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.arrow_back_ios_new_rounded),
                      ),
                      const Text(
                        'ИИ-агент',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Бэкенд хранит клиентов, звонки и задачи. Логин demo, пароль из .env сервера.',
                    style: TextStyle(height: 1.35, color: C.inkSoft),
                  ),
                  const SizedBox(height: 12),
                  _field(_server, 'Адрес сервера'),
                  const SizedBox(height: 12),
                  _field(_login, 'Логин'),
                  const SizedBox(height: 12),
                  _field(_password, 'Пароль', secret: true),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 48,
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: _connecting ? null : _connect,
                      child: Text(
                        _connecting ? 'Подключаюсь…' : 'Подключить бэкенд',
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  const Text(
                    'Перед звонком приложение записывает ваш голос. По записи разговора модель отличает вас от собеседника и пишет саммари. Нужен ключ OpenAI.',
                    style: TextStyle(height: 1.35, color: C.inkSoft),
                  ),
                  const SizedBox(height: 18),
                  _field(_key, 'API-ключ', secret: true),
                  const SizedBox(height: 12),
                  _field(_url, 'Адрес API'),
                  const SizedBox(height: 12),
                  _field(_model, 'Модель'),
                  const SizedBox(height: 20),
                  SizedBox(
                    height: 52,
                    child: FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: C.red,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      onPressed: _saving ? null : _save,
                      child: Text(_saving ? 'Сохраняю…' : 'Сохранить'),
                    ),
                  ),
                ],
              )
            : const Center(child: CircularProgressIndicator(color: C.red)),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    bool secret = false,
  }) {
    return TextField(
      controller: controller,
      obscureText: secret,
      decoration: InputDecoration(
        labelText: label,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }
}
