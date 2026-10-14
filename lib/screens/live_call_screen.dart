import 'dart:async';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/agent_settings.dart';
import '../data/call_agent.dart';
import '../data/store.dart';
import '../data/summarize.dart';
import '../format.dart';
import '../theme.dart';
import 'call_screen.dart';

enum _Step { voice, sampling, ready, ringing, talking }

const _capture = RecordConfig(
  encoder: AudioEncoder.aacLc,
  bitRate: 128000,
  sampleRate: 44100,
  numChannels: 1,
  echoCancel: false,
  autoGain: false,
  noiseSuppress: false,
  iosConfig: IosRecordConfig(
    categoryOptions: [
      IosAudioCategoryOption.defaultToSpeaker,
      IosAudioCategoryOption.mixWithOthers,
    ],
    allowHapticsAndSystemSoundsDuringRecording: true,
  ),
);

class LiveCallScreen extends StatefulWidget {
  const LiveCallScreen({super.key, required this.clientId});

  final String clientId;

  @override
  State<LiveCallScreen> createState() => _LiveCallScreenState();
}

class _LiveCallScreenState extends State<LiveCallScreen> {
  final _recorder = AudioRecorder();
  Timer? _ticker;
  Timer? _sampleTicker;
  _Step _step = _Step.voice;
  int _seconds = 0;
  int _sampleLeft = 5;
  String? _voicePath;
  String? _audioPath;
  String? _error;
  bool _busy = false;
  String _busyLabel = 'Определяю спикеров…';

  @override
  void dispose() {
    _ticker?.cancel();
    _sampleTicker?.cancel();
    _recorder.stop();
    super.dispose();
  }

  Future<String?> _startFile(String name) async {
    if (await _recorder.isRecording()) await _recorder.stop();
    if (!await _recorder.hasPermission()) {
      setState(() => _error = 'Нет доступа к микрофону.');
      return null;
    }
    final dir = await getTemporaryDirectory();
    final path =
        '${dir.path}/${name}_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(_capture, path: path);
    return path;
  }

  Future<void> _captureVoice() async {
    setState(() {
      _error = null;
      _step = _Step.sampling;
      _sampleLeft = 5;
    });
    try {
      final path = await _startFile('voice');
      if (path == null) {
        setState(() => _step = _Step.voice);
        return;
      }
      _sampleTicker?.cancel();
      _sampleTicker = Timer.periodic(const Duration(seconds: 1), (timer) async {
        if (!mounted) return;
        if (_sampleLeft <= 1) {
          timer.cancel();
          final saved = await _recorder.stop();
          if (!mounted) return;
          setState(() {
            _voicePath = saved ?? path;
            _step = _Step.ready;
          });
          return;
        }
        setState(() => _sampleLeft -= 1);
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Не удалось записать голос: $error';
        _step = _Step.voice;
      });
    }
  }

  Future<void> _dial() async {
    final client = Store.of(context).clientOf(widget.clientId);
    final phone = client?.phone;
    if (phone == null || phone.trim().isEmpty) {
      setState(() => _error = 'У этого человека нет номера.');
      return;
    }
    final digits = phone.replaceAll(RegExp(r'[^\d+]'), '');
    setState(() => _step = _Step.ringing);
    await launchUrl(Uri.parse('tel:$digits'));
  }

