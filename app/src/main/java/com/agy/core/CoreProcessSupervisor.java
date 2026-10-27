package com.agy.core;

import android.content.Context;
import android.text.TextUtils;
import android.util.Log;

import com.agy.runtime.RuntimeManager;
import com.agy.util.CoreUrl;
import com.agy.util.ErrorText;
import com.agy.util.ProcessUtils;
import com.agy.util.SensitiveDataRedactor;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.Writer;

/**
 * Supervises the core for its whole life. One pass = install, launch, wait for
 * ready, then block until exit. Intentional stops end the loop; an unexpected
 * exit is auto-restarted with exponential backoff up to MAX_RESTARTS, the
 * budget refilling after SUSTAINED_READY_MS of uptime.
 */
public final class CoreProcessSupervisor {

    private static final String TAG = "CoreProcessSupervisor";

    private final Context appContext;
    private final RuntimeManager runtime;
    private final OpenUrlWatcher openUrlWatcher;
    private final com.agy.log.LogRingBuffer logBuffer;
    private final Runnable terminalListener;

    private volatile Process process;
    private volatile boolean stopping = false;
    private Thread worker;

    public CoreProcessSupervisor(Context context, RuntimeManager runtime,
                                 OpenUrlWatcher openUrlWatcher,
                                 com.agy.log.LogRingBuffer logBuffer,
                                 Runnable terminalListener) {
        this.appContext = context.getApplicationContext();
        this.runtime = runtime;
        this.openUrlWatcher = openUrlWatcher;
        this.logBuffer = logBuffer;
        this.terminalListener = terminalListener;
    }

    public void start() {
        stopping = false;
        worker = new Thread(this::runCore, "CoreServerThread");
        worker.start();
    }

    public void stop() {
        stopping = true;
        destroy(process);
        if (worker != null) {
            worker.interrupt();
        }
    }

    private void runCore() {
        try {
            runCoreLoop();
        } finally {
            if (!stopping && terminalListener != null) {
                try {
                    terminalListener.run();
                } catch (Exception e) {
                    Log.w(TAG, "terminal callback failed", e);
                }
            }
        }
    }

