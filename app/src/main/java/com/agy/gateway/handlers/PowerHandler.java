package com.agy.gateway.handlers;

import android.content.Context;
import android.os.PowerManager;
import android.util.Log;

import org.json.JSONObject;

import java.util.concurrent.ConcurrentHashMap;

/**
 * Manages tagged Android Partial WakeLocks for long-running autonomous tasks.
 */
public final class PowerHandler {

    private static final String TAG = "PowerHandler";
    private final Context context;
    private final PowerManager powerManager;
    private final ConcurrentHashMap<String, PowerManager.WakeLock> locks = new ConcurrentHashMap<>();

    public PowerHandler(Context context) {
        this.context = context.getApplicationContext();
        this.powerManager = (PowerManager) this.context.getSystemService(Context.POWER_SERVICE);
    }

    public JSONObject handle(JSONObject payload) {
        JSONObject resp = new JSONObject();
        try {
            String action = payload.optString("action", "acquire");
            String tag = payload.optString("tag", "agy_task");
            long timeoutMs = payload.optLong("timeout_ms", 0);

            if (powerManager == null) {
                resp.put("ok", false);
                resp.put("error", "PowerManager unavailable");
                return resp;
            }

            if ("release".equalsIgnoreCase(action)) {
                PowerManager.WakeLock lock = locks.remove(tag);
                if (lock != null && lock.isHeld()) {
                    lock.release();
                    Log.d(TAG, "Released wakelock: " + tag);
                }
                resp.put("ok", true);
                resp.put("held", false);
                return resp;
            }

            // Acquire
            PowerManager.WakeLock lock = locks.computeIfAbsent(tag, k ->
                    powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "com.agy:wakelock:" + k));

            if (!lock.isHeld()) {
                if (timeoutMs > 0) {
                    lock.acquire(timeoutMs);
                } else {
                    lock.acquire();
                }
                Log.d(TAG, "Acquired wakelock: " + tag + (timeoutMs > 0 ? " timeout=" + timeoutMs + "ms" : ""));
            }

            resp.put("ok", true);
            resp.put("held", lock.isHeld());
            resp.put("tag", tag);
        } catch (Exception e) {
            Log.w(TAG, "wakelock error: " + e.getMessage());
            try {
                resp.put("ok", false);
                resp.put("error", e.getMessage());
            } catch (Exception ignored) {}
        }
        return resp;
    }

    public void releaseAll() {
        for (String tag : locks.keySet()) {
            PowerManager.WakeLock lock = locks.remove(tag);
            if (lock != null && lock.isHeld()) {
                try {
                    lock.release();
                } catch (Exception ignored) {}
            }
        }
    }
}
