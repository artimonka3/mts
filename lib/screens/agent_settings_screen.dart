import 'package:flutter/material.dart';

import '../data/agent_settings.dart';
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
  bool _ready = false;
  bool _saving = false;

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
    setState(() => _ready = true);
  }

  @override
  void dispose() {
    _key.dispose();
    _url.dispose();
    _model.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final previous = await AgentSettings.load();
    await AgentSettings(
      apiKey: _key.text,
      baseUrl: _url.text.isEmpty ? 'https://api.openai.com/v1' : _url.text,
      model: _model.text.isEmpty ? 'gpt-4o-mini' : _model.text,
      serverUrl: previous.serverUrl,
      sessionCookie: previous.sessionCookie,
      csrfToken: previous.csrfToken,
    ).save();
    if (!mounted) return;
    Navigator.of(context).pop();
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
