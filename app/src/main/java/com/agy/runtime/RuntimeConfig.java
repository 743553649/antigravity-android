package com.agy.runtime;

import android.content.Context;

import com.agy.BuildConfig;

/** App-level constants sourced from the generated BuildConfig. */
public final class RuntimeConfig {

    public static final int DEFAULT_HTTPS_PORT = BuildConfig.PORT;
    public static final String CORE_VERSION = BuildConfig.CORE_VERSION;
    public static final String APP_VERSION_NAME = BuildConfig.APP_VERSION_NAME;
    public static final int APP_VERSION_CODE = BuildConfig.APP_VERSION_CODE;
    public static final int MIN_API = BuildConfig.MIN_API;
    public static final int TARGET_SDK = BuildConfig.TARGET_SDK;
    public static final boolean DEBUG = BuildConfig.DEBUG;

    private static volatile int cachedHttpsPort = -1;

    private RuntimeConfig() {
    }

    /** The port from res/values/gen.xml, else the BuildConfig default; auto-avoids occupied ports. */
    public static synchronized int httpsPort(Context appContext) {
        if (cachedHttpsPort > 0) {
            return cachedHttpsPort;
        }
        int basePort = DEFAULT_HTTPS_PORT;
        if (appContext != null) {
            try {
                int resId = appContext.getResources().getIdentifier(
                        "https_server_port", "integer", appContext.getPackageName());
                if (resId != 0) {
                    basePort = appContext.getResources().getInteger(resId);
                }
            } catch (Exception ignored) {
            }
        }
        cachedHttpsPort = findAvailablePort(basePort);
        return cachedHttpsPort;
    }

    private static int findAvailablePort(int startPort) {
        for (int p = startPort; p < startPort + 50; p++) {
            if (isPortAvailable(p)) {
                return p;
            }
        }
        return startPort;
    }

    private static boolean isPortAvailable(int port) {
        try (java.net.ServerSocket ss = new java.net.ServerSocket()) {
            ss.setReuseAddress(true);
            ss.bind(new java.net.InetSocketAddress("127.0.0.1", port));
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
