import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'data/store.dart';
import 'screens/shell.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      statusBarBrightness: Brightness.light,
    ),
  );
  runApp(const DogovorApp());
}

class DogovorApp extends StatefulWidget {
  const DogovorApp({super.key});

  @override
  State<DogovorApp> createState() => _DogovorAppState();
}

class _DogovorAppState extends State<DogovorApp> {
  final store = Store();

  @override
  Widget build(BuildContext context) {
    return StoreScope(
      store: store,
      child: MaterialApp(
        title: 'Договорились',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: C.paper,
          canvasColor: C.paper,
          colorScheme: const ColorScheme.light(
            primary: C.red,
            onPrimary: Colors.white,
            surface: C.card,
            onSurface: C.ink,
            secondary: C.red,
            onSecondary: Colors.white,
          ),
          splashColor: const Color(0x14E30613),
          highlightColor: Colors.transparent,
          dividerColor: C.line,
          iconTheme: const IconThemeData(color: C.ink),
          appBarTheme: const AppBarTheme(
            backgroundColor: C.paper,
            foregroundColor: C.ink,
            elevation: 0,
            scrolledUnderElevation: 0,
          ),
          textSelectionTheme: const TextSelectionThemeData(
            cursorColor: C.red,
            selectionColor: C.redSoft,
            selectionHandleColor: C.red,
          ),
          textButtonTheme: TextButtonThemeData(
            style: TextButton.styleFrom(
              foregroundColor: C.red,
              textStyle: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 15,
              ),
            ),
          ),
          snackBarTheme: const SnackBarThemeData(
            behavior: SnackBarBehavior.floating,
            backgroundColor: C.ink,
            elevation: 0,
            contentTextStyle: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w500,
              fontSize: 14,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.all(Radius.circular(14)),
            ),
          ),
          textTheme: const TextTheme(bodyMedium: T.body, bodyLarge: T.body),
        ),
        home: const Shell(),
      ),
    );
  }
}
