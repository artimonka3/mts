import 'package:flutter/material.dart';

import '../data/ask.dart';
import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../routes.dart';
import '../theme.dart';

class CallScreen extends StatefulWidget {
  const CallScreen({super.key, required this.callId});

  final String callId;

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  bool _thinking = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _greet());
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _greet() {
    final store = Store.of(context);
    if (store.chatOf(widget.callId).isNotEmpty) return;
    final call = _call(store);
    final client = call == null ? null : store.clientOf(call.clientId);
    final name = client?.name ?? 'клиентом';
    store.addChat(
      widget.callId,
      ChatMessage(
        fromUser: false,
        text:
            'Разобрала звонок с $name. ${call?.summary ?? ''}\n\nСпросите, о чём говорили, какие сроки и кто что обещал.',
      ),
    );
  }

  CallRecord? _call(Store store) {
    for (final c in store.calls) {
      if (c.id == widget.callId) return c;
    }
    return null;
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _thinking) return;
    final store = Store.of(context);
    final call = _call(store);
    if (call == null) return;
    _input.clear();
    store.addChat(widget.callId, ChatMessage(fromUser: true, text: text));
    setState(() => _thinking = true);
    _jump();
    await Future<void>.delayed(const Duration(milliseconds: 700));
    if (!mounted) return;
    final reply = answerAbout(
      call: call,
      client: store.clientOf(call.clientId),
      items: store.commitmentsOfCall(call.id),
      question: text,
    );
    store.addChat(widget.callId, ChatMessage(fromUser: false, text: reply));
    setState(() => _thinking = false);
    _jump();
  }

  void _jump() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final call = _call(store);
    if (call == null) return const Scaffold(body: SizedBox.shrink());
    final client = store.clientOf(call.clientId);
    final messages = store.chatOf(call.id);
    final missed = call.direction == CallDirection.missed;
    final incoming = call.direction != CallDirection.outgoing;

    return Scaffold(
      backgroundColor: const Color(0xFFF2F3F7),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 6, 16, 8),
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(
                      Icons.arrow_back_ios_new_rounded,
                      size: 20,
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          client?.name ?? 'Звонок',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: missed ? const Color(0xFFFF3B30) : C.ink,
                          ),
                        ),
                        Text(
                          '${incoming ? 'Входящий' : 'Исходящий'} · ${recentsWhen(call.createdAt)} · ${durationLabel(call.durationSec)}',
                          style: const TextStyle(fontSize: 12, color: C.mute),
                        ),
                        if (client != null)
                          GestureDetector(
                            onTap: () => openClient(context, client.id),
                            child: const Padding(
                              padding: EdgeInsets.only(top: 2),
                              child: Text(
                                'История разговоров',
                                style: TextStyle(
                                  color: C.red,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                controller: _scroll,
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                children: [
                  _transcript(call, client?.name ?? 'Клиент'),
                  const SizedBox(height: 16),
                  const Text(
                    'Спросите про звонок',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 10),
                  for (final m in messages) ...[
                    _bubble(m),
                    const SizedBox(height: 8),
                  ],
                  if (_thinking)
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: Padding(
                        padding: EdgeInsets.only(left: 4, bottom: 8),
                        child: Text(
                          'печатает…',
                          style: TextStyle(color: C.mute, fontSize: 13),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: InputDecoration(
                        hintText: 'Что обещали? Какие сроки?',
                        filled: true,
                        fillColor: Colors.white,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(22),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Material(
                    color: C.red,
                    shape: const CircleBorder(),
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: _send,
                      child: const SizedBox(
                        width: 44,
                        height: 44,
                        child: Icon(
                          Icons.arrow_upward_rounded,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _transcript(CallRecord call, String name) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'О чём говорили',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          ),
          const SizedBox(height: 8),
          Text(
            call.summary,
            style: const TextStyle(height: 1.35, color: C.inkSoft),
          ),
          const SizedBox(height: 12),
          for (final turn in call.turns) ...[
            Text(
              turn.label ?? (turn.ours ? 'Мы' : name),
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: C.mute,
              ),
            ),
            const SizedBox(height: 2),
            Text(turn.text, style: const TextStyle(height: 1.35)),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _bubble(ChatMessage message) {
    final mine = message.fromUser;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 300),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: mine ? C.red : Colors.white,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Text(
              message.text,
              style: TextStyle(
                color: mine ? Colors.white : C.ink,
                height: 1.35,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
