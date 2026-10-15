import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/store.dart';
import '../format.dart';
import '../models/models.dart';
import '../theme.dart';

class Wordmark extends StatelessWidget {
  const Wordmark({super.key, this.size = 22});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Text.rich(
      TextSpan(
        style: TextStyle(
          fontSize: size,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
          color: C.ink,
          height: 1,
        ),
        children: const [
          TextSpan(text: 'договорились'),
          TextSpan(
            text: '.',
            style: TextStyle(color: C.red),
          ),
        ],
      ),
    );
  }
}

class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key, this.trailing});

  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12, top: 4),
      child: Row(
        children: [
          Text(text, style: T.section),
          if (trailing != null) ...[const Spacer(), trailing!],
        ],
      ),
    );
  }
}

class Surface extends StatelessWidget {
  const Surface({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
    this.border,
    this.color,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;
  final Color? border;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(kRadius);
    final decoration = BoxDecoration(
      color: color ?? C.card,
      borderRadius: radius,
      boxShadow: C.cardShadow,
      border: border == null ? null : Border.all(color: border!),
    );
    if (onTap == null) {
      return DecoratedBox(
        decoration: decoration,
        child: Padding(padding: padding, child: child),
      );
    }
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: radius,
        child: Ink(decoration: decoration, padding: padding, child: child),
      ),
    );
  }
}

class SelectChip extends StatelessWidget {
  const SelectChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? C.red : C.card,
      borderRadius: BorderRadius.circular(999),
      elevation: selected ? 0 : 0,
      shadowColor: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            boxShadow: selected ? null : C.cardShadow,
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: selected ? Colors.white : C.ink,
            ),
          ),
        ),
      ),
    );
  }
}

class MetaChip extends StatelessWidget {
  const MetaChip(
    this.text, {
    super.key,
    required this.bg,
    required this.fg,
    this.border,
  });

  final String text;
  final Color bg;
  final Color fg;
  final Color? border;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
        border: border == null ? null : Border.all(color: border!),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: fg),
      ),
    );
  }
}

class CheckDot extends StatelessWidget {
  const CheckDot({
    super.key,
    required this.checked,
    required this.onTap,
    this.active = C.red,
  });

  final bool checked;
  final VoidCallback onTap;
  final Color active;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          width: 26,
          height: 26,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: checked ? active : Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: checked ? active : C.line, width: 1.5),
          ),
          child: checked
              ? const Icon(Icons.check_rounded, size: 16, color: Colors.white)
              : null,
        ),
      ),
    );
  }
}

class Monogram extends StatelessWidget {
  const Monogram({
    super.key,
    required this.name,
    required this.tone,
    this.size = 44,
  });

  final String name;
  final int tone;
  final double size;

  @override
  Widget build(BuildContext context) {
    final color = C.tones[tone.abs() % C.tones.length];
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Text(
        initials(name),
        style: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w700,
          fontSize: size * 0.34,
          letterSpacing: -0.4,
        ),
      ),
    );
  }
}

class SearchBox extends StatelessWidget {
  const SearchBox({
    super.key,
    required this.controller,
    required this.hint,
    required this.onChanged,
  });

