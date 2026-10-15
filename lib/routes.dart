import 'package:flutter/material.dart';

import 'screens/call_screen.dart';
import 'screens/client_screen.dart';

void openCall(BuildContext context, String callId) {
  Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => CallScreen(callId: callId)));
}

void openClient(BuildContext context, String clientId) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(builder: (_) => ClientScreen(clientId: clientId)),
  );
}