    private void runCoreLoop() {
        int attempt = 0;
        while (!stopping) {
            Writer log = CoreLogWriter.open(appContext.getFilesDir());
            try {
                CoreRuntimeState.lastError = null;
                CoreRuntimeState.restarting = false;
                Process proc = CoreLauncher.launch(runtime, appContext.getFilesDir());
                process = proc;

                final Writer streamWriter = log;
                Thread streamer = new Thread(() -> streamLog(proc, streamWriter), "CoreStreamThread");
                streamer.setDaemon(true);
                streamer.start();

                if (!waitForReady(proc, log)) {
                    if (stopping) {
                        break;
                    }
                    // Ready timeout / launch death is fatal: no blind auto-restart.
                    if (CoreRuntimeState.lastError == null) {
                        CoreRuntimeState.lastError =
                                "核心服务在 " + (CoreReadyProbe.READY_TIMEOUT_MS / 1000) + " 秒内未就绪";
                        CoreLogWriter.writeLine(log, CoreRuntimeState.lastError);
                    }
                    destroy(proc);
                    break;
                }

                long readyAt = System.currentTimeMillis();
                try {
                    proc.waitFor();
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
                if (stopping) {
                    break;
                }

                int code = ProcessUtils.exitCode(proc);
                if (System.currentTimeMillis() - readyAt >= CoreRestartPolicy.SUSTAINED_READY_MS) {
                    attempt = 0;
                }
                CoreRuntimeState.serverUrl = null;
                attempt++;
                String tail = getLastLinesFromLog(appContext.getFilesDir(), 15);
                if (attempt > CoreRestartPolicy.MAX_RESTARTS) {
                    CoreRuntimeState.restarting = false;
                    CoreRuntimeState.lastError = "核心服务连续崩溃超过 " + CoreRestartPolicy.MAX_RESTARTS
                            + " 次，已停止重启 (最后退出码 " + code + ")"
                            + (tail.isEmpty() ? "" : "\n--- 核心日志摘要 (core.log tail) ---\n" + tail);
                    CoreLogWriter.writeLine(log, CoreRuntimeState.lastError);
                    com.agy.log.CrashRecorder.recordCrash(appContext, code, System.currentTimeMillis() - readyAt, CoreRuntimeState.lastError, logBuffer);
                    break;
                }
                long delay = CoreRestartPolicy.delayFor(attempt);
                CoreRuntimeState.restarting = true;
                CoreRuntimeState.lastError = "核心服务异常退出 (退出码 " + code
                        + ")；将在 " + (delay / 1000) + " 秒后自动重启 (第 "
                        + attempt + "/" + CoreRestartPolicy.MAX_RESTARTS + " 次尝试)"
                        + (tail.isEmpty() ? "" : "\n--- 核心日志摘要 (core.log tail) ---\n" + tail);
                Log.w(TAG, CoreRuntimeState.lastError);
                CoreLogWriter.writeLine(log, CoreRuntimeState.lastError);
                com.agy.log.CrashRecorder.recordCrash(appContext, code, System.currentTimeMillis() - readyAt, CoreRuntimeState.lastError, logBuffer);
                CoreLogWriter.closeQuietly(log);
                log = null;
                sleepInterruptible(delay);
            } catch (Exception e) {
                if (stopping) {
                    break;
                }
                Log.e(TAG, "core start failed", e);
                CoreRuntimeState.lastError = ErrorText.describe(e);
                CoreLogWriter.writeLine(log, "核心服务启动失败: " + CoreRuntimeState.lastError);
                // install/launch failure: fail-closed, user retries from the splash.
                break;
            } finally {
                CoreLogWriter.closeQuietly(log);
            }
        }
    }

    private boolean waitForReady(Process proc, Writer log) {
        long start = System.currentTimeMillis();
        String csrf = runtime.getCsrfToken();
        int port = CoreRuntimeState.httpsPort;
        while (System.currentTimeMillis() - start < CoreReadyProbe.READY_TIMEOUT_MS) {
            if (stopping) {
                return false;
            }
            if (!ProcessUtils.isAlive(proc)) {
                int code = ProcessUtils.exitCode(proc);
                ProcessUtils.sleep(200);
                String lastLogs = getLastLinesFromLog(appContext.getFilesDir(), 10);
                CoreRuntimeState.lastError = "核心服务进程在就绪前异常退出 (退出码 " + code + ")"
                        + (lastLogs.isEmpty() ? "" : "\n--- 核心日志摘要 (core.log tail) ---\n" + lastLogs);
                CoreLogWriter.writeLine(log, CoreRuntimeState.lastError);
                return false;
            }
            if (CoreReadyProbe.probeOnce(appContext, port)) {
                CoreRuntimeState.serverUrl = CoreUrl.startUrl(port, csrf);
                CoreRuntimeState.lastError = null;
                CoreRuntimeState.restarting = false;
                CoreRuntimeState.readyGeneration++;
                String readyStatus = "core ready on 127.0.0.1:" + port;
                Log.i(TAG, readyStatus);
                CoreLogWriter.writeLine(log, readyStatus);
                return true;
            }
        }
        return false;
    }

    private void streamLog(Process proc, Writer log) {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(proc.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String safeLine = SensitiveDataRedactor.redactLine(line);
                Log.d(TAG, safeLine);
                if (logBuffer != null) {
                    logBuffer.appendLine(safeLine);
                }
                CoreLogWriter.writeLine(log, safeLine);
                openUrlWatcher.handleStreamLine(line);
            }
        } catch (Exception e) {
            Log.w(TAG, "log stream ended", e);
        }
    }

    private void sleepInterruptible(long ms) {
        long end = System.currentTimeMillis() + ms;
        while (!stopping) {
            long left = end - System.currentTimeMillis();
            if (left <= 0) {
                return;
            }
            ProcessUtils.sleep(Math.min(left, 250));
        }
    }

    private static void destroy(Process proc) {
        if (proc != null) {
            try {
                proc.destroy();
            } catch (Exception ignored) {
            }
            try {
                proc.destroyForcibly();
            } catch (Exception ignored) {
            }
        }
        CoreLauncher.killOrphanCoreProcesses();
    }

    private static String getLastLinesFromLog(java.io.File filesDir, int maxLines) {
        java.io.File logFile = new java.io.File(filesDir, "logs/core.log");
        if (!logFile.isFile()) {
            return "";
        }
        java.util.List<String> lines = new java.util.ArrayList<>();
        try (BufferedReader br = new BufferedReader(new java.io.FileReader(logFile))) {
            String l;
            while ((l = br.readLine()) != null) {
                lines.add(SensitiveDataRedactor.redactLine(l));
                if (lines.size() > maxLines) {
                    lines.remove(0);
                }
            }
        } catch (Exception ignored) {
        }
        return TextUtils.join("\n", lines);
    }
}