  Future<void> _answered() async {
    setState(() => _error = null);
    try {
      final path = await _startFile('call');
      if (path == null) return;
      _audioPath = path;
      _seconds = 0;
      _ticker?.cancel();
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() => _seconds++);
      });
      setState(() => _step = _Step.talking);
    } catch (error) {
      setState(() => _error = 'Не удалось начать запись звонка: $error');
    }
  }

  Future<String?> _stopRecording() async {
    try {
      if (await _recorder.isRecording()) return await _recorder.stop();
    } catch (_) {}
    return _audioPath;
  }

  Future<void> _finish() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _busyLabel = 'Определяю спикеров…';
    });
    _ticker?.cancel();
    final audioPath = await _stopRecording();
    if (!mounted) return;
    final store = Store.of(context);
    final client = store.clientOf(widget.clientId);
    if (client == null) {
      Navigator.of(context).pop();
      return;
    }
    final settings = await AgentSettings.load();
    if (!mounted) return;
    TalkSummary talk;
    if (settings.hasKey && audioFileUsable(audioPath)) {
      try {
        talk = await CallAgent(settings).analyzeRecording(
          audioPath: audioPath!,
          clientName: client.name,
          liveTranscript: '',
          voiceReferencePath: _voicePath,
        );
      } on Exception catch (error) {
        talk = summarizeTalk('');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Не удалось разделить голоса: $error')),
          );
        }
      }
    } else {
      talk = const TalkSummary(
        summary: 'Нет записи звонка или ключа агента. Нажмите «Он ответил», когда возьмут трубку, и укажите ключ в настройках.',
        turns: [],
        drafts: [],
      );
    }
    if (!mounted) return;
    final saved = store.save(
      clientName: client.name,
      company: client.company ?? '',
      phone: client.phone ?? '',
      summary: talk.summary,
      facts: talk.facts,
      turns: talk.turns,
      durationSec: _seconds,
      drafts: talk.drafts,
    );
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => CallScreen(callId: saved.id)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final client = Store.of(context).clientOf(widget.clientId);
    return Scaffold(
      backgroundColor: const Color(0xFFF2F3F7),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              IconButton(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.close_rounded),
              ),
              Text(client?.name ?? 'Звонок', style: T.title),
              const SizedBox(height: 8),
              Text(
                _status,
                style: const TextStyle(
                  color: C.mute,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                _hint,
                style: const TextStyle(height: 1.4, color: C.inkSoft),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: C.red)),
              ],
              const Spacer(),
              if (_step == _Step.talking)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text(
                    clock(_seconds),
                    style: const TextStyle(
                      fontSize: 48,
                      fontWeight: FontWeight.w700,
                      fontFeatures: [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
              _actions(),
            ],
          ),
        ),
      ),
    );
  }

  String get _status => switch (_step) {
    _Step.voice => 'Шаг 1. Ваш голос',
    _Step.sampling => 'Говорите… $_sampleLeft',
    _Step.ready => 'Шаг 2. Звонок',
    _Step.ringing => 'Шаг 3. Когда ответят',
    _Step.talking => 'Идёт запись разговора',
  };

  String get _hint => switch (_step) {
    _Step.voice || _Step.sampling => 'Скажите спокойно: «Это мой голос, я буду говорить с клиентом». Эти 5 секунд нужны, чтобы отличить вас от собеседника.',
    _Step.ready => 'Образец сохранён. Позвоните и включите громкую связь. Запись начнётся, когда нажмёте «Он ответил».',
    _Step.ringing => 'Не начинайте запись на гудках. Нажмите «Он ответил», как только человек возьмёт трубку, и говорите по громкой связи.',
    _Step.talking => 'Микрофон пишет оба голоса без шумоподавления. После звонка спикеры определятся по записи.',
  };

  Widget _actions() {
    if (_busy) {
      return SizedBox(
        width: double.infinity,
        height: 52,
        child: FilledButton(onPressed: null, child: Text(_busyLabel)),
      );
    }
    return switch (_step) {
      _Step.voice => _button('Записать мой голос', _captureVoice),
      _Step.sampling => const SizedBox(
        width: double.infinity,
        height: 52,
        child: FilledButton(onPressed: null, child: Text('Слушаю ваш голос…')),
      ),
      _Step.ready => _button('Позвонить', _dial),
      _Step.ringing => _button('Он ответил', _answered),
      _Step.talking => _button('Звонок закончился', _finish),
    };
  }

  Widget _button(String label, VoidCallback onPressed, {Color color = C.red}) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: color,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        onPressed: onPressed,
        child: Text(label),
      ),
    );
  }
}
