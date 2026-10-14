import 'package:shared_preferences/shared_preferences.dart';

class AgentSettings {
  AgentSettings({
    this.apiKey = '',
    this.baseUrl = 'https://api.openai.com/v1',
    this.model = 'gpt-4o-mini',
  });

  String apiKey;
  String baseUrl;
  String model;

  bool get hasKey => apiKey.trim().isNotEmpty;

  static const _key = 'agent_api_key';
  static const _url = 'agent_base_url';
  static const _model = 'agent_model';

  static Future<AgentSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    return AgentSettings(
      apiKey: prefs.getString(_key) ?? '',
      baseUrl: prefs.getString(_url) ?? 'https://api.openai.com/v1',
      model: prefs.getString(_model) ?? 'gpt-4o-mini',
    );
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, apiKey.trim());
    await prefs.setString(_url, baseUrl.trim());
    await prefs.setString(_model, model.trim());
  }
}
