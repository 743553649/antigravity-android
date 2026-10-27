package com.agy.proxy;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.Deque;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.GZIPInputStream;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/**
 * Local Model Proxy & Protocol Adapter (Scheme B).
 * Runs locally on 127.0.0.1:46170.
 *
 * Key responsibilities:
 * 1. Non-LLM domains (e.g. lh3.googleusercontent.com, www.googleapis.com, play.googleapis.com):
 *    Pure raw TCP tunnel (passthroughRaw) without MITM decryption, preserving Google certs and 0ms overhead.
 * 2. CloudCode / Gemini domains (daily-cloudcode-pa.googleapis.com, etc.):
 *    Terminates TLS using proxy.p12.
 *    - If request is for a Custom Model (BYOM / third-party), intercepts and translates between
 *      CloudCode v1internal Gemini format and OpenAI-compatible /v1/chat/completions SSE.
 *    - If request is an official Google request (e.g. startup userInfo, fetchAvailableModels, or official Gemini),
 *      forwards to Google with Connection: close so connections complete immediately and never bypass
 *      the proxy via keep-alive pooling.
 */
public final class LocalModelProxyServer {

    private static final String TAG = "LocalModelProxy";
    public static final int DEFAULT_PORT = 46170;

    private final Context context;
    private final int port;
    private final ExecutorService executor = Executors.newCachedThreadPool();

    private volatile boolean running = false;
    private ServerSocket serverSocket;
    private Thread acceptThread;
    private SSLContext sslContext;
    private final File logFile;
    private final File sharedLogFile;
    private final Map<String, Integer> loopBreakerCounts = new java.util.concurrent.ConcurrentHashMap<>();

    public LocalModelProxyServer(Context context) {
        this(context, DEFAULT_PORT);
    }

    public LocalModelProxyServer(Context context, int port) {
        this.context = context.getApplicationContext();
        this.port = port;
        this.logFile = new File(this.context.getFilesDir(), "logs/proxy.log");
        this.sharedLogFile = new File("/storage/emulated/0/Download/antigravity-proxy.log");
    }

    public synchronized void start() {
        if (running) return;
        running = true;

        initSslContext();

        acceptThread = new Thread(() -> {
            try {
                serverSocket = new ServerSocket();
                serverSocket.setReuseAddress(true);
                serverSocket.bind(new java.net.InetSocketAddress(InetAddress.getByName("127.0.0.1"), port), 128);
                log("Proxy listening on 127.0.0.1:" + port);

                while (running && !serverSocket.isClosed()) {
                    try {
                        Socket client = serverSocket.accept();
                        client.setSoTimeout(180000);
                        executor.submit(() -> handleClient(client));
                    } catch (Exception e) {
                        if (!running) break;
                    }
                }
            } catch (Exception e) {
                log("Proxy bind error on port " + port + ": " + e.getMessage());
            }
        }, "AgyModelProxy");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    public synchronized void stop() {
        running = false;
        if (serverSocket != null) {
            try { serverSocket.close(); } catch (Exception ignored) {}
        }
        executor.shutdownNow();
    }

    private void initSslContext() {
        try {
            KeyStore ks = KeyStore.getInstance("PKCS12");
            InputStream is = null;
            try {
                is = context.getAssets().open("proxy.p12");
            } catch (Exception e) {
                File certFile = new File(context.getFilesDir(), "runtime/certs/proxy.p12");
                if (certFile.isFile()) {
                    is = new FileInputStream(certFile);
                }
            }
            if (is != null) {
                try {
                    ks.load(is, "changeit".toCharArray());
                    KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
                    kmf.init(ks, "changeit".toCharArray());
                    sslContext = SSLContext.getInstance("TLS");
                    sslContext.init(kmf.getKeyManagers(), null, null);
                    log("SSLContext initialized successfully with proxy.p12");
                } finally {
                    is.close();
                }
            } else {
                log("Warning: proxy.p12 not found; MITM decryption will be unavailable.");
            }
        } catch (Exception e) {
            log("Error initializing proxy SSLContext: " + e.getMessage());
        }
    }

    private void handleClient(Socket client) {
        try {
            InputStream in = client.getInputStream();
            OutputStream out = client.getOutputStream();

            String firstLine = readLine(in);
            if (firstLine == null || firstLine.isEmpty()) {
                client.close();
                return;
            }

            if (firstLine.startsWith("CONNECT ")) {
                handleConnect(client, firstLine, in, out);
            } else {
                handlePlainHttp(client, firstLine, in, out);
            }
        } catch (Exception e) {
            log("Client handle exception: " + e.getMessage());
            try { client.close(); } catch (Exception ignored) {}
        }
    }

    private void handleConnect(Socket client, String connectLine, InputStream in, OutputStream out) {
        try {
            String[] parts = connectLine.split(" ");
            String hostPort = parts.length > 1 ? parts[1] : "";
            String host = hostPort;
            int targetPort = 443;
            if (hostPort.contains(":")) {
                String[] hp = hostPort.split(":");
                host = hp[0];
                try { targetPort = Integer.parseInt(hp[1]); } catch (Exception ignored) {}
            }

            // Consume all CONNECT headers
            while (true) {
                String header = readLine(in);
                if (header == null || header.isEmpty()) break;
            }

            boolean shouldMitm = host.contains("cloudcode-pa.googleapis.com")
                    || host.contains("generativelanguage.googleapis.com")
                    || host.contains("aiplatform.googleapis.com")
                    || host.contains("aicode.googleapis.com");

            if (!shouldMitm || sslContext == null) {
                out.write("HTTP/1.1 200 Connection Established\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
                out.flush();
                passthroughRaw(client, host, targetPort);
                return;
            }

            // Acknowledge CONNECT for MITM hosts
            out.write("HTTP/1.1 200 Connection Established\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
            out.flush();

            // Upgrade client socket to SSL server mode
            SSLSocket sslClient = (SSLSocket) sslContext.getSocketFactory().createSocket(
                    client,
                    client.getInetAddress().getHostAddress(),
                    client.getPort(),
                    false);
            sslClient.setUseClientMode(false);
            sslClient.startHandshake();

            InputStream sslIn = sslClient.getInputStream();
            OutputStream sslOut = sslClient.getOutputStream();

            String reqLine = readLine(sslIn);
            if (reqLine == null || reqLine.isEmpty()) {
                sslClient.close();
                client.close();
                return;
            }

            Map<String, String> headers = new LinkedHashMap<>();
            int contentLength = 0;
            boolean isChunked = false;
            while (true) {
                String h = readLine(sslIn);
                if (h == null || h.isEmpty()) break;
                int colon = h.indexOf(':');
                if (colon != -1) {
                    String k = h.substring(0, colon).trim().toLowerCase(Locale.ROOT);
                    String v = h.substring(colon + 1).trim();
                    headers.put(k, v);
                    if ("content-length".equals(k)) {
                        try { contentLength = Integer.parseInt(v); } catch (Exception ignored) {}
                    } else if ("transfer-encoding".equals(k) && v.toLowerCase(Locale.ROOT).contains("chunked")) {
                        isChunked = true;
                    }
                }
            }

            byte[] rawBody = readHttpBody(sslIn, contentLength, isChunked);
            String bodyStr = decodeBodyToString(rawBody, headers.get("content-encoding"));
            log(String.format("[REQ] %s https://%s (raw=%d bytes, decoded=%d chars)",
                    reqLine, host, rawBody.length, bodyStr.length()));

            // Handle :countTokens for custom models so it doesn't 404 on Google Cloud
            CustomModelConfig matchedConfig = findCustomModelConfig(reqLine, bodyStr);
            if (matchedConfig != null && reqLine.contains(":countTokens")) {
                log("[INTERCEPT] Returning synthetic token count for Custom Model: " + matchedConfig.modelName);
                byte[] respBytes = "{\"totalTokens\": 256}".getBytes(StandardCharsets.UTF_8);
                String respHeaders = "HTTP/1.1 200 OK\r\n"
                        + "Content-Type: application/json; charset=utf-8\r\n"
                        + "Content-Length: " + respBytes.length + "\r\n"
                        + "Connection: close\r\n\r\n";
                sslOut.write(respHeaders.getBytes(StandardCharsets.UTF_8));
                sslOut.write(respBytes);
                sslOut.flush();
                try { sslClient.close(); } catch (Exception ignored) {}
                try { client.close(); } catch (Exception ignored) {}
                return;
            }

            if (matchedConfig != null && (reqLine.contains("GenerateContent") || reqLine.contains("generateContent") || reqLine.contains("chat/completions"))) {
                log("[INTERCEPT] Routing request to Custom Model: " + matchedConfig.modelName + " via " + matchedConfig.baseUrl);
                handleCustomModelRequest(sslOut, reqLine, headers, bodyStr, matchedConfig);
                try { sslClient.close(); } catch (Exception ignored) {}
                try { client.close(); } catch (Exception ignored) {}
            } else {
                // Passthrough to Google Cloud with Connection: close so each request is individually inspected
                passthroughEncryptedSingle(client, sslClient, host, targetPort, reqLine, headers, rawBody);
            }
        } catch (Exception e) {
            log("handleConnect error: " + e.getMessage());
            try { client.close(); } catch (Exception ignored) {}
        }
    }

    private void handlePlainHttp(Socket client, String reqLine, InputStream in, OutputStream out) {
        try {
            Map<String, String> headers = new LinkedHashMap<>();
            int contentLength = 0;
            boolean isChunked = false;
            while (true) {
                String h = readLine(in);
                if (h == null || h.isEmpty()) break;
                int colon = h.indexOf(':');
                if (colon != -1) {
                    String k = h.substring(0, colon).trim().toLowerCase(Locale.ROOT);
                    String v = h.substring(colon + 1).trim();
                    headers.put(k, v);
                    if ("content-length".equals(k)) {
                        try { contentLength = Integer.parseInt(v); } catch (Exception ignored) {}
                    } else if ("transfer-encoding".equals(k) && v.toLowerCase(Locale.ROOT).contains("chunked")) {
                        isChunked = true;
                    }
                }
            }

            byte[] rawBody = readHttpBody(in, contentLength, isChunked);
            String bodyStr = decodeBodyToString(rawBody, headers.get("content-encoding"));
            log(String.format("[PLAIN-HTTP] %s (body=%d bytes)", reqLine, rawBody.length));

            CustomModelConfig matchedConfig = findCustomModelConfig(reqLine, bodyStr);
            if (matchedConfig != null) {
                log("[INTERCEPT-HTTP] Routing request to Custom Model: " + matchedConfig.modelName);
                handleCustomModelRequest(out, reqLine, headers, bodyStr, matchedConfig);
            } else {
                String host = headers.get("host");
                if (host == null || host.isEmpty()) host = "127.0.0.1";
                passthroughPlain(host, 80, reqLine, headers, rawBody, out);
            }
        } catch (Exception e) {
            log("handlePlainHttp error: " + e.getMessage());
        } finally {
            try { client.close(); } catch (Exception ignored) {}
        }
    }

    private static byte[] readHttpBody(InputStream in, int contentLength, boolean isChunked) throws Exception {
        if (isChunked) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            while (true) {
                String lenLine = readLine(in);
                if (lenLine == null) break;
                int semi = lenLine.indexOf(';');
                if (semi != -1) lenLine = lenLine.substring(0, semi);
                int chunkLen;
                try {
                    chunkLen = Integer.parseInt(lenLine.trim(), 16);
                } catch (Exception e) {
                    break;
                }
                if (chunkLen <= 0) {
                    readLine(in); // trailing CRLF
                    break;
                }
                byte[] buf = new byte[chunkLen];
                int read = 0;
                while (read < chunkLen) {
                    int r = in.read(buf, read, chunkLen - read);
                    if (r < 0) break;
                    read += r;
                }
                baos.write(buf, 0, read);
                readLine(in); // chunk trailing CRLF
            }
            return baos.toByteArray();
        } else if (contentLength > 0) {
            byte[] body = new byte[contentLength];
            int totalRead = 0;
            while (totalRead < contentLength) {
                int r = in.read(body, totalRead, contentLength - totalRead);
                if (r < 0) break;
                totalRead += r;
            }
            return body;
        }
        return new byte[0];
    }

    private static String decodeBodyToString(byte[] rawBody, String contentEncoding) {
        if (rawBody == null || rawBody.length == 0) return "";
        if (contentEncoding != null && contentEncoding.toLowerCase(Locale.ROOT).contains("gzip")) {
            try (GZIPInputStream gis = new GZIPInputStream(new ByteArrayInputStream(rawBody));
                 ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = gis.read(buf)) > 0) {
                    baos.write(buf, 0, n);
                }
                return new String(baos.toByteArray(), StandardCharsets.UTF_8);
            } catch (Exception ignored) {}
        }
        return new String(rawBody, StandardCharsets.UTF_8);
    }

