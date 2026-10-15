import 'package:shared_preferences/shared_preferences.dart';

class AgentSettings {
  AgentSettings({
    this.apiKey = '',
    this.baseUrl = 'https://api.openai.com/v1',
    this.model = 'gpt-4o-mini',
    this.serverUrl = defaultServer,
    this.sessionCookie = '',
    this.csrfToken = '',
  });

  String apiKey;
  String baseUrl;
  String model;
  String serverUrl;
  String sessionCookie;
  String csrfToken;

  static const defaultServer = 'http://10.65.158.39:8000';
  static const demoLogin = 'demo';
  static const demoPassword = 'dogovor-demo';

  bool get hasKey => apiKey.trim().isNotEmpty;
  bool get hasSession =>
      sessionCookie.trim().isNotEmpty && serverUrl.trim().isNotEmpty;

  static const _key = 'agent_api_key';
  static const _url = 'agent_base_url';
  static const _model = 'agent_model';
  static const _server = 'backend_server_url';
  static const _cookie = 'backend_session';
  static const _csrf = 'backend_csrf';

  static Future<AgentSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    return AgentSettings(
      apiKey: prefs.getString(_key) ?? '',
      baseUrl: prefs.getString(_url) ?? 'https://api.openai.com/v1',
      model: prefs.getString(_model) ?? 'gpt-4o-mini',
      serverUrl: _serverUrl(prefs.getString(_server)),
      sessionCookie: prefs.getString(_cookie) ?? '',
      csrfToken: prefs.getString(_csrf) ?? '',
    );
  }

  static String _serverUrl(String? saved) {
    if (saved == null || saved.isEmpty || saved.contains('127.0.0.1')) {
      return defaultServer;
    }
    return saved;
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, apiKey.trim());
    await prefs.setString(_url, baseUrl.trim());
    await prefs.setString(_model, model.trim());
    await prefs.setString(_server, serverUrl.trim());
    await prefs.setString(_cookie, sessionCookie.trim());
    await prefs.setString(_csrf, csrfToken.trim());
  }
}