  final TextEditingController controller;
  final String hint;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      decoration: BoxDecoration(
        color: C.card,
        borderRadius: BorderRadius.circular(16),
        boxShadow: C.cardShadow,
      ),
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w500,
          color: C.ink,
        ),
        decoration: InputDecoration(
          isDense: true,
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          hintText: hint,
          hintStyle: const TextStyle(
            color: C.mute,
            fontWeight: FontWeight.w400,
          ),
          prefixIcon: const Icon(Icons.search_rounded, color: C.mute, size: 20),
          prefixIconConstraints: const BoxConstraints(minWidth: 44),
          contentPadding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: onPressed == null ? 0.4 : 1,
      child: Material(
        color: C.red,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(16),
          child: SizedBox(
            height: 52,
            width: double.infinity,
            child: Center(
              child: Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class RoundIconButton extends StatelessWidget {
  const RoundIconButton({super.key, required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: C.card,
      shape: const CircleBorder(),
      shadowColor: C.shadow,
      elevation: 1,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: 40,
          height: 40,
          child: Icon(icon, size: 20, color: C.ink),
        ),
      ),
    );
  }
}

class SummaryCard extends StatelessWidget {
  const SummaryCard({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Surface(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome_rounded, size: 16, color: C.red),
              SizedBox(width: 6),
              Text(
                'Суть разговора',
                style: TextStyle(
                  color: C.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            text,
            style: const TextStyle(
              color: C.inkSoft,
              fontSize: 15,
              height: 1.4,
              fontWeight: FontWeight.w400,
            ),
          ),
        ],
      ),
    );
  }
}

class FactList extends StatelessWidget {
  const FactList({super.key, required this.facts});

  final List<String> facts;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < facts.length; i++)
          Padding(
            padding: EdgeInsets.only(top: i == 0 ? 0 : 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  margin: const EdgeInsets.only(top: 6),
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: C.red,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    facts[i],
                    style: const TextStyle(
                      fontSize: 14.5,
                      height: 1.35,
                      fontWeight: FontWeight.w400,
                      color: C.inkSoft,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class CommitmentTile extends StatelessWidget {
  const CommitmentTile({
    super.key,
    required this.commitment,
    required this.clientName,
    required this.onToggle,
    this.onOpen,
    this.showClient = true,
    this.showQuote = false,
  });

  final Commitment commitment;
  final String clientName;
  final VoidCallback onToggle;
  final VoidCallback? onOpen;
  final bool showClient;
  final bool showQuote;

  @override
  Widget build(BuildContext context) {
    final c = commitment;
    final today = !c.isDone && c.dueDate != null && dayDiff(c.dueDate!) == 0;
    final (Color bg, Color fg) due = c.isDone
        ? (C.mossBg, C.moss)
        : c.isOverdue
        ? (C.blush, C.red)
        : today
        ? (C.sand, C.clay)
        : (C.chip, C.inkSoft);
    final ours = c.owner == CommitmentOwner.us;

    return Surface(
      onTap: onOpen,
      border: c.isOverdue ? C.redSoftBorder : null,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CheckDot(
            checked: c.isDone,
            active: c.isDone ? C.moss : C.red,
            onTap: onToggle,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(
                  c.text,
                  style: TextStyle(
                    fontSize: 15.5,
                    height: 1.35,
                    fontWeight: FontWeight.w600,
                    color: c.isDone ? C.mute : C.ink,
                    decoration: c.isDone ? TextDecoration.lineThrough : null,
                    decorationColor: C.mute,
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
                    if (showClient)
                      MetaChip(clientName, bg: C.chip, fg: C.inkSoft),
                    MetaChip(commitmentWhen(c), bg: due.$1, fg: due.$2),
                  ],
                ),
                if (showQuote && c.quote != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.only(left: 10),
                    decoration: const BoxDecoration(
                      border: Border(left: BorderSide(color: C.line, width: 2)),
                    ),
                    child: Text(
                      '«${c.quote}»',
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
    );
  }
}

class CallCard extends StatelessWidget {
  const CallCard({super.key, required this.call, required this.onTap});

  final CallRecord call;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final store = Store.of(context);
    final client = store.clientOf(call.clientId);
    if (client == null) return const SizedBox.shrink();
    final open = store
        .commitmentsOfCall(call.id)
        .where((c) => !c.isDone)
        .length;
    final overdue = store.commitmentsOfCall(call.id).any((c) => c.isOverdue);

    return Surface(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Monogram(name: client.name, tone: client.tone),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      client.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      ),
                    ),
                    if (client.company != null)
                      Text(
                        client.company!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 13,
                          color: C.mute,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                callWhen(call.createdAt),
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: C.mute,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            call.summary,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 14,
              height: 1.35,
              fontWeight: FontWeight.w400,
              color: C.inkSoft,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            open == 0
                ? '${durationLabel(call.durationSec)} · закрыто'
                : '${durationLabel(call.durationSec)} · ${countAgreements(open)}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: overdue ? C.red : C.mute,
            ),
          ),
        ],
      ),
    );
  }
}

class TranscriptView extends StatelessWidget {
  const TranscriptView({
    super.key,
    required this.turns,
    required this.theirName,
  });

  final List<Turn> turns;
  final String theirName;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxW = constraints.maxWidth * 0.86;
        return Column(
          children: [
            for (var i = 0; i < turns.length; i++)
              _bubble(
                turns[i],
                maxW,
                showLabel: i == 0 || turns[i].ours != turns[i - 1].ours,
              ),
          ],
        );
      },
    );
  }

  Widget _bubble(Turn turn, double maxW, {required bool showLabel}) {
    final ours = turn.ours;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: ours
            ? CrossAxisAlignment.end
            : CrossAxisAlignment.start,
        children: [
          if (showLabel)
            Padding(
              padding: const EdgeInsets.only(bottom: 4, left: 4, right: 4),
              child: Text(ours ? 'Мы' : theirName, style: T.label),
            ),
          Align(
            alignment: ours ? Alignment.centerRight : Alignment.centerLeft,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxW),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: ours ? C.red : C.card,
                  borderRadius: BorderRadius.only(
                    topLeft: const Radius.circular(18),
                    topRight: const Radius.circular(18),
                    bottomLeft: Radius.circular(ours ? 18 : 6),
                    bottomRight: Radius.circular(ours ? 6 : 18),
                  ),
                  boxShadow: ours ? null : C.cardShadow,
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  child: Text(
                    turn.text,
                    style: TextStyle(
                      color: ours ? Colors.white : C.ink,
                      fontSize: 14.5,
                      height: 1.35,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
