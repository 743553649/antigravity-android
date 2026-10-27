package com.agy.ui.splash;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Environment;
import android.widget.Toast;

import com.agy.core.CoreRuntimeState;
import com.agy.runtime.RuntimeConfig;
import com.agy.util.SensitiveDataRedactor;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.Charset;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;

/** Collects diagnostics and core logs for user export and debugging. */
public final class LogExporter {

    private static final Charset UTF8 = Charset.forName("UTF-8");
    private static final int MAX_LOG_BYTES = 300_000;

    private LogExporter() {
    }

    public static String collectDiagnostics(Context context) {
        StringBuilder sb = new StringBuilder();
        sb.append("=== Antigravity 运行诊断日志 ===\n");
        sb.append("记录时间: ").append(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date())).append("\n");
        String verName = RuntimeConfig.APP_VERSION_NAME;
        long verCode = RuntimeConfig.APP_VERSION_CODE;
        if (context != null) {
            try {
                android.content.pm.PackageInfo pi = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
                verName = pi.versionName;
                verCode = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? pi.getLongVersionCode() : pi.versionCode;
            } catch (Exception ignored) {
            }
        }
        sb.append("应用版本: ").append(verName).append(" (版本号 ").append(verCode).append(")\n");
        sb.append("设备型号: ").append(Build.MANUFACTURER).append(" ").append(Build.MODEL)
                .append(" (").append(Build.DEVICE).append(")\n");
        sb.append("系统版本: Android ").append(Build.VERSION.RELEASE)
                .append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        sb.append("CPU架构: ").append(Arrays.toString(Build.SUPPORTED_ABIS)).append("\n");
        sb.append("最近错误: ").append(CoreRuntimeState.lastError != null
                ? SensitiveDataRedactor.redactLine(CoreRuntimeState.lastError) : "无").append("\n");
        sb.append("服务地址: ").append(CoreRuntimeState.serverUrl != null
                ? SensitiveDataRedactor.safeUrl(CoreRuntimeState.serverUrl) : "无").append("\n");
        sb.append("\n=== 核心运行日志 (files/logs/core.log) ===\n");

        if (context == null) {
            sb.append("(无法定位应用文件目录)\n");
            return sb.toString();
        }

        File logFile = new File(context.getFilesDir(), "logs/core.log");
        if (!logFile.exists() || logFile.length() == 0) {
            sb.append("(核心日志文件为空或不存在)\n");
        } else {
            try {
                long len = logFile.length();
                long skipBytes = Math.max(0, len - MAX_LOG_BYTES);
                try (FileInputStream fis = new FileInputStream(logFile)) {
                    if (skipBytes > 0) {
                        long skipped = fis.skip(skipBytes);
                        sb.append("... [日志已截断 ").append(skipped).append(" 字节；显示末尾 ")
                                .append(len - skipped).append(" 字节，共 ").append(len).append(" 字节] ...\n");
                    }
                    try (BufferedReader reader = new BufferedReader(new InputStreamReader(fis, UTF8))) {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            sb.append(SensitiveDataRedactor.redactLine(line)).append("\n");
                        }
                    }
                }
            } catch (Exception e) {
                sb.append("读取日志文件失败: ").append(e.getMessage()).append("\n");
            }
        }
        return sb.toString();
    }

    public static void copyToClipboard(Context context) {
        if (context == null) {
            return;
        }
        try {
            String report = collectDiagnostics(context);
            ClipboardManager cm = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) {
                ClipData clip = ClipData.newPlainText("Antigravity 运行日志", report);
                cm.setPrimaryClip(clip);
                Toast.makeText(context, "日志已复制到剪贴板", Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) {
            Toast.makeText(context, "复制日志失败: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    public static void saveAndShare(Context context) {
        if (context == null) {
            return;
        }
        try {
            String report = collectDiagnostics(context);
            File savedFile = null;

            File downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (downloadsDir != null && (downloadsDir.exists() || downloadsDir.mkdirs())) {
                File target = new File(downloadsDir, "antigravity-core.log");
                try (OutputStreamWriter writer = new OutputStreamWriter(new FileOutputStream(target), UTF8)) {
                    writer.write(report);
                    savedFile = target;
                } catch (Exception ignored) {
                }
            }

            if (savedFile == null) {
                File direct = new File(Environment.getExternalStorageDirectory(), "Download/antigravity-core.log");
                try (OutputStreamWriter writer = new OutputStreamWriter(new FileOutputStream(direct), UTF8)) {
                    writer.write(report);
                    savedFile = direct;
                } catch (Exception ignored) {
                }
            }

            if (savedFile == null) {
                File appExternal = context.getExternalFilesDir(null);
                if (appExternal != null && (appExternal.exists() || appExternal.mkdirs())) {
                    File target = new File(appExternal, "antigravity-core.log");
                    try (OutputStreamWriter writer = new OutputStreamWriter(new FileOutputStream(target), UTF8)) {
                        writer.write(report);
                        savedFile = target;
                    } catch (Exception ignored) {
                    }
                }
            }

            if (savedFile != null) {
                Toast.makeText(context, "日志已保存至: " + savedFile.getAbsolutePath(), Toast.LENGTH_LONG).show();
            } else {
                Toast.makeText(context, "无法将日志写入下载目录", Toast.LENGTH_SHORT).show();
            }

            Intent sendIntent = new Intent(Intent.ACTION_SEND);
            sendIntent.setType("text/plain");
            sendIntent.putExtra(Intent.EXTRA_SUBJECT, "Antigravity 运行日志");
            if (report.length() < MAX_LOG_BYTES) {
                sendIntent.putExtra(Intent.EXTRA_TEXT, report);
            }
            sendIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            Intent chooser = Intent.createChooser(sendIntent, "分享日志");
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(chooser);
        } catch (Exception e) {
            Toast.makeText(context, "导出日志失败: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }
}
