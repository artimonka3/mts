import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/demo.dart';
import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../theme.dart';
import '../widgets/common.dart';

enum _Phase { idle, recording, processing, review }

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen>
    with SingleTickerProviderStateMixin {
  _Phase phase = _Phase.idle;
  int seconds = 0;
  int step = 0;
  bool showScript = false;
  DemoScript? script;
  List<bool> picked = [];
  Timer? _tick;
  late final AnimationController _wave;

  static const _steps = [
    'Расшифровка речи',
    'Договорённости и сроки',
    'Карточка клиента',
  ];

  @override
  void initState() {
    super.initState();
    _wave = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
  }

  @override
  void dispose() {
    _tick?.cancel();
    _wave.dispose();
    super.dispose();
  }

  void _start() {
    HapticFeedback.mediumImpact();
    setState(() {
      phase = _Phase.recording;
      seconds = 0;
    });
    _wave.repeat();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => seconds++);
    });
  }

  void _cancelRec() {
    _tick?.cancel();
    _wave.stop();
    setState(() {
      phase = _Phase.idle;
      seconds = 0;
    });
  }

  void _stop() {
    HapticFeedback.mediumImpact();
    _tick?.cancel();
    _wave.stop();
    _process();
  }

  Future<void> _process() async {
    setState(() {
      phase = _Phase.processing;
      step = 0;
    });
    for (var i = 1; i <= 3; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 650));
      if (!mounted) return;
      setState(() => step = i);
    }
    await Future<void>.delayed(const Duration(milliseconds: 280));
    if (!mounted) return;
    final demo = demoScript();
    setState(() {
      script = demo;
      picked = List<bool>.filled(demo.drafts.length, true);
      showScript = false;
      phase = _Phase.review;
    });
  }

  void _close() {
    if (phase == _Phase.recording) {
      _cancelRec();
      return;
    }
    Navigator.of(context).pop();
  }

  void _save() {
    final demo = script;
    if (demo == null) return;
    final drafts = <CommitmentDraft>[
      for (var i = 0; i < demo.drafts.length; i++)
        if (picked[i]) demo.drafts[i],
    ];
    Store.of(context).save(
      clientName: demo.clientName,
      company: demo.company,
      phone: demo.phone,
      summary: demo.summary,
      facts: demo.facts,
      turns: demo.turns,
      durationSec: demo.durationSec,
      drafts: drafts,
    );
    HapticFeedback.mediumImpact();
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final canPop = phase == _Phase.idle || phase == _Phase.review;
    return PopScope(
      canPop: canPop,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && phase == _Phase.recording) _cancelRec();
      },
      child: Scaffold(
        body: SafeArea(child: phase == _Phase.review ? _review() : _stage()),
      ),
    );
  }

  Widget _top(String eyebrow) {
    final canClose = phase != _Phase.processing;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 20, 0),
      child: Row(
        children: [
          if (canClose)
            RoundIconButton(
              icon: phase == _Phase.recording
                  ? Icons.arrow_back_rounded
                  : Icons.close_rounded,
              onTap: _close,
            )
          else
            const SizedBox(width: 40, height: 40),
          const SizedBox(width: 12),
          Text(
            eyebrow,
            style: T.label.copyWith(
              color: phase == _Phase.recording ? C.red : C.mute,
            ),
          ),
        ],
      ),
    );
  }

  Widget _stage() {
    return Column(
      children: [
        _top(switch (phase) {
          _Phase.recording => 'ИДЁТ ЗАПИСЬ',
          _Phase.processing => 'РАЗБИРАЕМ',
          _ => 'ГРОМКАЯ СВЯЗЬ',
        }),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight - 36,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (phase == _Phase.idle) ..._idle(),
                      if (phase == _Phase.recording) ..._recording(),
                      if (phase == _Phase.processing) ..._processing(),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  List<Widget> _idle() {
    return [
      const Text(
        'Запишите разговор',
        textAlign: TextAlign.center,
        style: T.title,
      ),
      const SizedBox(height: 10),
      ConstrainedBox(
        constraints: BoxConstraints(maxWidth: 320),
        child: Text(
          'Договорённости, сроки и факты о клиенте соберутся в карточку.',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 15,
            height: 1.4,
            fontWeight: FontWeight.w500,
            color: C.mute,
          ),
        ),
      ),
      const SizedBox(height: 28),
      _halo(
        onTap: _start,
        child: const Icon(Icons.mic_rounded, color: Colors.white, size: 40),
      ),
      const SizedBox(height: 18),
      const Text(
        'Начать запись',
        style: TextStyle(fontWeight: FontWeight.w700, color: C.ink),
      ),
      const SizedBox(height: 28),
      ConstrainedBox(
        constraints: BoxConstraints(maxWidth: 280),
        child: Text(
          'Демонстрация: после остановки покажем разбор готового разговора.',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 13,
            height: 1.35,
            fontWeight: FontWeight.w500,
            color: C.mute,
          ),
        ),
      ),
    ];
  }

  List<Widget> _recording() {
    return [
      Text(
        clock(seconds),
        style: const TextStyle(
          fontSize: 64,
          fontWeight: FontWeight.w700,
          letterSpacing: -2,
          height: 1,
          color: C.ink,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
      const SizedBox(height: 8),
      const Text(
        'Говорите как обычно',
        style: TextStyle(color: C.mute, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 28),
      AnimatedBuilder(
        animation: _wave,
        builder: (_, _) => _Wave(t: _wave.value),
      ),
      const SizedBox(height: 28),
      _halo(
        onTap: _stop,
        color: C.ink,
        child: const Icon(Icons.stop_rounded, color: Colors.white, size: 36),
      ),
      const SizedBox(height: 18),
      const Text(
        'Остановить',
        style: TextStyle(fontWeight: FontWeight.w700, color: C.ink),
      ),
    ];
  }

  List<Widget> _processing() {
    return [
      const Text('Секунду', textAlign: TextAlign.center, style: T.title),
      const SizedBox(height: 8),
      const Text(
        'Собираем то, о чём договорились',
        style: TextStyle(color: C.mute, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 22),
      Surface(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: Column(
          children: [for (var i = 0; i < _steps.length; i++) _stepRow(i)],
        ),
      ),
    ];
  }

  Widget _stepRow(int index) {
    final done = step > index;
    final active = step == index;
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          _mark(done: done, active: active),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _steps[index],
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: done || active ? C.ink : C.mute,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _mark({required bool done, required bool active}) {
    if (active) {
      return const SizedBox(
        width: 22,
        height: 22,
        child: Padding(
          padding: EdgeInsets.all(2),
          child: CircularProgressIndicator(strokeWidth: 2, color: C.red),
        ),
      );
    }
    return Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: done ? C.moss : Colors.white,
        shape: BoxShape.circle,
        border: Border.all(color: done ? C.moss : C.line, width: 1.5),
      ),
      child: done
          ? const Icon(Icons.check_rounded, size: 14, color: Colors.white)
          : null,
    );
  }

  Widget _halo({
    required VoidCallback onTap,
    required Widget child,
    Color color = C.red,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: SizedBox(
        width: 220,
        height: 220,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: 220,
              height: 220,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: C.blush.withValues(alpha: 0.55),
              ),
            ),
            Container(
              width: 164,
              height: 164,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: C.blush,
              ),
            ),
            Container(
              width: 104,
              height: 104,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(34),
              ),
              child: child,
            ),
          ],
        ),
      ),
    );
  }

  Widget _review() {
    final demo = script!;
    final selected = picked.where((e) => e).length;
    return Column(
      children: [
        _top('ПРОВЕРКА'),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(kPage, 8, kPage, 16),
            children: [
              const Text('Проверьте', style: T.title),
              const SizedBox(height: 6),
              Text(
                'Сохраним только отмеченное · ${durationLabel(demo.durationSec)}',
                style: const TextStyle(
                  color: C.mute,
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 18),
              Surface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Monogram(name: demo.clientName, tone: 4, size: 48),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                demo.clientName,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              Text(
                                demo.company,
                                style: const TextStyle(
                                  color: C.mute,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              Text(
                                demo.phone,
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: C.inkSoft,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    FactList(facts: demo.facts),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              SummaryCard(text: demo.summary),
              const SizedBox(height: 22),
              SectionLabel('Отмечено $selected из ${demo.drafts.length}'),
              for (var i = 0; i < demo.drafts.length; i++) ...[
                _draft(demo.drafts[i], i),
                const SizedBox(height: 10),
              ],
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: () => setState(() => showScript = !showScript),
                  child: Text(
                    showScript ? 'Скрыть расшифровку' : 'Показать расшифровку',
                  ),
                ),
              ),
              if (showScript)
                TranscriptView(
                  turns: demo.turns,
                  theirName: firstName(demo.clientName),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(kPage, 4, kPage, 12),
          child: PrimaryButton(
            label: selected == 0 ? 'Сохранить звонок' : 'Сохранить · $selected',
            onPressed: _save,
          ),
        ),
      ],
    );
  }

  Widget _draft(CommitmentDraft draft, int index) {
    final on = picked[index];
    final ours = draft.owner == CommitmentOwner.us;
    return Opacity(
      opacity: on ? 1 : 0.45,
      child: Surface(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CheckDot(
              checked: on,
              onTap: () => setState(() => picked[index] = !picked[index]),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 4),
                  Text(
                    draft.text,
                    style: const TextStyle(
                      fontSize: 15.5,
                      height: 1.35,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      MetaChip(
                        ours ? 'Мы' : 'Клиент',
                        bg: ours ? C.redSoft : C.chip,
                        fg: ours ? C.red : C.inkSoft,
                      ),
                      MetaChip(
                        draft.dueText ?? dueLabel(draft.dueDate),
                        bg: C.sand,
                        fg: C.clay,
                      ),
                    ],
                  ),
                  if (draft.quote != null) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.only(left: 10),
                      decoration: const BoxDecoration(
                        border: Border(
                          left: BorderSide(color: C.line, width: 2),
                        ),
                      ),
                      child: Text(
                        '«${draft.quote}»',
                        style: const TextStyle(
                          fontSize: 13,
                          height: 1.35,
                          color: C.mute,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Wave extends StatelessWidget {
  const _Wave({required this.t});

  final double t;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          for (var i = 0; i < 22; i++)
            Container(
              width: 3,
              height: 8 + 36 * ((math.sin(t * math.pi * 2 + i * 0.55) + 1) / 2),
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                color: C.red.withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
        ],
      ),
    );
  }
}