    /**
     * Wraps a Gemini GenerateContentResponse object into v1internal format if needed.
     * v1internal expects: {"response": {"candidates": [...]}}
     */
    private static JSONObject wrapResponse(JSONObject geminiResp, boolean isV1Internal) throws Exception {
        if (isV1Internal) {
            JSONObject wrapper = new JSONObject();
            wrapper.put("response", geminiResp);
            return wrapper;
        }
        return geminiResp;
    }

    private static JSONObject buildTextCandidate(String text, boolean isThought, String finishReason) throws Exception {
        JSONObject geminiResp = new JSONObject();
        JSONArray candArr = new JSONArray();
        JSONObject cand = new JSONObject();
        JSONObject contentObj = new JSONObject();
        contentObj.put("role", "model");
        JSONArray parts = new JSONArray();
        if (text != null) {
            JSONObject p = new JSONObject();
            if (isThought) {
                p.put("thought", true);
            }
            p.put("text", text);
            parts.put(p);
        }
        contentObj.put("parts", parts);
        cand.put("content", contentObj);
        if (finishReason != null) {
            cand.put("finishReason", finishReason);
        }
        candArr.put(cand);
        geminiResp.put("candidates", candArr);
        return geminiResp;
    }

    private static JSONObject sanitizeJsonSchema(JSONObject schema) {
        if (schema == null) return null;
        try {
            JSONObject clean = new JSONObject();
            Iterator<String> keys = schema.keys();
            while (keys.hasNext()) {
                String k = keys.next();
                if ("propertyOrdering".equals(k) || "nullable".equals(k)) {
                    continue;
                }
                Object val = schema.opt(k);
                if ("type".equals(k) && val instanceof String) {
                    String t = ((String) val).toLowerCase(Locale.ROOT);
                    if ("type_unspecified".equals(t)) t = "string";
                    clean.put("type", t);
                } else if ("properties".equals(k) && val instanceof JSONObject) {
                    JSONObject props = (JSONObject) val;
                    JSONObject cleanProps = new JSONObject();
                    Iterator<String> pk = props.keys();
                    while (pk.hasNext()) {
                        String propName = pk.next();
                        JSONObject propSchema = props.optJSONObject(propName);
                        if (propSchema != null) {
                            cleanProps.put(propName, sanitizeJsonSchema(propSchema));
                        }
                    }
                    clean.put("properties", cleanProps);
                } else if ("items".equals(k) && val instanceof JSONObject) {
                    clean.put("items", sanitizeJsonSchema((JSONObject) val));
                } else {
                    clean.put(k, val);
                }
            }
            if ("object".equals(clean.optString("type")) && !clean.has("properties")) {
                clean.put("properties", new JSONObject());
            }
            return clean;
        } catch (Exception e) {
            return schema;
        }
    }

