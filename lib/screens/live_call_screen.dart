import 'dart:async';

import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/store.dart';
import '../data/summarize.dart';
import '../format.dart';
import '../theme.dart';
import 'call_screen.dart';

class LiveCallScreen extends StatefulWidget {
  const LiveCallScreen({super.key, required this.clientId});

  final String clientId;

  @override
  State<LiveCallScreen> createState() => _LiveCallScreenState();
}

class _LiveCallScreenState extends State<LiveCallScreen> {
  final _speech = SpeechToText();
  Timer? _ticker;
  int _seconds = 0;
  String _committed = '';
  String _partial = '';
  String? _error;
  bool _busy = false;
  bool _callStarted = false;

  String get _transcript => '$_committed $_partial'.trim();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _begin());
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _speech.stop();
    super.dispose();
  }

  Future<void> _begin() async {
    final store = Store.of(context);
    final client = store.clientOf(widget.clientId);
    final phone = client?.phone;
    if (phone == null || phone.trim().isEmpty) {
      setState(() => _error = 'У этого человека нет номера.');
      return;
    }
    final digits = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final ready = await _speech.initialize(
      onStatus: _onStatus,
      onError: (error) {
        if (!mounted) return;
        setState(() => _error = error.errorMsg);
      },
    );
    if (!mounted) return;
    if (!ready) {
      setState(
        () => _error = 'Нет доступа к микрофону или распознаванию речи.',
      );
      return;
    }
    await _listen();
    await launchUrl(Uri.parse('tel:$digits'));
  }

  void _startClock() {
    if (_callStarted || _busy) return;
    _callStarted = true;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _seconds++);
    });
  }

  Future<void> _listen() async {
    if (!mounted || _busy || _speech.isListening) return;
    await _speech.listen(
      onResult: (result) {
        if (!mounted) return;
        setState(() {
          if (result.recognizedWords.trim().isNotEmpty) _startClock();
          if (result.finalResult) {
            final words = result.recognizedWords.trim();
            if (words.isNotEmpty) {
              _committed = '$_committed $words'.trim();
            }
            _partial = '';
          } else {
            _partial = result.recognizedWords;
          }
        });
      },
      listenOptions: SpeechListenOptions(
        listenFor: const Duration(minutes: 2),
        pauseFor: const Duration(seconds: 8),
        localeId: 'ru_RU',
        listenMode: ListenMode.dictation,
        partialResults: true,
      ),
    );
  }

  void _onStatus(String status) {
    if (!mounted || _busy || _error != null) return;
    if (status != 'done' && status != 'notListening') return;
    Future<void>.delayed(const Duration(milliseconds: 400), () {
      if (mounted && !_busy) _listen();
    });
  }

  Future<void> _finish() async {
    if (_busy) return;
    setState(() => _busy = true);
    _ticker?.cancel();
    await _speech.stop();
    if (!mounted) return;
    final store = Store.of(context);
    final client = store.clientOf(widget.clientId);
    if (client == null) {
      Navigator.of(context).pop();
      return;
    }
    final talk = summarizeTalk(_transcript);
    final saved = store.save(
      clientName: client.name,
      company: client.company ?? '',
      phone: client.phone ?? '',
      summary: talk.summary,
      facts: const [],
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
    final store = Store.of(context);
    final client = store.clientOf(widget.clientId);
    final heard = _transcript;

    return Scaffold(
      backgroundColor: const Color(0xFFF2F3F7),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close_rounded),
                  ),
                  const Spacer(),
                  Text(
                    clock(_seconds),
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: _callStarted ? C.ink : C.mute,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(client?.name ?? 'Звонок', style: T.title),
              const SizedBox(height: 6),
              Text(
                _callStarted
                    ? 'Разговор идёт'
                    : 'Жду начала звонка — таймер ещё не идёт',
                style: const TextStyle(
                  color: C.mute,
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (!_callStarted) ...[
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => setState(_startClock),
                  child: const Text('Разговор начался'),
                ),
              ],
              const SizedBox(height: 12),
              const Text(
                'Включите громкую связь. Телефон слышит обоих и после звонка соберёт саммари в историю с этим человеком.',
                style: TextStyle(height: 1.35, color: C.inkSoft),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: C.red)),
              ],
              const SizedBox(height: 16),
              Expanded(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: SingleChildScrollView(
                    child: Text(
                      heard.isEmpty
                          ? 'Здесь появится текст, как только начнёте говорить.'
                          : heard,
                      style: TextStyle(
                        height: 1.4,
                        fontSize: 16,
                        color: heard.isEmpty ? C.mute : C.ink,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: C.red,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  onPressed: _busy ? null : _finish,
                  child: Text(_busy ? 'Собираю саммари…' : 'Звонок закончился'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
