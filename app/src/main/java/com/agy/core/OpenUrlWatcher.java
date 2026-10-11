package com.agy.core;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.agy.oauth.OAuthManager;
import com.agy.ui.MainActivity;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The core execs core/tools/xdg-open, but swallows its stdout, so the
 * "AGY_OPEN_URL=" line never reaches the stdout bridge. The shim broadcasts
 * ACTION_OPEN_URL and appends to fallback files: tail them for new URLs.
 */
public final class OpenUrlWatcher {

    private static final String TAG = "OpenUrlWatcher";
    private static final String OPEN_URL_PREFIX = "AGY_OPEN_URL=";
    /** Fallback channel written by core/tools/xdg-open (append-only). */
    private static final String OPEN_URL_FILE = "agy-open-url";
    private static final long OPEN_URL_POLL_MS = 80;
    private static final Pattern URL_PATTERN =
            Pattern.compile("https?://[\\w\\-\\.\\~:\\?\\#\\[\\]\\@\\!\\$\\&\\'\\(\\)\\*\\+,;=%/]+");

    private final Context appContext;
    private final OAuthManager oauth = new OAuthManager();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private volatile boolean stopping;
    private volatile String lastDispatchedUrl = "";
    private volatile long lastDispatchedTime = 0;
    private Thread watcher;

    private final BroadcastReceiver openUrlReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null) return;
            String url = intent.getStringExtra("url");
            if (url != null && !url.trim().isEmpty()) {
                Log.i(TAG, "broadcast ACTION_OPEN_URL received: " + url);
                dispatchIfValid(url);
            }
        }
    };

    public OpenUrlWatcher(Context context) {
        this.appContext = context.getApplicationContext();
    }

    /** Cleans up stale files and starts the daemon tail thread. */
    public void start() {
        try {
            IntentFilter filter = new IntentFilter("com.agy.ACTION_OPEN_URL");
            if (Build.VERSION.SDK_INT >= 33) {
                appContext.registerReceiver(openUrlReceiver, filter, Context.RECEIVER_EXPORTED);
            } else {
                appContext.registerReceiver(openUrlReceiver, filter);
            }
            Log.i(TAG, "registered ACTION_OPEN_URL receiver");
        } catch (Throwable t) {
            Log.w(TAG, "failed to register ACTION_OPEN_URL receiver: " + t.getMessage());
        }

        for (File f : candidateFiles()) {
            if (f.isFile()) {
                f.delete();
            }
        }
        Log.i(TAG, "open-url watcher started");
        watcher = new Thread(this::watchFile, "CoreOpenUrlWatch");
        watcher.setDaemon(true);
        watcher.start();
    }

    public void stop() {
        stopping = true;
        try {
            appContext.unregisterReceiver(openUrlReceiver);
        } catch (Throwable ignored) {
        }
    }

    /** Detects the stdout OPEN_URL prefix or logged auth URLs; called by the stream reader. */
    public void handleStreamLine(String line) {
        if (line == null) {
            return;
        }
        int at = line.indexOf(OPEN_URL_PREFIX);
        if (at >= 0) {
            String url = line.substring(at + OPEN_URL_PREFIX.length()).trim();
            dispatchIfValid(url);
            return;
        }
        // Fallback: detect OAuth or login URLs emitted by language_server / openBrowser
        if (line.contains("accounts.google.com") || line.contains("oauth2")
                || (line.contains("/auth/callback") && line.contains("http"))) {
            Matcher m = URL_PATTERN.matcher(line);
            while (m.find()) {
                String candidate = m.group();
                if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
                    if (candidate.contains("accounts.google.com") || candidate.contains("oauth2")
                            || candidate.contains("auth")) {
                        Log.i(TAG, "stream regex detected auth URL: " + candidate);
                        dispatchIfValid(candidate);
                    }
                }
            }
        }
    }

    public void dispatchIfValid(String url) {
        if (url == null) return;
        url = url.trim();
        if (url.isEmpty()) return;
        long now = System.currentTimeMillis();
        if (url.equals(lastDispatchedUrl) && (now - lastDispatchedTime) < 1500) {
            return;
        }
        lastDispatchedUrl = url;
        lastDispatchedTime = now;
        Log.i(TAG, "dispatching external URL: " + url);
        openUrl(url);
    }

    private List<File> candidateFiles() {
        Set<String> seen = new HashSet<>();
        List<File> files = new ArrayList<>();
        File cache = appContext.getCacheDir();
        if (cache != null) {
            addCandidate(files, seen, new File(cache, OPEN_URL_FILE));
        }
        File fDir = appContext.getFilesDir();
        if (fDir != null) {
            addCandidate(files, seen, new File(fDir, OPEN_URL_FILE));
        }
        File extCache = appContext.getExternalCacheDir();
        if (extCache != null) {
            addCandidate(files, seen, new File(extCache, OPEN_URL_FILE));
        }
        String pkg = appContext.getPackageName();
        addCandidate(files, seen, new File("/data/user/0/" + pkg + "/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/" + pkg + "/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/user/0/" + pkg + "/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/" + pkg + "/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/user/0/com.agy/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/com.agy/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/user/0/com.agy/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/com.agy/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/user/0/com.agy.dev/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/com.agy.dev/cache", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/user/0/com.agy.dev/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/data/com.agy.dev/files", OPEN_URL_FILE));
        addCandidate(files, seen, new File("/data/local/tmp", OPEN_URL_FILE));
        return files;
    }

    private static void addCandidate(List<File> files, Set<String> seen, File f) {
        if (f != null && seen.add(f.getAbsolutePath())) {
            files.add(f);
        }
    }

    /** Polls the fallback files and consumes URLs appended by the opener shim. */
    private void watchFile() {
        while (!stopping) {
            for (File file : candidateFiles()) {
                if (!file.isFile() || file.length() == 0) {
                    continue;
                }
                List<String> lines = new ArrayList<>();
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                        new FileInputStream(file), Charset.forName("UTF-8")))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        line = line.trim();
                        if (!line.isEmpty()) {
                            lines.add(line);
                        }
                    }
                } catch (Exception e) {
                    Log.w(TAG, "cannot read " + file, e);
                }
                // Immediately consume / clear the file so subsequent requests are seen
                file.delete();

                for (String url : lines) {
                    dispatchIfValid(url);
                }
            }
            sleep(OPEN_URL_POLL_MS);
        }
    }

    /**
     * The core shells out to core/tools/xdg-open, whose shim prints
     * "AGY_OPEN_URL=<url>" to stdout. The core process runs as the app UID, so
     * `am` is unavailable: this bridge fires the ACTION_VIEW intent on the main
     * thread instead.
     */
    private void openUrl(final String url) {
        if (url == null || url.trim().isEmpty()) {
            return;
        }
        Log.i(TAG, "open-url -> external browser: " + url);
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                Context target = (MainActivity.activeActivity != null)
                        ? MainActivity.activeActivity
                        : appContext;
                boolean opened = oauth.openInBrowser(target, url);
                if (!opened) {
                    Log.w(TAG, "no browser accepted the url: " + url);
                }
            }
        });
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