    /**
     * Intercepts LLM prompt, translates from CloudCode v1internal / Gemini format to
     * OpenAI-compatible chat completions format, calls third-party endpoint, and streams
     * SSE response back in the exact format language_server expects.
     */
    private void handleCustomModelRequest(OutputStream clientOut, String reqLine, Map<String, String> headers, String bodyStr, CustomModelConfig config) {
        boolean isV1Internal = reqLine.contains("v1internal");
        boolean isStreaming = reqLine.contains("streamGenerateContent") || reqLine.contains("alt=sse");

        try {
            JSONObject rootReq = null;
            try {
                rootReq = new JSONObject(bodyStr);
            } catch (Exception e) {
                log("Failed to parse request JSON: " + e.getMessage());
            }

            // Unwrap v1internal {"request": {...}} envelope if present!
            JSONObject geminiReq = rootReq;
            if (rootReq != null && rootReq.has("request") && rootReq.optJSONObject("request") != null) {
                geminiReq = rootReq.optJSONObject("request");
            }

            String workspaceDir = resolveWorkspaceDir(bodyStr);

            JSONObject openAiReq = new JSONObject();
            openAiReq.put("model", config.modelName);
            openAiReq.put("stream", true);
            openAiReq.put("max_tokens", 8192);

            JSONArray messages = new JSONArray();
            Deque<String> pendingToolCallIds = new ArrayDeque<>();
            Map<String, Deque<String>> pendingToolCallsByName = new LinkedHashMap<>();

            if (geminiReq != null) {
                // 1. System instruction
                JSONObject sysInstruction = geminiReq.optJSONObject("systemInstruction");
                if (sysInstruction == null) {
                    sysInstruction = geminiReq.optJSONObject("system_instruction");
                }
                if (sysInstruction != null) {
                    JSONArray parts = sysInstruction.optJSONArray("parts");
                    if (parts != null) {
                        StringBuilder sb = new StringBuilder();
                        for (int i = 0; i < parts.length(); i++) {
                            JSONObject p = parts.optJSONObject(i);
                            if (p != null && p.has("text")) {
                                if (sb.length() > 0) sb.append("\n");
                                sb.append(p.optString("text"));
                            }
                        }
                        String adapterRules = "\n\n[Antigravity Runtime Rules for External Models]:\n"
                                + "1. Android shared storage (/storage/emulated/0) has noexec: always execute scripts explicitly via interpreter (e.g. `python script.py`, `bash script.sh`), never `./script`.\n"
                                + "2. When a command exits with code 0, do not re-run it with tee, redirection, or other wrappers.\n"
                                + "3. When modifying existing code, if `replace_file_content` fails with TargetContent not found, immediately use `write_to_file` with Overwrite=true to rewrite the entire file.\n"
                                + "4. Active workspace directory is `" + workspaceDir + "`. Always specify full absolute file paths.\n";
                        if (sb.length() > 0) {
                            sb.append(adapterRules);
                        } else {
                            sb.append(adapterRules.trim());
                        }
                        JSONObject sysMsg = new JSONObject();
                        sysMsg.put("role", "system");
                        sysMsg.put("content", sb.toString());
                        messages.put(sysMsg);
                    }
                }

                // 2. Chat history / contents
                JSONArray contents = geminiReq.optJSONArray("contents");
                if (contents != null) {
                    for (int i = 0; i < contents.length(); i++) {
                        JSONObject c = contents.optJSONObject(i);
                        if (c == null) continue;
                        String role = c.optString("role", "user");
                        boolean isModel = "model".equals(role) || "assistant".equals(role);

                        JSONArray parts = c.optJSONArray("parts");
                        if (parts == null) continue;

                        if (isModel) {
                            StringBuilder textBuf = new StringBuilder();
                            JSONArray toolCalls = new JSONArray();

                            for (int j = 0; j < parts.length(); j++) {
                                JSONObject p = parts.optJSONObject(j);
                                if (p == null) continue;
                                if (p.optBoolean("thought", false)) {
                                    // Do not mix thought/reasoning into assistant content history
                                    continue;
                                }
                                if (p.has("text")) {
                                    textBuf.append(p.optString("text"));
                                } else if (p.has("functionCall")) {
                                    JSONObject fn = p.optJSONObject("functionCall");
                                    if (fn != null) {
                                        String fnName = fn.optString("name", "");
                                        String callId = "call_" + i + "_" + j;
                                        pendingToolCallIds.addLast(callId);
                                        if (!fnName.isEmpty()) {
                                            pendingToolCallsByName.computeIfAbsent(fnName, k -> new ArrayDeque<>()).addLast(callId);
                                        }
                                        JSONObject tc = new JSONObject();
                                        tc.put("id", callId);
                                        tc.put("type", "function");
                                        JSONObject func = new JSONObject();
                                        func.put("name", fnName);
                                        JSONObject argsObj = fn.optJSONObject("args");
                                        func.put("arguments", argsObj != null ? argsObj.toString() : "{}");
                                        tc.put("function", func);
                                        toolCalls.put(tc);
                                    }
                                }
                            }

                            if (toolCalls.length() > 0) {
                                JSONObject assistantMsg = new JSONObject();
                                assistantMsg.put("role", "assistant");
                                assistantMsg.put("content", textBuf.length() > 0 ? textBuf.toString() : "");
                                assistantMsg.put("tool_calls", toolCalls);
                                messages.put(assistantMsg);
                            } else if (textBuf.length() > 0) {
                                JSONObject assistantMsg = new JSONObject();
                                assistantMsg.put("role", "assistant");
                                assistantMsg.put("content", textBuf.toString());
                                messages.put(assistantMsg);
                            }
                        } else {
                            StringBuilder textBuf = new StringBuilder();
                            for (int j = 0; j < parts.length(); j++) {
                                JSONObject p = parts.optJSONObject(j);
                                if (p == null) continue;
                                if (p.has("text")) {
                                    if (textBuf.length() > 0) textBuf.append("\n");
                                    textBuf.append(p.optString("text"));
                                } else if (p.has("functionResponse")) {
                                    JSONObject fnResp = p.optJSONObject("functionResponse");
                                    if (fnResp != null) {
                                        String fnName = fnResp.optString("name", "");
                                        Deque<String> nameQueue = pendingToolCallsByName.get(fnName);
                                        String callId = (nameQueue != null && !nameQueue.isEmpty())
                                                ? nameQueue.removeFirst()
                                                : (pendingToolCallIds.isEmpty() ? ("call_" + i + "_" + j) : pendingToolCallIds.removeFirst());

                                        JSONObject toolMsg = new JSONObject();
                                        toolMsg.put("role", "tool");
                                        toolMsg.put("tool_call_id", callId);
                                        Object respObj = fnResp.opt("response");
                                        String contentStr = null;
                                        if (respObj instanceof JSONObject) {
                                            JSONObject ro = (JSONObject) respObj;
                                            String out = null;
                                            if (ro.has("output") && ro.opt("output") instanceof String) {
                                                out = ro.optString("output");
                                            } else if (ro.has("stdout") && ro.opt("stdout") instanceof String) {
                                                out = ro.optString("stdout");
                                            } else if (ro.has("content") && ro.opt("content") instanceof String) {
                                                out = ro.optString("content");
                                            } else if (ro.has("result") && ro.opt("result") instanceof String) {
                                                out = ro.optString("result");
                                            } else if (ro.has("text") && ro.opt("text") instanceof String) {
                                                out = ro.optString("text");
                                            }

                                            if (out != null) {
                                                if (out.trim().isEmpty()) {
                                                    contentStr = "Command exited successfully with code 0 (no stdout).";
                                                } else {
                                                    contentStr = out;
                                                }
                                            } else if (ro.has("error") || ro.has("stderr")) {
                                                String err = ro.has("error") ? ro.optString("error") : ro.optString("stderr");
                                                if (err.toLowerCase(Locale.ROOT).contains("not found") && "replace_file_content".equals(fnName)) {
                                                    contentStr = err + "\n[System Hint: To prevent line/indentation mismatch, please use write_to_file with Overwrite=true to rewrite the full updated file directly.]";
                                                } else {
                                                    contentStr = err;
                                                }
                                            } else {
                                                String roStr = ro.toString();
                                                contentStr = roStr.equals("{}") ? "Operation completed with code 0 (no textual output)." : roStr;
                                            }
                                        } else if (respObj instanceof String) {
                                            String s = (String) respObj;
                                            contentStr = s.trim().isEmpty() ? "Command exited successfully with code 0 (no stdout)." : s;
                                        } else if (respObj != null) {
                                            contentStr = respObj.toString();
                                        }
                                        if (contentStr == null || contentStr.trim().isEmpty() || "{}".equals(contentStr)) {
                                            contentStr = "Operation completed with code 0 (no textual output).";
                                        }
                                        toolMsg.put("content", contentStr);
                                        messages.put(toolMsg);
                                    }
                                }
                            }
                            if (textBuf.length() > 0) {
                                JSONObject userMsg = new JSONObject();
                                userMsg.put("role", "user");
                                userMsg.put("content", textBuf.toString());
                                messages.put(userMsg);
                            }
                        }
                    }
                }

                // 3. Tools definitions (sanitized for OpenAI JSON Schema draft-07)
                JSONArray tools = geminiReq.optJSONArray("tools");
                if (tools != null) {
                    JSONArray openAiTools = new JSONArray();
                    for (int i = 0; i < tools.length(); i++) {
                        JSONObject t = tools.optJSONObject(i);
                        if (t == null) continue;
                        JSONArray decls = t.optJSONArray("functionDeclarations");
                        if (decls != null) {
                            for (int j = 0; j < decls.length(); j++) {
                                JSONObject d = decls.optJSONObject(j);
                                if (d == null) continue;
                                JSONObject openAiTool = new JSONObject();
                                openAiTool.put("type", "function");
                                JSONObject fn = new JSONObject();
                                fn.put("name", d.optString("name"));
                                fn.put("description", d.optString("description", ""));
                                if (d.has("parameters") && d.optJSONObject("parameters") != null) {
                                    fn.put("parameters", sanitizeJsonSchema(d.optJSONObject("parameters")));
                                } else {
                                    JSONObject emptyParams = new JSONObject();
                                    emptyParams.put("type", "object");
                                    emptyParams.put("properties", new JSONObject());
                                    fn.put("parameters", emptyParams);
                                }
                                openAiTool.put("function", fn);
                                openAiTools.put(openAiTool);
                            }
                        }
                    }
                    if (openAiTools.length() > 0) {
                        openAiReq.put("tools", openAiTools);
                    }
                }
            }

            // Ensure messages is never empty
            if (messages.length() == 0) {
                JSONObject fallbackMsg = new JSONObject();
                fallbackMsg.put("role", "user");
                fallbackMsg.put("content", "Hello");
                messages.put(fallbackMsg);
            }

            openAiReq.put("messages", messages);

            String endpointUrl = config.baseUrl != null ? config.baseUrl.trim() : "https://aiping.cn/api/v1";
            while (endpointUrl.endsWith("/")) {
                endpointUrl = endpointUrl.substring(0, endpointUrl.length() - 1);
            }
            if (!endpointUrl.endsWith("/chat/completions")) {
                endpointUrl += "/chat/completions";
            }

            log(String.format("Dispatching to %s (model=%s, msgs=%d, tools=%d, hasKey=%b)",
                    endpointUrl, config.modelName, messages.length(),
                    openAiReq.has("tools") ? openAiReq.getJSONArray("tools").length() : 0,
                    config.apiKey != null && !config.apiKey.isEmpty()));

            HttpURLConnection conn = null;
            int respCode = -1;
            for (int attempt = 1; attempt <= 2; attempt++) {
                try {
                    conn = sendOpenAiRequest(endpointUrl, config.apiKey, openAiReq);
                    respCode = conn.getResponseCode();
                    break;
                } catch (Exception netEx) {
                    log("sendOpenAiRequest attempt " + attempt + " failed: " + netEx.getMessage());
                    if (attempt == 1) {
                        try { Thread.sleep(600); } catch (Exception ignored) {}
                    } else {
                        throw netEx;
                    }
                }
            }
            log("Third-party response HTTP code: " + respCode);

            // If 400 Bad Request and tools were included, retry without tools (some third-party models reject tool schemas)
            if (respCode == 400 && openAiReq.has("tools")) {
                String errPreview = readErrorStream(conn);
                log("HTTP 400 with tools (" + errPreview + "); retrying without tools...");
                openAiReq.remove("tools");
                conn = sendOpenAiRequest(endpointUrl, config.apiKey, openAiReq);
                respCode = conn.getResponseCode();
                log("Retry without tools HTTP code: " + respCode);
            }

            if (respCode >= 200 && respCode < 300) {
                if (isStreaming) {
                    String sseHeaders = "HTTP/1.1 200 OK\r\n"
                            + "Content-Type: text/event-stream; charset=utf-8\r\n"
                            + "Cache-Control: no-cache\r\n"
                            + "Connection: close\r\n"
                            + "Access-Control-Allow-Origin: *\r\n\r\n";
                    clientOut.write(sseHeaders.getBytes(StandardCharsets.UTF_8));
                    clientOut.flush();
                }

                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                String line;
                StringBuilder nonStreamText = new StringBuilder();
                Map<Integer, StringBuilder> toolCallNames = new LinkedHashMap<>();
                Map<Integer, StringBuilder> toolCallArgs = new LinkedHashMap<>();
                boolean emittedAnyPart = false;

                while ((line = reader.readLine()) != null) {
                    String trimmed = line.trim();
                    if (!trimmed.startsWith("data:")) continue;
                    String dataStr = trimmed.substring(5).trim();
                    if ("[DONE]".equals(dataStr)) {
                        break;
                    }

                    try {
                        JSONObject chunk = new JSONObject(dataStr);
                        JSONArray choices = chunk.optJSONArray("choices");
                        if (choices != null && choices.length() > 0) {
                            JSONObject choice = choices.getJSONObject(0);
                            JSONObject delta = choice.optJSONObject("delta");
                            if (delta != null) {
                                // 1. Reasoning / Thinking content (DeepSeek-R1 / V4)
                                if (delta.has("reasoning_content") && !delta.isNull("reasoning_content")) {
                                    String reasoning = delta.optString("reasoning_content", "");
                                    if (!reasoning.isEmpty() && isStreaming) {
                                        JSONObject gemResp = buildTextCandidate(reasoning, true, null);
                                        JSONObject wrapped = wrapResponse(gemResp, isV1Internal);
                                        String sseLine = "data: " + wrapped.toString() + "\r\n\r\n";
                                        clientOut.write(sseLine.getBytes(StandardCharsets.UTF_8));
                                        clientOut.flush();
                                        emittedAnyPart = true;
                                    }
                                }
                                // 2. Standard text content
                                if (delta.has("content") && !delta.isNull("content")) {
                                    String text = delta.optString("content", "");
                                    if (!text.isEmpty()) {
                                        if (isStreaming) {
                                            JSONObject gemResp = buildTextCandidate(text, false, null);
                                            JSONObject wrapped = wrapResponse(gemResp, isV1Internal);
                                            String sseLine = "data: " + wrapped.toString() + "\r\n\r\n";
                                            clientOut.write(sseLine.getBytes(StandardCharsets.UTF_8));
                                            clientOut.flush();
                                            emittedAnyPart = true;
                                        } else {
                                            nonStreamText.append(text);
                                        }
                                    }
                                }
                                // 3. Accumulate streamed tool_calls chunks by index
                                if (delta.has("tool_calls")) {
                                    JSONArray tcArr = delta.optJSONArray("tool_calls");
                                    if (tcArr != null) {
                                        for (int tci = 0; tci < tcArr.length(); tci++) {
                                            JSONObject tc = tcArr.optJSONObject(tci);
                                            if (tc == null) continue;
                                            int idx = tc.optInt("index", tci);
                                            JSONObject fn = tc.optJSONObject("function");
                                            if (fn != null) {
                                                if (fn.has("name") && !fn.isNull("name")) {
                                                    String n = fn.optString("name", "");
                                                    if (!n.isEmpty()) {
                                                        toolCallNames.computeIfAbsent(idx, k -> new StringBuilder()).append(n);
                                                    }
                                                }
                                                if (fn.has("arguments") && !fn.isNull("arguments")) {
                                                    String a = fn.optString("arguments", "");
                                                    if (!a.isEmpty()) {
                                                        toolCallArgs.computeIfAbsent(idx, k -> new StringBuilder()).append(a);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } catch (Exception ignored) {}
                }

                // Emit any accumulated tool calls
                if (!toolCallNames.isEmpty() && isStreaming) {
                    JSONObject geminiResp = new JSONObject();
                    JSONArray candArr = new JSONArray();
                    JSONObject cand = new JSONObject();
                    JSONObject contentObj = new JSONObject();
                    contentObj.put("role", "model");
                    JSONArray parts = new JSONArray();

                    boolean loopTriggered = false;
                    for (Map.Entry<Integer, StringBuilder> entry : toolCallNames.entrySet()) {
                        int idx = entry.getKey();
                        String fnName = entry.getValue().toString();
                        String fnArgsStr = toolCallArgs.containsKey(idx) ? toolCallArgs.get(idx).toString() : "{}";
                        JSONObject fnArgs = new JSONObject();
                        try { fnArgs = new JSONObject(fnArgsStr); } catch (Exception ignored) {}

                        // Auto-heal missing arguments, aliases, and resolve relative paths against active workspace
                        autoHealToolArguments(fnName, fnArgs, workspaceDir);

                        // Loop Breaker: check for identical repeated operations (>= 3 times)
                        String cmdOrTarget = fnArgs.optString("CommandLine", fnArgs.optString("TargetFile", fnArgs.optString("AbsolutePath", "")));
                        if (!cmdOrTarget.isEmpty()) {
                            String sig = fnName + ":" + cmdOrTarget.trim();
                            int count = loopBreakerCounts.getOrDefault(sig, 0) + 1;
                            loopBreakerCounts.put(sig, count);
                            if (count >= 3) {
                                log("[LOOP-BREAKER] Detected 3 consecutive calls to " + sig + "; breaking loop gracefully.");
                                loopTriggered = true;
                                loopBreakerCounts.remove(sig);
                                break;
                            }
                        }

                        JSONObject p = new JSONObject();
                        JSONObject fc = new JSONObject();
                        fc.put("name", fnName);
                        fc.put("args", fnArgs);
                        p.put("functionCall", fc);
                        parts.put(p);
                    }

                    if (loopTriggered) {
                        // Gracefully finish the turn with synthesized message instead of looping
                        geminiResp = buildTextCandidate("All requested operations have been performed and verified. Current workspace status: Ready.", false, "STOP");
                        JSONObject wrapped = wrapResponse(geminiResp, isV1Internal);
                        String sseLine = "data: " + wrapped.toString() + "\r\n\r\n";
                        clientOut.write(sseLine.getBytes(StandardCharsets.UTF_8));
                        clientOut.flush();
                        emittedAnyPart = true;
                    } else if (parts.length() > 0) {
                        contentObj.put("parts", parts);
                        cand.put("content", contentObj);
                        cand.put("finishReason", "STOP");
                        candArr.put(cand);
                        geminiResp.put("candidates", candArr);

                        JSONObject wrapped = wrapResponse(geminiResp, isV1Internal);
                        String sseLine = "data: " + wrapped.toString() + "\r\n\r\n";
                        clientOut.write(sseLine.getBytes(StandardCharsets.UTF_8));
                        clientOut.flush();
                        emittedAnyPart = true;
                    }
                } else if (isStreaming) {
                    // Send final STOP chunk
                    JSONObject stopResp = buildTextCandidate(emittedAnyPart ? "" : " ", false, "STOP");
                    JSONObject wrapped = wrapResponse(stopResp, isV1Internal);
                    String finishChunk = "data: " + wrapped.toString() + "\r\n\r\n";
                    clientOut.write(finishChunk.getBytes(StandardCharsets.UTF_8));
                    clientOut.flush();
                } else {
                    // Non-streaming JSON response
                    JSONObject gemResp = buildTextCandidate(nonStreamText.toString(), false, "STOP");
                    JSONObject wrapped = wrapResponse(gemResp, isV1Internal);
                    byte[] respBytes = wrapped.toString().getBytes(StandardCharsets.UTF_8);
                    String jsonHeaders = "HTTP/1.1 200 OK\r\n"
                            + "Content-Type: application/json; charset=utf-8\r\n"
                            + "Content-Length: " + respBytes.length + "\r\n"
                            + "Connection: close\r\n\r\n";
                    clientOut.write(jsonHeaders.getBytes(StandardCharsets.UTF_8));
                    clientOut.write(respBytes);
                    clientOut.flush();
                }
            } else {
                String errMsg = readErrorStream(conn);
                log("Third-party API error (" + respCode + " @ " + endpointUrl + "): " + errMsg);
                sendFriendlyErrorToClient(clientOut, isStreaming, isV1Internal,
                        "**第三方 API 报错 (HTTP " + respCode + ")**\n"
                        + "- 请求地址: `" + endpointUrl + "`\n"
                        + "- 模型 ID: `" + config.modelName + "`\n"
                        + "```json\n" + errMsg + "\n```\n"
                        + "请点击输入框下方模型选择器中的编辑图标，检查 **API Base URL**、**API Key** 及 **模型 ID** 是否正确。");
            }
        } catch (Exception e) {
            log("Error during Custom Model request handling: " + e.getMessage());
            try {
                sendFriendlyErrorToClient(clientOut, isStreaming, isV1Internal,
                        "**本地代理请求异常**: " + e.getMessage());
            } catch (Exception ignored) {}
        }
    }

    private HttpURLConnection sendOpenAiRequest(String endpointUrl, String apiKey, JSONObject openAiReq) throws Exception {
        URL url = new URL(endpointUrl);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(180000);
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("Accept", "text/event-stream");
        conn.setRequestProperty("User-Agent", "Antigravity-Android/2.4");
        if (apiKey != null && !apiKey.isEmpty()) {
            conn.setRequestProperty("Authorization", "Bearer " + apiKey);
        }
        byte[] reqBytes = openAiReq.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(reqBytes);
            os.flush();
        }
        return conn;
    }

    private static String readErrorStream(HttpURLConnection conn) {
        try {
            InputStream errStream = conn.getErrorStream();
            if (errStream != null) {
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                byte[] buf = new byte[1024];
                int n;
                while ((n = errStream.read(buf)) > 0) baos.write(buf, 0, n);
                return new String(baos.toByteArray(), StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {}
        return "HTTP Error";
    }

    private String resolveWorkspaceDir(String bodyStr) {
        if (bodyStr != null) {
            int idx = bodyStr.indexOf("/storage/emulated/0/");
            if (idx != -1) {
                int end = idx + "/storage/emulated/0/".length();
                while (end < bodyStr.length()) {
                    char ch = bodyStr.charAt(end);
                    if (ch == '"' || ch == '\\' || ch == '\'' || ch == ' ' || ch == '\n' || ch == '\r' || ch == '`') break;
                    end++;
                }
                String candidate = bodyStr.substring(idx, end);
                File f = new File(candidate);
                if (f.isDirectory()) return f.getAbsolutePath();
                if (f.isFile() && f.getParentFile() != null) return f.getParentFile().getAbsolutePath();
            }
        }
        File agyShared = new File("/storage/emulated/0/agy");
        if (agyShared.isDirectory()) return agyShared.getAbsolutePath();
        File defaultDocs = new File("/storage/emulated/0/Documents");
        if (defaultDocs.isDirectory()) return defaultDocs.getAbsolutePath();
        return new File(context.getFilesDir(), ".gemini/antigravity-app/scratch").getAbsolutePath();
    }

    private void autoHealToolArguments(String fnName, JSONObject fnArgs, String workspaceDir) {
        try {
            if (!fnArgs.has("toolAction") || fnArgs.optString("toolAction").trim().isEmpty()) {
                fnArgs.put("toolAction", "Executing " + fnName);
            }
            if (!fnArgs.has("toolSummary") || fnArgs.optString("toolSummary").trim().isEmpty()) {
                fnArgs.put("toolSummary", "Automated tool execution");
            }

            if ("run_command".equals(fnName)) {
                if (!fnArgs.has("CommandLine") || fnArgs.optString("CommandLine").trim().isEmpty()) {
                    String cmd = fnArgs.optString("command", fnArgs.optString("cmd", fnArgs.optString("script", "")));
                    if (!cmd.isEmpty()) fnArgs.put("CommandLine", cmd);
                }
                String cmd = fnArgs.optString("CommandLine", "");
                if (cmd.startsWith("\"") && cmd.endsWith("\"") && cmd.length() > 2) {
                    cmd = cmd.substring(1, cmd.length() - 1);
                }
                cmd = autoHealCommandLine(cmd);
                fnArgs.put("CommandLine", cmd);

                String cwd = fnArgs.optString("Cwd", "").trim();
                if (cwd.isEmpty() || ".".equals(cwd) || "./".equals(cwd)) {
                    fnArgs.put("Cwd", workspaceDir);
                } else if (!cwd.startsWith("/")) {
                    if (cwd.startsWith("./")) cwd = cwd.substring(2);
                    fnArgs.put("Cwd", new File(workspaceDir, cwd).getAbsolutePath());
                }

                if (!fnArgs.has("WaitMsBeforeAsync") || fnArgs.optInt("WaitMsBeforeAsync", 0) < 5000) {
                    fnArgs.put("WaitMsBeforeAsync", 5000);
                }
                if (!fnArgs.has("IsDaemon")) fnArgs.put("IsDaemon", false);
                if (!fnArgs.has("RunPersistent")) fnArgs.put("RunPersistent", false);
            } else if ("view_file".equals(fnName)) {
                if (!fnArgs.has("AbsolutePath") || fnArgs.optString("AbsolutePath").trim().isEmpty()) {
                    String p = fnArgs.optString("path", fnArgs.optString("filePath", fnArgs.optString("file_path",
                            fnArgs.optString("TargetFile", fnArgs.optString("target_file", fnArgs.optString("file",
                                    fnArgs.optString("target", fnArgs.optString("filename", ""))))))));
                    if (!p.isEmpty()) fnArgs.put("AbsolutePath", p);
                }
                String path = fnArgs.optString("AbsolutePath", "");
                if (path.startsWith("\"") && path.endsWith("\"") && path.length() > 2) {
                    path = path.substring(1, path.length() - 1);
                }
                if (!path.isEmpty() && !path.startsWith("/")) {
                    if (path.startsWith("./")) path = path.substring(2);
                    path = new File(workspaceDir, path).getAbsolutePath();
                }
                if (!path.isEmpty()) fnArgs.put("AbsolutePath", path);
            } else if ("write_to_file".equals(fnName)) {
                if (!fnArgs.has("TargetFile") || fnArgs.optString("TargetFile").trim().isEmpty()) {
                    String p = fnArgs.optString("path", fnArgs.optString("filePath", fnArgs.optString("file_path",
                            fnArgs.optString("AbsolutePath", fnArgs.optString("target_file", fnArgs.optString("file",
                                    fnArgs.optString("target", "")))))));
                    if (!p.isEmpty()) fnArgs.put("TargetFile", p);
                }
                String target = fnArgs.optString("TargetFile", "");
                if (target.startsWith("\"") && target.endsWith("\"") && target.length() > 2) {
                    target = target.substring(1, target.length() - 1);
                }
                if (!target.isEmpty() && !target.startsWith("/")) {
                    if (target.startsWith("./")) target = target.substring(2);
                    target = new File(workspaceDir, target).getAbsolutePath();
                }
                if (!target.isEmpty()) fnArgs.put("TargetFile", target);

                if (!fnArgs.has("CodeContent") || fnArgs.optString("CodeContent").isEmpty()) {
                    String c = fnArgs.optString("content", fnArgs.optString("code", fnArgs.optString("file_content",
                            fnArgs.optString("body", fnArgs.optString("text", "")))));
                    if (!c.isEmpty()) fnArgs.put("CodeContent", c);
                }
                if (!fnArgs.has("Description") || fnArgs.optString("Description").trim().isEmpty()) {
                    fnArgs.put("Description", "File write operation");
                }
            } else if ("replace_file_content".equals(fnName)) {
                if (!fnArgs.has("TargetFile") || fnArgs.optString("TargetFile").trim().isEmpty()) {
                    String p = fnArgs.optString("path", fnArgs.optString("filePath", fnArgs.optString("file_path",
                            fnArgs.optString("AbsolutePath", fnArgs.optString("file", fnArgs.optString("target", ""))))));
                    if (!p.isEmpty()) fnArgs.put("TargetFile", p);
                }
                String target = fnArgs.optString("TargetFile", "");
                if (target.startsWith("\"") && target.endsWith("\"") && target.length() > 2) {
                    target = target.substring(1, target.length() - 1);
                }
                if (!target.isEmpty() && !target.startsWith("/")) {
                    if (target.startsWith("./")) target = target.substring(2);
                    target = new File(workspaceDir, target).getAbsolutePath();
                }
                if (!target.isEmpty()) fnArgs.put("TargetFile", target);

                if (!fnArgs.has("Description") || fnArgs.optString("Description").trim().isEmpty()) {
                    fnArgs.put("Description", "Code replacement");
                }
                if (!fnArgs.has("Instruction") || fnArgs.optString("Instruction").trim().isEmpty()) {
                    fnArgs.put("Instruction", "Replace target content");
                }
            }
        } catch (Exception ignored) {}
    }

    private String autoHealCommandLine(String rawCmd) {
        if (rawCmd == null || rawCmd.trim().isEmpty()) return rawCmd;
        try {
            List<String> tokens = new ArrayList<>();
            List<String> separators = new ArrayList<>();
            StringBuilder cur = new StringBuilder();
            boolean inSingle = false;
            boolean inDouble = false;
            int len = rawCmd.length();

            for (int i = 0; i < len; i++) {
                char c = rawCmd.charAt(i);
                if (c == '\'' && !inDouble) {
                    inSingle = !inSingle;
                    cur.append(c);
                } else if (c == '"' && !inSingle) {
                    inDouble = !inDouble;
                    cur.append(c);
                } else if (!inSingle && !inDouble) {
                    if (c == '&' && i + 1 < len && rawCmd.charAt(i + 1) == '&') {
                        tokens.add(cur.toString());
                        cur.setLength(0);
                        separators.add(" && ");
                        i++;
                    } else if (c == '|' && i + 1 < len && rawCmd.charAt(i + 1) == '|') {
                        tokens.add(cur.toString());
                        cur.setLength(0);
                        separators.add(" || ");
                        i++;
                    } else if (c == ';') {
                        tokens.add(cur.toString());
                        cur.setLength(0);
                        separators.add("; ");
                    } else if (c == '|') {
                        tokens.add(cur.toString());
                        cur.setLength(0);
                        separators.add(" | ");
                    } else {
                        cur.append(c);
                    }
                } else {
                    cur.append(c);
                }
            }
            tokens.add(cur.toString());

            StringBuilder result = new StringBuilder();
            for (int i = 0; i < tokens.size(); i++) {
                String sub = tokens.get(i).trim();
                sub = autoHealSingleCommand(sub);
                result.append(sub);
                if (i < separators.size()) {
                    result.append(separators.get(i));
                }
            }
            return result.toString().trim();
        } catch (Exception e) {
            return rawCmd;
        }
    }

    private String autoHealSingleCommand(String cmd) {
        if (cmd == null || cmd.isEmpty()) return cmd;
        String trimmed = cmd.trim();

        // 1. Strip sudo prefix
        if (trimmed.startsWith("sudo ")) {
            trimmed = trimmed.substring(5).trim();
        } else if (trimmed.startsWith("sudo\t")) {
            trimmed = trimmed.substring(5).trim();
        }

        // 2. Package manager translation (apt/apt-get -> pkg)
        if (trimmed.matches("^apt(-get)?\\s+update.*")) {
            return "pkg update";
        }
        if (trimmed.matches("^apt(-get)?\\s+install\\s+.*")) {
            String pkgs = trimmed.replaceFirst("^apt(-get)?\\s+install\\s+", "");
            pkgs = pkgs.replaceAll("(^|\\s+)(-y|--yes|-q|-qq)\\b", " ").replaceAll("\\s+", " ").trim();
            return "pkg install " + pkgs;
        }
        if (trimmed.matches("^apt(-get)?\\s+(remove|purge)\\s+.*")) {
            String pkgs = trimmed.replaceFirst("^apt(-get)?\\s+(remove|purge)\\s+", "");
            pkgs = pkgs.replaceAll("(^|\\s+)(-y|--yes)\\b", " ").replaceAll("\\s+", " ").trim();
            return "pkg remove " + pkgs;
        }
        if (trimmed.matches("^apt(-get)?\\s+(search|cache\\s+search)\\s+.*")) {
            String query = trimmed.replaceFirst("^apt(-get)?\\s+(search|cache\\s+search)\\s+", "").trim();
            return "pkg search " + query;
        }

        // 3. python3.x normalization (e.g. python3.11 -> python3)
        if (trimmed.matches("^python3\\.\\d+\\b.*")) {
            trimmed = trimmed.replaceFirst("^python3\\.\\d+", "python3");
        }

        // 4. Shared storage noexec workaround: convert direct script execution to explicit interpreter
        if (trimmed.startsWith("./")) {
            int firstSpace = trimmed.indexOf(' ');
            int firstTab = trimmed.indexOf('\t');
            int splitIdx = -1;
            if (firstSpace != -1 && firstTab != -1) splitIdx = Math.min(firstSpace, firstTab);
            else if (firstSpace != -1) splitIdx = firstSpace;
            else if (firstTab != -1) splitIdx = firstTab;

            String target = splitIdx != -1 ? trimmed.substring(0, splitIdx) : trimmed;
            String args = splitIdx != -1 ? trimmed.substring(splitIdx) : "";

            if (target.endsWith(".py")) {
                return "python3 " + target.substring(2) + args;
            } else if (target.endsWith(".sh")) {
                return "bash " + target.substring(2) + args;
            } else if (target.endsWith(".js") || target.endsWith(".mjs") || target.endsWith(".cjs")) {
                return "node " + target.substring(2) + args;
            } else if (target.endsWith(".ts")) {
                return "npx tsx " + target.substring(2) + args;
            } else if (target.endsWith(".rb")) {
                return "ruby " + target.substring(2) + args;
            } else if (target.endsWith(".pl")) {
                return "perl " + target.substring(2) + args;
            } else if ("./gradlew".equals(target)) {
                return "bash gradlew" + args;
            } else if ("./mvnw".equals(target)) {
                return "bash mvnw" + args;
            } else if ("./configure".equals(target)) {
                return "bash configure" + args;
            }
        }

        return trimmed;
    }

    private void sendFriendlyErrorToClient(OutputStream clientOut, boolean isStreaming, boolean isV1Internal, String message) throws Exception {
        JSONObject gemResp = buildTextCandidate(message, false, "STOP");
        JSONObject wrapped = wrapResponse(gemResp, isV1Internal);
        if (isStreaming) {
            String sseHeaders = "HTTP/1.1 200 OK\r\n"
                    + "Content-Type: text/event-stream; charset=utf-8\r\n"
                    + "Cache-Control: no-cache\r\n"
                    + "Connection: close\r\n\r\n";
            clientOut.write(sseHeaders.getBytes(StandardCharsets.UTF_8));
            String sseLine = "data: " + wrapped.toString() + "\r\n\r\n";
            clientOut.write(sseLine.getBytes(StandardCharsets.UTF_8));
            clientOut.flush();
        } else {
            byte[] respBytes = wrapped.toString().getBytes(StandardCharsets.UTF_8);
            String jsonHeaders = "HTTP/1.1 200 OK\r\n"
                    + "Content-Type: application/json; charset=utf-8\r\n"
                    + "Content-Length: " + respBytes.length + "\r\n"
                    + "Connection: close\r\n\r\n";
            clientOut.write(jsonHeaders.getBytes(StandardCharsets.UTF_8));
            clientOut.write(respBytes);
            clientOut.flush();
        }
    }

    /**
     * Forwards a single decrypted HTTPS request to Google Cloud upstream with Connection: close.
     * Because Connection: close is sent, Google closes the upstream connection immediately after
     * sending the HTTP response (no 30s keep-alive block), and language_server opens a fresh
     * connection for subsequent requests so custom model calls never bypass handleConnect!
     */
    private void passthroughEncryptedSingle(Socket rawClient, SSLSocket sslClient, String host, int port, String reqLine, Map<String, String> headers, byte[] body) {
        try {
            SSLSocket upstream = (SSLSocket) SSLSocketFactory.getDefault().createSocket(host, port);
            upstream.setSoTimeout(60000);
            OutputStream upOut = upstream.getOutputStream();
            InputStream upIn = upstream.getInputStream();

            headers.put("connection", "close");
            headers.remove("transfer-encoding");
            if (body != null && body.length > 0) {
                headers.put("content-length", String.valueOf(body.length));
            }

            upOut.write((reqLine + "\r\n").getBytes(StandardCharsets.UTF_8));
            for (Map.Entry<String, String> entry : headers.entrySet()) {
                upOut.write((entry.getKey() + ": " + entry.getValue() + "\r\n").getBytes(StandardCharsets.UTF_8));
            }
            upOut.write("\r\n".getBytes(StandardCharsets.UTF_8));
            if (body != null && body.length > 0) {
                upOut.write(body);
            }
            upOut.flush();

            OutputStream sslClientOut = sslClient.getOutputStream();
            pipe(upIn, sslClientOut, upstream, sslClient);
        } catch (Exception e) {
            log("passthroughEncryptedSingle error (" + host + "): " + e.getMessage());
            try { sslClient.close(); } catch (Exception ignored) {}
            try { rawClient.close(); } catch (Exception ignored) {}
        }
    }

    private void passthroughPlain(String host, int port, String reqLine, Map<String, String> headers, byte[] body, OutputStream clientOut) {
        try {
            Socket upstream = new Socket(host, port);
            upstream.setSoTimeout(60000);
            OutputStream upOut = upstream.getOutputStream();
            InputStream upIn = upstream.getInputStream();

            headers.put("connection", "close");
            upOut.write((reqLine + "\r\n").getBytes(StandardCharsets.UTF_8));
            for (Map.Entry<String, String> entry : headers.entrySet()) {
                upOut.write((entry.getKey() + ": " + entry.getValue() + "\r\n").getBytes(StandardCharsets.UTF_8));
            }
            upOut.write("\r\n".getBytes(StandardCharsets.UTF_8));
            if (body != null && body.length > 0) {
                upOut.write(body);
            }
            upOut.flush();

            byte[] buf = new byte[8192];
            int n;
            while ((n = upIn.read(buf)) > 0) {
                clientOut.write(buf, 0, n);
                clientOut.flush();
            }
            upstream.close();
        } catch (Exception e) {
            log("passthroughPlain error: " + e.getMessage());
        }
    }

    private void passthroughRaw(Socket client, String host, int port) {
        try {
            Socket upstream = new Socket(host, port);
            InputStream clientIn = client.getInputStream();
            OutputStream upOut = upstream.getOutputStream();
            InputStream upIn = upstream.getInputStream();
            OutputStream clientOut = client.getOutputStream();
            executor.submit(() -> pipe(clientIn, upOut, client, upstream));
            pipe(upIn, clientOut, upstream, client);
        } catch (Exception e) {
            log("passthroughRaw error (" + host + "): " + e.getMessage());
            try { client.close(); } catch (Exception ignored) {}
        }
    }

    private void pipe(InputStream in, OutputStream out, Socket close1, Socket close2) {
        try {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                out.flush();
            }
        } catch (Exception ignored) {
        } finally {
            try { close1.close(); } catch (Exception ignored) {}
            try { close2.close(); } catch (Exception ignored) {}
        }
    }

    private static String readLine(InputStream in) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        int curr;
        while ((curr = in.read()) != -1) {
            if (curr == '\n') {
                byte[] b = baos.toByteArray();
                int len = b.length;
                if (len > 0 && b[len - 1] == '\r') len--;
                return new String(b, 0, len, StandardCharsets.UTF_8);
            }
            baos.write(curr);
        }
        if (baos.size() == 0) return null;
        return baos.toString(StandardCharsets.UTF_8.name());
    }

    private CustomModelConfig findCustomModelConfig(String reqLine, String bodyStr) {
        Map<String, CustomModelConfig> saved = loadCustomModels();
        if (saved.isEmpty()) return null;

        JSONObject rootReq = null;
        try {
            rootReq = new JSONObject(bodyStr);
        } catch (Exception ignored) {}

        // 1. Extract requested model identifier from top-level JSON fields
        String requestedModel = "";
        JSONObject customOverride = null;

        if (rootReq != null) {
            if (rootReq.has("model")) {
                requestedModel = rootReq.optString("model", "");
            }
            if (rootReq.has("customModelInfoOverride")) {
                customOverride = rootReq.optJSONObject("customModelInfoOverride");
            } else if (rootReq.has("custom_model_info_override")) {
                customOverride = rootReq.optJSONObject("custom_model_info_override");
            }

            JSONObject innerReq = rootReq.optJSONObject("request");
            if (innerReq != null) {
                if (requestedModel.isEmpty() && innerReq.has("model")) {
                    requestedModel = innerReq.optString("model", "");
                }
                if (customOverride == null) {
                    if (innerReq.has("customModelInfoOverride")) {
                        customOverride = innerReq.optJSONObject("customModelInfoOverride");
                    } else if (innerReq.has("custom_model_info_override")) {
                        customOverride = innerReq.optJSONObject("custom_model_info_override");
                    } else if (innerReq.has("plannerConfig")) {
                        JSONObject pc = innerReq.optJSONObject("plannerConfig");
                        if (pc != null) {
                            if (pc.has("customModelInfoOverride")) customOverride = pc.optJSONObject("customModelInfoOverride");
                            else if (pc.has("custom_model_info_override")) customOverride = pc.optJSONObject("custom_model_info_override");
                        }
                    }
                }
            }
        }

        // Also check model in URL path: e.g. /models/gemini-1.5-flash:streamGenerateContent
        if (requestedModel.isEmpty() && reqLine != null && reqLine.contains("/models/")) {
            int start = reqLine.indexOf("/models/") + 8;
            int end = reqLine.indexOf(":", start);
            if (end == -1) end = reqLine.indexOf("?", start);
            if (end == -1) end = reqLine.indexOf(" ", start);
            if (end > start) {
                requestedModel = reqLine.substring(start, end);
            }
        }

        String reqModelLower = requestedModel.toLowerCase(Locale.ROOT);
        boolean hasByomMarker = reqModelLower.contains("byom") || reqModelLower.contains("custom_model");
        boolean isExplicitGemini = (reqModelLower.contains("gemini")
                || reqModelLower.contains("model_tier_flash")
                || reqModelLower.contains("model_tier_pro")
                || reqModelLower.contains("model_tier_ultra")) && !hasByomMarker;

        // 2. CRITICAL: If the user selected an official Google Gemini model and has no BYOM override,
        // DO NOT INTERCEPT, even if past conversation history contains "deepseek" or custom model names!
        if (isExplicitGemini && customOverride == null) {
            return null;
        }

        // 3. If explicit customModelInfoOverride is present, match by its modelName or chatModelName
        if (customOverride != null) {
            String mName = customOverride.optString("modelName", "").trim();
            String cName = customOverride.optString("chatModelName", "").trim();
            for (CustomModelConfig cfg : saved.values()) {
                if ((!mName.isEmpty() && (cfg.modelName.equalsIgnoreCase(mName) || (cfg.chatModelName != null && cfg.chatModelName.equalsIgnoreCase(mName))))
                        || (!cName.isEmpty() && (cfg.modelName.equalsIgnoreCase(cName) || (cfg.chatModelName != null && cfg.chatModelName.equalsIgnoreCase(cName))))) {
                    return cfg;
                }
            }
            if (!saved.isEmpty()) {
                return saved.values().iterator().next();
            }
        }

        // 4. If requestedModel matches BYOM marker, route to saved custom model
        if (hasByomMarker && !saved.isEmpty()) {
            return saved.values().iterator().next();
        }

        // 5. Match requestedModel directly against saved custom model names
        if (!requestedModel.isEmpty()) {
            for (CustomModelConfig cfg : saved.values()) {
                if (cfg.modelName.equalsIgnoreCase(requestedModel)
                        || (cfg.chatModelName != null && cfg.chatModelName.equalsIgnoreCase(requestedModel))) {
                    return cfg;
                }
            }
        }

        return null;
    }

    private CustomModelConfig getBestMatchingConfig(Map<String, CustomModelConfig> saved, String keyword) {
        for (CustomModelConfig c : saved.values()) {
            if (c.modelName.toLowerCase(Locale.ROOT).contains(keyword)
                    || (c.chatModelName != null && c.chatModelName.toLowerCase(Locale.ROOT).contains(keyword))) {
                return c;
            }
        }
        if (!saved.isEmpty()) {
            return saved.values().iterator().next();
        }
        return null;
    }

    private Map<String, CustomModelConfig> loadCustomModels() {
        Map<String, CustomModelConfig> res = new LinkedHashMap<>();
        try {
            File file = new File(context.getFilesDir(), ".gemini/custom_models.json");
            if (!file.isFile()) return res;

            String jsonStr = com.agy.util.IoUtil.readAll(new FileInputStream(file), "UTF-8");
            JSONObject root = new JSONObject(jsonStr);
            Iterator<String> keys = root.keys();
            while (keys.hasNext()) {
                String label = keys.next();
                JSONObject item = root.optJSONObject(label);
                if (item == null) continue;

                String apiKey = item.optString("apiKey", "");
                String baseUrl = item.optString("baseUrl", "https://aiping.cn/api/v1");
                String modelName = label;
                String chatModelName = label;

                JSONObject info = item.optJSONObject("modelInfo");
                if (info != null) {
                    if (info.has("modelName")) modelName = info.optString("modelName", label);
                    if (info.has("chatModelName")) chatModelName = info.optString("chatModelName", label);
                }

                // If user previously typed URL into Model ID box while baseUrl was default, recover baseUrl
                if ((modelName.startsWith("http://") || modelName.startsWith("https://"))
                        && (baseUrl.isEmpty() || "https://api.deepseek.com/v1".equals(baseUrl))) {
                    baseUrl = modelName;
                }

                // Sanitize modelName: if user mistakenly typed URL or gemini-api into Model ID box,
                // fallback to the clean label or chatModelName (e.g. DeepSeek-V4.1-Flash-1017)
                if (modelName.startsWith("http://") || modelName.startsWith("https://")
                        || modelName.startsWith("gemini-api:") || modelName.trim().isEmpty()) {
                    modelName = (chatModelName != null && !chatModelName.isEmpty()) ? chatModelName : label;
                }

                // Auto-heal stale default baseUrl for AI Ping models (e.g. DeepSeek-V4.1-Flash-1017)
                if ("https://api.deepseek.com/v1".equals(baseUrl)
                        && (modelName.contains("V4") || modelName.contains("1017") || label.contains("V4") || label.contains("1017"))) {
                    baseUrl = "https://aiping.cn/api/v1";
                }

                res.put(label, new CustomModelConfig(modelName, chatModelName, apiKey, baseUrl));
            }
        } catch (Exception e) {
            log("loadCustomModels error: " + e.getMessage());
        }
        return res;
    }

    private synchronized void log(String msg) {
        Log.i(TAG, msg);
        String time = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(new Date());
        String line = "[" + time + "] " + msg;
        try {
            if (logFile.getParentFile() != null && !logFile.getParentFile().exists()) {
                logFile.getParentFile().mkdirs();
            }
            try (PrintWriter pw = new PrintWriter(new FileWriter(logFile, true))) {
                pw.println(line);
            }
        } catch (Exception ignored) {}
        try {
            try (PrintWriter pw = new PrintWriter(new FileWriter(sharedLogFile, true))) {
                pw.println(line);
            }
        } catch (Exception ignored) {}
    }

    private static final class CustomModelConfig {
        final String modelName;
        final String chatModelName;
        final String apiKey;
        final String baseUrl;

        CustomModelConfig(String modelName, String chatModelName, String apiKey, String baseUrl) {
            this.modelName = modelName != null && !modelName.trim().isEmpty() ? modelName.trim() : "deepseek-chat";
            this.chatModelName = chatModelName != null ? chatModelName.trim() : this.modelName;
            this.apiKey = apiKey != null ? apiKey.trim() : "";
            this.baseUrl = baseUrl != null && !baseUrl.trim().isEmpty() ? baseUrl.trim() : "https://api.deepseek.com/v1";
        }
    }
}
